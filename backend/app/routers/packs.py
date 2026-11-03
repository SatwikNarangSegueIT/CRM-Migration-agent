"""/setup/packs: industry packs (install, upgrade, enable, disable, custom permissions) and pack resources."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import packs
from app.auth.deps import AuthContext, DbSession, require
from app.core.errors import NotFoundError
from app.engine.deps import Records
from app.engine.meta import invalidate_cache
from app.security.catalog import SystemPermission
from app.services.audit import RequestMeta

router = APIRouter(tags=["setup: packs"])
P = SystemPermission
Reader = Annotated[AuthContext, Depends(require(P.VIEW_SETUP, P.MANAGE_INDUSTRY_PACKS))]
Manager = Annotated[AuthContext, Depends(require(P.MANAGE_INDUSTRY_PACKS))]


class PermissionProfilesIn(BaseModel):
    profile_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


def _out(db: DbSession) -> list[dict[str, Any]]:
    installed = packs.installed(db)
    out = []
    for p in packs.available():
        row = installed.get(p.key)
        out.append(
            {
                "key": p.key,
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "region": p.region,
                "installed_version": row.version if row else None,
                "is_enabled": bool(row and row.is_enabled),
                "upgrade_available": bool(row and row.version != p.version),
                "installed_at": row.created_at if row else None,
                "custom_permissions": [
                    {"name": name, "label": label, "profile_ids": packs.permission_profiles(db, p.key, name)}
                    for name, label in p.custom_permissions.items()
                ],
                "contents": {k: len(v) for k, v in p.bundle().items()},
            }
        )
    return out


@router.get("/setup/packs")
def list_packs(db: DbSession, _: Reader) -> list[dict[str, Any]]:
    return _out(db)


@router.post("/setup/packs/{key}/install")
def install(key: str, request: Request, db: DbSession, auth: Manager) -> list[dict[str, Any]]:
    packs.install(db, key, auth.user.id, RequestMeta.from_request(request))
    db.commit()
    invalidate_cache()
    return _out(db)


@router.post("/setup/packs/{key}/enable")
def enable(key: str, request: Request, db: DbSession, auth: Manager) -> list[dict[str, Any]]:
    packs.set_enabled(db, key, True, auth.user.id, RequestMeta.from_request(request))
    db.commit()
    return _out(db)


@router.post("/setup/packs/{key}/disable")
def disable(key: str, request: Request, db: DbSession, auth: Manager) -> list[dict[str, Any]]:
    packs.set_enabled(db, key, False, auth.user.id, RequestMeta.from_request(request))
    db.commit()
    return _out(db)


@router.put("/setup/packs/{key}/permissions/{name}")
def set_permission(
    key: str, name: str, body: PermissionProfilesIn, request: Request, db: DbSession, auth: Manager
) -> list[dict[str, Any]]:
    packs.set_permission_profiles(
        db, key, name, body.profile_ids, auth.user.id, RequestMeta.from_request(request)
    )
    db.commit()
    return _out(db)


@router.get("/packs/migration_agency/statement/{client_id}")
def client_statement(client_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    if "migration_agency" not in svc.enabled_packs:
        raise NotFoundError("Not found.")
    from app.packs.migration_agency import statement

    return statement(svc, client_id)
