"""Privacy Act 1988 / APPs and GDPR-style tooling (plan v3, section 14).

- Subject access: export everything held about one person (contact or lead) as JSON.
- Erasure: anonymise the person's personal fields, related notes/files and portal account, keeping the
  records needed for legal obligations (consent proof, invoices, client-account ledger).
- Retention: per-object policies ("records not changed for N years") applied by a scheduled job; records
  go to the recycle bin first, so object hooks can veto (e.g. ledger retention) and admins can restore.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, false, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError
from app.engine.records import RecordService
from app.models import EmailDelivery, FieldHistory, Record, RecordLink, User
from app.services import audit
from app.services.audit import AuditAction
from app.services.auth import revoke_sessions
from app.services.settings import get_setting

PERSON_OBJECTS = ("contact", "lead")
# Field types that can hold personal information and are cleared on erasure.
PERSONAL_TYPES = frozenset(
    {
        "text",
        "textarea",
        "long_text",
        "email",
        "phone",
        "url",
        "address",
        "date",
        "datetime",
        "encrypted_text",
        "multi_picklist",
    }
)
ACTIVITY_OBJECTS = ("task", "event", "note", "file")


class PrivacyError(AppError):
    status_code = 422
    code = "privacy"


def _person(svc: RecordService, obj: str, record_id: uuid.UUID) -> Record:
    if obj not in PERSON_OBJECTS:
        raise PrivacyError("Privacy requests apply to contacts and leads.")
    return svc.get(obj, record_id)


def _linked(db: Session, record_id: uuid.UUID) -> list[Record]:
    """Records that point at the person through any lookup (cases, consents, activities, members...)."""
    ids = db.scalars(select(RecordLink.from_record_id).where(RecordLink.to_record_id == record_id)).all()
    if not ids:
        return []
    return list(db.scalars(select(Record).where(Record.id.in_(ids), Record.is_deleted == false())))


def export_person(svc: RecordService, obj: str, record_id: uuid.UUID) -> dict[str, Any]:
    """Subject access request: the person's record, everything linked to it, consents and e-mail history."""
    person = _person(svc, obj, record_id)
    full = svc.elevated()
    linked = _linked(svc.db, person.id)
    by_object: dict[str, list[dict[str, Any]]] = {}
    for rec in linked:
        by_object.setdefault(rec.object_api_name, []).append(full.serialize(rec))
    deliveries = svc.db.scalars(
        select(EmailDelivery).where(EmailDelivery.recipient_record_id == person.id)
    ).all()
    history = full.history(obj, person.id) if svc.registry.get(obj).track_history else []
    audit.record(
        svc.db,
        action=AuditAction.EXPORT,
        entity_type=f"record:{obj}",
        entity_id=person.id,
        summary=f"Privacy export of {obj} {person.id}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return {
        "generated_at": datetime.now(UTC),
        "subject": full.serialize(person),
        "field_history": history,
        "related": by_object,
        "email_deliveries": [
            {
                "send_id": str(d.send_record_id),
                "email": d.email,
                "status": d.status,
                "sent_at": d.sent_at,
                "opened_at": d.opened_at,
                "clicked_at": d.clicked_at,
                "unsubscribed_at": d.unsubscribed_at,
            }
            for d in deliveries
        ],
    }


def erase_person(svc: RecordService, obj: str, record_id: uuid.UUID, reason: str) -> Record:
    """Anonymise a person. Irreversible; the audit log keeps who did it and why (no personal data)."""
    if not reason.strip():
        raise PrivacyError(
            "Enter the reason for the erasure (e.g. the request reference).", fields={"reason": "Required"}
        )
    person = _person(svc, obj, record_id)
    if not svc.can_edit(person):
        raise AppError("You need edit access to this record.", code="forbidden", status_code=403)
    db = svc.db
    # Trust and client-account records name the client and are kept for 7 years (Legal Profession Uniform
    # General Rules; the migration agents' Code of Conduct).
    kept_since = datetime.now(UTC) - timedelta(days=round(365.25 * 7))
    held = db.scalar(
        select(Record.id)
        .where(
            Record.object_api_name.in_(("client_account_transaction", "trust_transaction")),
            Record.data["client"].astext == str(person.id),
            Record.created_at >= kept_since,
        )
        .limit(1)
    )
    if held is not None:
        raise ConflictError(
            "This person has trust or client-account transactions from the last 7 years, which must be "
            "kept; erasure is blocked until the retention period ends.",
            code="retention_hold",
        )
    meta = svc.registry.get(obj)
    sys = svc.elevated()
    data = dict(person.data)
    for f in meta.data_fields:
        if f.type in PERSONAL_TYPES and f.api_name in data:
            data.pop(f.api_name)
    if "last_name" in meta.fields:
        data["last_name"] = "Erased"
    for flag in ("email_opt_in",):
        if flag in meta.fields:
            data[flag] = False
    for flag in ("do_not_call",):
        if flag in meta.fields:
            data[flag] = True
    person.data = data
    person.name = f"Erased {meta.label}"
    person.version += 1
    person.updated_at = datetime.now(UTC)
    person.updated_by_id = svc.user_id
    db.execute(delete(FieldHistory).where(FieldHistory.record_id == person.id))
    for rec in _linked(db, person.id):
        if rec.object_api_name in ("note", "file"):
            sys.hard_delete(rec)
        elif rec.object_api_name in ("task", "event"):
            rec.data = {k: v for k, v in rec.data.items() if k not in ("description", "location")}
        elif rec.object_api_name == "consent":
            rec.data = {k: v for k, v in rec.data.items() if k not in ("ip_address", "notes")}
        elif rec.object_api_name == "case":
            rec.data = {k: v for k, v in rec.data.items() if k not in ("supplied_name", "supplied_email")}
    db.execute(
        update(EmailDelivery)
        .where(EmailDelivery.recipient_record_id == person.id)
        .values(email="erased@invalid")
    )
    for user in db.scalars(select(User).where(User.contact_id == person.id)):
        user.is_active = False
        user.name = "Erased user"
        user.email = f"erased-{user.id.hex[:12]}@invalid.example"
        user.phone = None
        user.title = None
        revoke_sessions(db, user.id)
    sys._refresh_search(meta, person)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type=f"record:{obj}",
        entity_id=person.id,
        summary=f"Personal data erased ({reason.strip()[:200]})",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    db.flush()
    return person


def apply_retention(db: Session, now: datetime | None = None) -> int:
    """Scheduled job: move records past their object's retention period to the recycle bin.

    Policy: settings["retention"]["object_years"] = {"lead": 2, "case": 7, ...}. Objects without a policy
    are kept. Hooks run as for a normal delete, so legal holds (e.g. matters with ledger entries) stay.
    """
    now = now or datetime.now(UTC)
    policies: dict[str, Any] = (get_setting(db, "retention") or {}).get("object_years") or {}
    svc = RecordService.as_system(db)
    moved = 0
    for obj, years in policies.items():
        if obj not in svc.registry.objects or not isinstance(years, int | float) or years <= 0:
            continue
        cutoff = now - timedelta(days=365.25 * float(years))
        rows = db.scalars(
            select(Record.id)
            .where(Record.object_api_name == obj, Record.is_deleted == false(), Record.updated_at < cutoff)
            .limit(1000)
        ).all()
        for rid in rows:
            try:
                with db.begin_nested():
                    svc.delete(obj, rid)
                moved += 1
            except AppError:
                continue
    db.commit()
    return moved


__all__ = ["apply_retention", "erase_person", "export_person"]
