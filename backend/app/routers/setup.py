"""/setup: security configuration (plan v3, section 9).

Read access: View Setup or Manage Profiles & Sharing (profiles and roles are also readable with
Manage Users, which needs them to assign users). Changes: Manage Profiles & Sharing.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.auth.deps import AuthContext, DbSession, require
from app.models import Group, Profile, Queue, SharingRule
from app.schemas.setup import (
    CatalogItem,
    CatalogOut,
    FieldPermissionOut,
    FieldPermissionsIn,
    GroupIn,
    GroupMembersIn,
    GroupOut,
    GroupRoleMember,
    ObjectPermissionOut,
    ObjectPermissionsIn,
    ProfileCreate,
    ProfileDetail,
    ProfileSummary,
    ProfileUpdate,
    QueueIn,
    QueueMembersIn,
    QueueOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    SharingDefaultIn,
    SharingDefaultOut,
    SharingRuleIn,
    SharingRuleOut,
    StandardObjectOut,
    SystemPermissionsIn,
)
from app.security.catalog import (
    STANDARD_OBJECTS,
    SYSTEM_PERMISSION_LABELS,
    FieldAccess,
    SharingAccess,
    SystemPermission,
)
from app.services import setup_security as svc
from app.services.audit import RequestMeta

router = APIRouter(prefix="/setup", tags=["setup: security"])

P = SystemPermission
Reader = Annotated[AuthContext, Depends(require(P.VIEW_SETUP, P.MANAGE_PROFILES_SHARING))]
AssignmentReader = Annotated[
    AuthContext, Depends(require(P.VIEW_SETUP, P.MANAGE_PROFILES_SHARING, P.MANAGE_USERS))
]
Manager = Annotated[AuthContext, Depends(require(P.MANAGE_PROFILES_SHARING))]


def _meta(request: Request) -> RequestMeta:
    return RequestMeta.from_request(request)


# ---------------------------------------------------------------- catalog


@router.get("/catalog", response_model=CatalogOut)
def catalog(_: AssignmentReader) -> CatalogOut:
    return CatalogOut(
        system_permissions=[
            CatalogItem(value=p.value, label=SYSTEM_PERMISSION_LABELS[p]) for p in SystemPermission
        ],
        objects=[
            StandardObjectOut(
                api_name=o.api_name, label=o.label, plural=o.plural, app=o.app, default_sharing=o.sharing
            )
            for o in STANDARD_OBJECTS
        ],
        sharing_access=[a.value for a in SharingAccess],
        field_access=[a.value for a in FieldAccess],
    )


# ---------------------------------------------------------------- profiles


def _summary(profile: Profile, counts: dict[uuid.UUID, int]) -> ProfileSummary:
    out = ProfileSummary.model_validate(profile)
    out.user_count = counts.get(profile.id, 0)
    return out


def _detail(db: DbSession, profile: Profile) -> ProfileDetail:
    counts = svc.user_counts_by_profile(db)
    base = _summary(profile, counts)
    if profile.is_locked:
        system = list(SystemPermission)
        objects = [
            ObjectPermissionOut(
                object_api_name=o.api_name,
                read=True,
                create=True,
                edit=True,
                delete=True,
                view_all=True,
                modify_all=True,
            )
            for o in STANDARD_OBJECTS
        ]
    else:
        system = sorted(SystemPermission(sp.permission) for sp in profile.system_permissions)
        objects = sorted(
            (
                ObjectPermissionOut(
                    object_api_name=op.object_api_name,
                    read=op.can_read,
                    create=op.can_create,
                    edit=op.can_edit,
                    delete=op.can_delete,
                    view_all=op.view_all,
                    modify_all=op.modify_all,
                )
                for op in profile.object_permissions
            ),
            key=lambda o: o.object_api_name,
        )
    fields = sorted(
        (
            FieldPermissionOut(
                object_api_name=f.object_api_name,
                field_api_name=f.field_api_name,
                access=FieldAccess(f.access),
            )
            for f in profile.field_permissions
        ),
        key=lambda f: (f.object_api_name, f.field_api_name),
    )
    return ProfileDetail(
        **base.model_dump(), system_permissions=system, object_permissions=objects, field_permissions=fields
    )


@router.get("/profiles", response_model=list[ProfileSummary])
def list_profiles(db: DbSession, _: AssignmentReader) -> list[ProfileSummary]:
    counts = svc.user_counts_by_profile(db)
    return [_summary(p, counts) for p in svc.list_profiles(db)]


@router.post("/profiles", response_model=ProfileDetail, status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, request: Request, db: DbSession, auth: Manager) -> ProfileDetail:
    return _detail(db, svc.create_profile(db, auth, body, _meta(request)))


@router.get("/profiles/{profile_id}", response_model=ProfileDetail)
def get_profile(profile_id: uuid.UUID, db: DbSession, _: Reader) -> ProfileDetail:
    return _detail(db, svc.get_profile(db, profile_id))


@router.patch("/profiles/{profile_id}", response_model=ProfileDetail)
def update_profile(
    profile_id: uuid.UUID, body: ProfileUpdate, request: Request, db: DbSession, auth: Manager
) -> ProfileDetail:
    return _detail(db, svc.update_profile(db, auth, profile_id, body, _meta(request)))


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: uuid.UUID, request: Request, db: DbSession, auth: Manager) -> Response:
    svc.delete_profile(db, auth, profile_id, _meta(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/profiles/{profile_id}/system-permissions", response_model=ProfileDetail)
def set_system_permissions(
    profile_id: uuid.UUID, body: SystemPermissionsIn, request: Request, db: DbSession, auth: Manager
) -> ProfileDetail:
    return _detail(db, svc.set_system_permissions(db, auth, profile_id, body.permissions, _meta(request)))


@router.put("/profiles/{profile_id}/object-permissions", response_model=ProfileDetail)
def set_object_permissions(
    profile_id: uuid.UUID, body: ObjectPermissionsIn, request: Request, db: DbSession, auth: Manager
) -> ProfileDetail:
    return _detail(db, svc.set_object_permissions(db, auth, profile_id, body, _meta(request)))


@router.put("/profiles/{profile_id}/field-permissions", response_model=ProfileDetail)
def set_field_permissions(
    profile_id: uuid.UUID, body: FieldPermissionsIn, request: Request, db: DbSession, auth: Manager
) -> ProfileDetail:
    return _detail(db, svc.set_field_permissions(db, auth, profile_id, body, _meta(request)))


# ---------------------------------------------------------------- roles


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DbSession, _: AssignmentReader) -> list[RoleOut]:
    return [
        RoleOut(
            id=r.id,
            key=r.key,
            name=r.name,
            description=r.description,
            parent_id=r.parent_id,
            depth=svc.role_depth(r),
            user_count=n,
        )
        for r, n in svc.list_roles(db)
    ]


def _role_out(db: DbSession, role_id: uuid.UUID) -> RoleOut:
    for r, n in svc.list_roles(db):
        if r.id == role_id:
            return RoleOut(
                id=r.id,
                key=r.key,
                name=r.name,
                description=r.description,
                parent_id=r.parent_id,
                depth=svc.role_depth(r),
                user_count=n,
            )
    raise AssertionError("role vanished")


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleCreate, request: Request, db: DbSession, auth: Manager) -> RoleOut:
    return _role_out(db, svc.create_role(db, auth, body, _meta(request)).id)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID, body: RoleUpdate, request: Request, db: DbSession, auth: Manager
) -> RoleOut:
    return _role_out(db, svc.update_role(db, auth, role_id, body, _meta(request)).id)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: uuid.UUID, request: Request, db: DbSession, auth: Manager) -> Response:
    svc.delete_role(db, auth, role_id, _meta(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- sharing defaults


@router.get("/sharing-defaults", response_model=list[SharingDefaultOut])
def sharing_defaults(db: DbSession, _: Reader) -> list[SharingDefaultOut]:
    return [
        SharingDefaultOut(
            object_api_name=sd.object_api_name,
            access=SharingAccess(sd.access),
            grant_access_using_hierarchy=sd.grant_access_using_hierarchy,
        )
        for sd in svc.list_sharing_defaults(db)
    ]


@router.put("/sharing-defaults/{object_api_name}", response_model=SharingDefaultOut)
def set_sharing_default(
    object_api_name: str, body: SharingDefaultIn, request: Request, db: DbSession, auth: Manager
) -> SharingDefaultOut:
    sd = svc.set_sharing_default(db, auth, object_api_name, body, _meta(request))
    return SharingDefaultOut(
        object_api_name=sd.object_api_name,
        access=SharingAccess(sd.access),
        grant_access_using_hierarchy=sd.grant_access_using_hierarchy,
    )


# ---------------------------------------------------------------- groups


def _group_out(group: Group) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        user_ids=[m.user_id for m in group.members if m.user_id is not None],
        roles=[
            GroupRoleMember(role_id=m.role_id, include_subordinates=m.include_subordinates)
            for m in group.members
            if m.role_id is not None
        ],
    )


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: DbSession, _: Reader) -> list[GroupOut]:
    return [_group_out(g) for g in svc.list_groups(db)]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupIn, request: Request, db: DbSession, auth: Manager) -> GroupOut:
    return _group_out(svc.save_group(db, auth, body, _meta(request)))


@router.put("/groups/{group_id}", response_model=GroupOut)
def update_group(
    group_id: uuid.UUID, body: GroupIn, request: Request, db: DbSession, auth: Manager
) -> GroupOut:
    return _group_out(svc.save_group(db, auth, body, _meta(request), group_id))


@router.put("/groups/{group_id}/members", response_model=GroupOut)
def set_group_members(
    group_id: uuid.UUID, body: GroupMembersIn, request: Request, db: DbSession, auth: Manager
) -> GroupOut:
    return _group_out(svc.set_group_members(db, auth, group_id, body, _meta(request)))


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: uuid.UUID, request: Request, db: DbSession, auth: Manager) -> Response:
    svc.delete_group(db, auth, group_id, _meta(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- queues


def _queue_out(queue: Queue) -> QueueOut:
    return QueueOut(
        id=queue.id,
        name=queue.name,
        email=queue.email,
        object_api_names=list(queue.object_api_names),
        user_ids=[m.user_id for m in queue.members],
    )


@router.get("/queues", response_model=list[QueueOut])
def list_queues(db: DbSession, _: Reader) -> list[QueueOut]:
    return [_queue_out(q) for q in svc.list_queues(db)]


@router.post("/queues", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
def create_queue(body: QueueIn, request: Request, db: DbSession, auth: Manager) -> QueueOut:
    return _queue_out(svc.save_queue(db, auth, body, _meta(request)))


@router.put("/queues/{queue_id}", response_model=QueueOut)
def update_queue(
    queue_id: uuid.UUID, body: QueueIn, request: Request, db: DbSession, auth: Manager
) -> QueueOut:
    return _queue_out(svc.save_queue(db, auth, body, _meta(request), queue_id))


@router.put("/queues/{queue_id}/members", response_model=QueueOut)
def set_queue_members(
    queue_id: uuid.UUID, body: QueueMembersIn, request: Request, db: DbSession, auth: Manager
) -> QueueOut:
    return _queue_out(svc.set_queue_members(db, auth, queue_id, body, _meta(request)))


@router.delete("/queues/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_queue(queue_id: uuid.UUID, request: Request, db: DbSession, auth: Manager) -> Response:
    svc.delete_queue(db, auth, queue_id, _meta(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- sharing rules


def _rule_out(rule: SharingRule) -> SharingRuleOut:
    return SharingRuleOut.model_validate(
        {
            "id": rule.id,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
            "object_api_name": rule.object_api_name,
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "source_type": rule.source_type,
            "source_id": rule.source_id,
            "criteria": rule.criteria,
            "target_type": rule.target_type,
            "target_id": rule.target_id,
            "access": rule.access,
        }
    )


@router.get("/sharing-rules", response_model=list[SharingRuleOut])
def list_sharing_rules(
    db: DbSession, _: Reader, object_api_name: Annotated[str | None, Query(max_length=80)] = None
) -> list[SharingRuleOut]:
    return [_rule_out(r) for r in svc.list_sharing_rules(db, object_api_name)]


@router.post("/sharing-rules", response_model=SharingRuleOut, status_code=status.HTTP_201_CREATED)
def create_sharing_rule(
    body: SharingRuleIn, request: Request, db: DbSession, auth: Manager
) -> SharingRuleOut:
    return _rule_out(svc.save_sharing_rule(db, auth, body, _meta(request)))


@router.put("/sharing-rules/{rule_id}", response_model=SharingRuleOut)
def update_sharing_rule(
    rule_id: uuid.UUID, body: SharingRuleIn, request: Request, db: DbSession, auth: Manager
) -> SharingRuleOut:
    return _rule_out(svc.save_sharing_rule(db, auth, body, _meta(request), rule_id))


@router.delete("/sharing-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sharing_rule(rule_id: uuid.UUID, request: Request, db: DbSession, auth: Manager) -> Response:
    svc.delete_sharing_rule(db, auth, rule_id, _meta(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
