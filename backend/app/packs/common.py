"""Building blocks shared by the industry packs: profiles copied from a base profile, ledger balances,
dated reminders and append-only rules."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, Numeric, false, func, select, text
from sqlalchemy.orm import Session

from app.apps.service import notify
from app.core.clock import local_today
from app.engine.types import money
from app.models import Notification, Record
from app.packs import grant, permission_key
from app.security.seed_v1 import _flags
from app.security.seed_v1 import stable_id as security_id

# (key, name, description, base profile, {object: permission code}, system permissions, custom permissions)
ProfileSpec = tuple[str, str, str, str, dict[str, str], tuple[str, ...], tuple[str, ...]]


def install_profiles(conn: Connection, pack_key: str, profiles: Iterable[ProfileSpec]) -> None:
    """Create each pack profile as a copy of its base profile, then apply the pack's object grants."""
    for key, name, description, base, objects, system, custom in profiles:
        pid = security_id("profile", key)
        conn.execute(
            text(
                "INSERT INTO profiles (id, key, name, description, is_locked, is_portal, created_at, updated_at) "
                "VALUES (:id, :key, :name, :description, false, false, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": pid, "key": key, "name": name, "description": description},
        )
        base_id = security_id("profile", base)
        conn.execute(
            text(
                "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all) "
                "SELECT :pid, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all "
                "FROM profile_object_permissions WHERE profile_id = :base ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        conn.execute(
            text(
                "INSERT INTO profile_system_permissions (profile_id, permission) SELECT :pid, permission FROM profile_system_permissions "
                "WHERE profile_id = :base AND permission NOT LIKE 'pack:%' ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        conn.execute(
            text(
                "INSERT INTO profile_field_permissions (profile_id, object_api_name, field_api_name, access) SELECT :pid, object_api_name, "
                "field_api_name, access FROM profile_field_permissions WHERE profile_id = :base ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        for obj, code in objects.items():
            flags = _flags(code)
            conn.execute(
                text(
                    "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all) "
                    "VALUES (:p, :o, :r, :c, :e, :d, :va, :ma) ON CONFLICT (profile_id, object_api_name) DO UPDATE SET can_read = EXCLUDED.can_read, "
                    "can_create = EXCLUDED.can_create, can_edit = EXCLUDED.can_edit, can_delete = EXCLUDED.can_delete, view_all = EXCLUDED.view_all, "
                    "modify_all = EXCLUDED.modify_all"
                ),
                {
                    "p": pid,
                    "o": obj,
                    "r": flags["can_read"],
                    "c": flags["can_create"],
                    "e": flags["can_edit"],
                    "d": flags["can_delete"],
                    "va": flags["view_all"],
                    "ma": flags["modify_all"],
                },
            )
        for perm in system:
            grant(conn, pid, perm)
        for perm in custom:
            grant(conn, pid, permission_key(pack_key, perm))


def ledger_balance(db: Session, obj: str, field: str, value: uuid.UUID) -> Decimal:
    """Sum of signed_amount over live rows of a ledger object where data[field] = value."""
    total = db.scalar(
        select(func.coalesce(func.sum(Record.data["signed_amount"].astext.cast(Numeric)), 0)).where(
            Record.object_api_name == obj,
            Record.is_deleted == false(),
            Record.data[field].astext == str(value),
        )
    )
    return money(Decimal(str(total or 0)))


def live(db: Session, obj: str, **equals: str) -> list[Record]:
    stmt = select(Record).where(Record.object_api_name == obj, Record.is_deleted == false())
    for field, value in equals.items():
        stmt = stmt.where(Record.data[field].astext == value)
    return list(db.scalars(stmt))


# (object, date field, title prefix, recipient)
ReminderTarget = tuple[str, str, str, Callable[[Record], str | None]]


def owner_of(record: Record) -> str | None:
    return str(record.owner_id) if record.owner_id else None


def first_of(*fields: str) -> Callable[[Record], str | None]:
    """Recipient: the first user field that is set, else the record owner."""

    def pick(record: Record) -> str | None:
        for f in fields:
            if record.data.get(f):
                return str(record.data[f])
        return owner_of(record)

    return pick


def date_reminders(
    db: Session, targets: Iterable[ReminderTarget], days: Iterable[int], today: date | None = None
) -> int:
    """Notify once per record, date field and lead time ("Settlement in 3 days: LA-2026-0001")."""
    today = today or local_today()
    count = 0
    for obj, field, label, who in targets:
        for n in days:
            day = (today + timedelta(days=int(n))).isoformat()
            rows = db.scalars(
                select(Record).where(
                    Record.object_api_name == obj,
                    Record.is_deleted == false(),
                    Record.data[field].astext.like(f"{day}%"),
                )
            ).all()
            for r in rows:
                uid = who(r)
                if not uid:
                    continue
                when = "today" if int(n) == 0 else f"in {n} days"
                title = f"{label} {when}: {r.name}"
                exists = db.scalar(
                    select(Notification.id)
                    .where(Notification.record_id == r.id, Notification.title == title)
                    .limit(1)
                )
                if exists:
                    continue
                notify(db, uuid.UUID(uid), title, f"{label} on {day}.", f"/o/{obj}/{r.id}", r.id)
                db.flush()
                count += 1
    return count


def json_ready(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


# ------------------------------------------------------------------ telling the client


def portal_users_for(db: Session, contact_ids: Iterable[Any], account_id: Any = None) -> list[Any]:
    """Active portal users for these client contacts (or, failing that, anyone at the client entity)."""
    from app.models import User

    ids = [uuid.UUID(str(c)) for c in contact_ids if c]
    users = list(db.scalars(select(User).where(User.contact_id.in_(ids), User.is_active))) if ids else []
    if not users and account_id:
        people = select(Record.id).where(
            Record.object_api_name == "contact",
            Record.is_deleted == false(),
            Record.data["account"].astext == str(account_id),
        )
        users = list(db.scalars(select(User).where(User.contact_id.in_(people), User.is_active)))
    return [u for u in users if u.profile.is_portal]


def firm_name(db: Session) -> str:
    from app.services.settings import get_setting

    return str((get_setting(db, "branding") or {}).get("name") or "Your adviser")


def tell_client(
    svc: Any,
    *,
    contact_ids: Iterable[Any],
    account_id: Any = None,
    subject: str,
    message: str,
    portal_path: str,
    record: Record,
) -> bool:
    """E-mail the client's portal users that something is waiting for them (sent after the change is
    saved). When nobody at the client can sign in yet, the person who acted is told to invite them.
    Returns whether an e-mail was queued."""
    from app.services.email import app_link, queue_after_commit

    db = svc.db
    users = portal_users_for(db, contact_ids, account_id)
    firm = firm_name(db)
    for user in users:
        first = (user.name or "").split(" ")[0] or "there"
        body = (
            f"Hello {first},\n\n{message}\n\nOpen it in your client portal:\n{app_link('/portal' + portal_path)}\n\n"
            f"{firm}\n"
        )
        queue_after_commit(db, user.email, subject, body)
    if not users and svc.user_id:
        notify(
            db,
            svc.user_id,
            f"The client can't see {record.name} yet",
            "Nobody at the client can sign in to the portal. Invite them from their client record "
            "(Invite to portal) so they can open it.",
            f"/o/{record.object_api_name}/{record.id}",
            record.id,
        )
    return bool(users)
