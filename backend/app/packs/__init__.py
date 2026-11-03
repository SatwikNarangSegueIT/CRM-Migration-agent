"""Industry packs (plan v3, section 11): versioned bundles of objects, fields, apps, profiles, reports
and server-side rules, installed through the same metadata engine as admin customisations.

A pack provides:
  bundle()           objects / fields / apps / list views (installer format)
  install(conn)      extra data: profiles, permissions, field security, reports, settings (idempotent)
  hooks module       object hooks and actions, registered with pack_key so they only run while enabled
  custom permissions "pack:<key>:<name>" granted to profiles like system permissions
  daily_job(db)      optional scheduled work (e.g. expiry reminders)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, delete, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.engine.installer import install_bundle
from app.engine.meta import bump_revision
from app.models import PackInstallation, ProfileSystemPermission
from app.services import audit
from app.services.audit import AuditAction, RequestMeta


@dataclass(frozen=True)
class Pack:
    key: str
    name: str
    version: str
    description: str
    bundle: Callable[[], dict[str, Any]]
    install: Callable[[Connection], None]
    custom_permissions: dict[str, str] = field(default_factory=dict)  # name -> label
    daily_job: Callable[[Session], int] | None = None
    region: str = ""


_PACKS: dict[str, Pack] = {}


def register(pack: Pack) -> Pack:
    _PACKS[pack.key] = pack
    return pack


def available() -> list[Pack]:
    _load()
    return sorted(_PACKS.values(), key=lambda p: p.name)


def get(key: str) -> Pack:
    _load()
    pack = _PACKS.get(key)
    if pack is None:
        raise NotFoundError("Pack not found.")
    return pack


def _load() -> None:
    from app.packs import migration_agency  # noqa: F401 - registers the pack and its hooks


def permission_key(pack_key: str, name: str) -> str:
    return f"pack:{pack_key}:{name}"


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def install(
    db: Session, key: str, actor_id: uuid.UUID | None, meta: RequestMeta | None = None
) -> PackInstallation:
    """Install or upgrade (re-applying a newer bundle only adds what is missing)."""
    pack = get(key)
    row = db.scalar(select(PackInstallation).where(PackInstallation.pack_key == key))
    if row is not None and _version_tuple(row.version) > _version_tuple(pack.version):
        raise AppError("A newer version of this pack is already installed.", status_code=409, code="conflict")
    conn = db.connection()
    install_bundle(conn, pack.bundle(), pack_key=pack.key)
    pack.install(conn)
    action = AuditAction.CREATE
    if row is None:
        row = PackInstallation(pack_key=key, version=pack.version, is_enabled=True, installed_by_id=actor_id)
        db.add(row)
    else:
        action = AuditAction.UPDATE
        row.version = pack.version
        row.is_enabled = True
    bump_revision(db)
    db.flush()
    audit.record(
        db,
        action=action,
        entity_type="pack",
        entity_id=key,
        summary=f"{'Installed' if action is AuditAction.CREATE else 'Upgraded'} industry pack "
        f"{pack.name} {pack.version}",
        actor_id=actor_id,
        meta=meta,
    )
    return row


def set_enabled(
    db: Session, key: str, enabled: bool, actor_id: uuid.UUID | None, meta: RequestMeta | None = None
) -> PackInstallation:
    get(key)
    row = db.scalar(select(PackInstallation).where(PackInstallation.pack_key == key))
    if row is None:
        raise NotFoundError("The pack isn't installed.")
    row.is_enabled = enabled
    bump_revision(db)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="pack",
        entity_id=key,
        summary=f"{'Enabled' if enabled else 'Disabled'} industry pack {key}",
        actor_id=actor_id,
        changes={"is_enabled": {"from": not enabled, "to": enabled}},
        meta=meta,
    )
    db.flush()
    return row


def set_permission_profiles(
    db: Session,
    key: str,
    name: str,
    profile_ids: list[uuid.UUID],
    actor_id: uuid.UUID | None,
    meta: RequestMeta | None = None,
) -> None:
    pack = get(key)
    if name not in pack.custom_permissions:
        raise NotFoundError("Permission not found.")
    perm = permission_key(key, name)
    db.execute(delete(ProfileSystemPermission).where(ProfileSystemPermission.permission == perm))
    for pid in profile_ids:
        db.add(ProfileSystemPermission(profile_id=pid, permission=perm))
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="pack_permission",
        entity_id=perm,
        summary=f"Changed profiles with {pack.custom_permissions[name]}",
        actor_id=actor_id,
        changes={"profile_ids": {"from": None, "to": [str(p) for p in profile_ids]}},
        meta=meta,
    )
    db.flush()


def permission_profiles(db: Session, key: str, name: str) -> list[str]:
    perm = permission_key(key, name)
    return [
        str(p)
        for p in db.scalars(
            select(ProfileSystemPermission.profile_id).where(ProfileSystemPermission.permission == perm)
        )
    ]


def grant(conn: Connection, profile_id: uuid.UUID, permission: str) -> None:
    conn.execute(
        text(
            "INSERT INTO profile_system_permissions (profile_id, permission) VALUES (:p, :perm) "
            "ON CONFLICT DO NOTHING"
        ),
        {"p": profile_id, "perm": permission},
    )


def run_daily_jobs(db: Session) -> int:
    count = 0
    enabled = set(db.scalars(select(PackInstallation.pack_key).where(PackInstallation.is_enabled)))
    for pack in available():
        if pack.key in enabled and pack.daily_job is not None:
            count += pack.daily_job(db)
    db.commit()
    return count


def installed(db: Session) -> dict[str, PackInstallation]:
    return {r.pack_key: r for r in db.scalars(select(PackInstallation))}


def utcnow() -> datetime:
    return datetime.now(UTC)
