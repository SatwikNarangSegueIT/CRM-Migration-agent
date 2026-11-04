"""Record sharing (plan v3, section 9, layer 4): SQL predicates for "can read" / "can edit".

Every list, record read, related list, report, search and export applies `readable()`; every write
checks `editable()`. Predicates are built from validated metadata only and bind all values.

Read access is granted by any of: View All on the object; an organisation-wide default of Public
Read Only / Read-Write; ownership; the role hierarchy (managers see their subordinates' records);
queue membership (queue-owned records); manual shares; owner- or criteria-based sharing rules; and,
for detail objects, access to the master record. Portal users see only records tied to their own
contact or account.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ColumnElement,
    and_,
    exists,
    false,
    literal,
    or_,
    select,
    true,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import False_

from app.core.cache import new_cache, revisions, tenant_of
from app.models import (
    GroupMember,
    QueueMember,
    Record,
    RecordLink,
    RecordShare,
    Role,
    SharingDefault,
    SharingRule,
    User,
)
from app.security.catalog import SharingAccess
from app.security.policy import AccessPolicy

if TYPE_CHECKING:
    from app.engine.meta import ObjectMeta, Registry

RecordAlias = Any  # Record or an aliased(Record)
_CRITERIA_OPS = {"eq": "equals", "ne": "not_equals"}


def criteria_to_filter(criteria: dict[str, Any]) -> dict[str, Any]:
    """Sharing-rule criteria (eq/ne/...) -> record-engine filter AST."""
    return {
        "logic": criteria.get("logic", "and"),
        "conditions": [
            {**c, "op": _CRITERIA_OPS.get(str(c.get("op")), c.get("op"))}
            for c in criteria.get("conditions", [])
        ],
    }


MAX_PARENT_DEPTH = 3


@dataclass
class SharingContext:
    """Per-request facts about the current user needed to build sharing predicates."""

    policy: AccessPolicy
    registry: Registry
    defaults: dict[str, SharingDefault]
    rules: dict[str, list[SharingRule]]
    group_ids: frozenset[uuid.UUID]
    queue_ids: frozenset[uuid.UUID]
    ancestor_role_ids: frozenset[uuid.UUID]  # own role and every role above it
    contact_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    _cache: dict[tuple[str, str, int], ColumnElement[bool] | None] = field(default_factory=dict)

    @property
    def user_id(self) -> uuid.UUID:
        return self.policy.user_id

    # ------------------------------------------------------------------ helpers

    def owd(self, obj: str) -> str:
        row = self.defaults.get(obj)
        if row is not None:
            return row.access
        meta = self.registry.objects.get(obj)
        if meta is not None and meta.master_field is not None:
            return SharingAccess.CONTROLLED_BY_PARENT.value
        return SharingAccess.PRIVATE.value

    def uses_hierarchy(self, obj: str) -> bool:
        row = self.defaults.get(obj)
        return row.grant_access_using_hierarchy if row is not None else True

    def _subordinate_owner_ids(self) -> Any:
        """Users strictly below the current user's role in the hierarchy."""
        if not self.policy.role_path or self.policy.role_id is None:
            return None
        return (
            select(User.id)
            .join(Role, Role.id == User.role_id)
            .where(Role.path.like(self.policy.role_path + "%"), Role.id != self.policy.role_id)
        )

    def _share_principal_match(self, share: Any) -> ColumnElement[bool]:
        clauses: list[ColumnElement[bool]] = [
            and_(share.principal_type == "user", share.principal_id == self.user_id)
        ]
        if self.group_ids:
            clauses.append(and_(share.principal_type == "group", share.principal_id.in_(self.group_ids)))
        if self.policy.role_id is not None:
            clauses.append(and_(share.principal_type == "role", share.principal_id == self.policy.role_id))
        if self.ancestor_role_ids:
            clauses.append(
                and_(
                    share.principal_type == "role_and_subordinates",
                    share.principal_id.in_(self.ancestor_role_ids),
                )
            )
        return or_(*clauses)

    def _in_target(self, rule: SharingRule) -> bool:
        if rule.target_type == "role":
            return self.policy.role_id == rule.target_id
        if rule.target_type == "role_and_subordinates":
            return rule.target_id in self.ancestor_role_ids
        return rule.target_id in self.group_ids

    def _source_owner_ids(self, rule: SharingRule) -> Any:
        if rule.source_type == "role":
            return select(User.id).where(User.role_id == rule.source_id)
        if rule.source_type == "role_and_subordinates":
            src = aliased(Role)
            member_role = aliased(Role)
            return (
                select(User.id)
                .join(member_role, member_role.id == User.role_id)
                .join(src, src.id == rule.source_id)
                .where(member_role.path.like(src.path + "%"))
            )
        if rule.source_type == "group":
            gm = aliased(GroupMember)
            member_role = aliased(Role)
            gm_role = aliased(Role)
            direct = select(gm.user_id).where(gm.group_id == rule.source_id, gm.user_id.is_not(None))
            via_role = (
                select(User.id)
                .join(member_role, member_role.id == User.role_id)
                .join(gm, gm.group_id == rule.source_id)
                .join(gm_role, gm_role.id == gm.role_id)
                .where(
                    or_(
                        member_role.id == gm.role_id,
                        and_(gm.include_subordinates, member_role.path.like(gm_role.path + "%")),
                    )
                )
            )
            return direct.union(via_role)
        return None

    # ------------------------------------------------------------------ predicates

    def _private_access(self, obj: str, r: RecordAlias, *, edit: bool, depth: int) -> ColumnElement[bool]:
        clauses: list[ColumnElement[bool]] = [r.owner_id == self.user_id]
        subordinates = self._subordinate_owner_ids()
        if subordinates is not None and self.uses_hierarchy(obj):
            clauses.append(r.owner_id.in_(subordinates))
        if self.queue_ids:
            clauses.append(r.queue_id.in_(self.queue_ids))
        share = aliased(RecordShare)
        share_conditions = [share.record_id == r.id, self._share_principal_match(share)]
        if edit:
            share_conditions.append(share.access == "read_write")
        clauses.append(exists().where(*share_conditions))
        for rule in self.rules.get(obj, []):
            if edit and rule.access != "read_write":
                continue
            if not self._in_target(rule):
                continue
            if rule.rule_type == "owner":
                if rule.source_type == "queue":
                    clauses.append(r.queue_id == rule.source_id)
                else:
                    owners = self._source_owner_ids(rule)
                    if owners is not None:
                        clauses.append(r.owner_id.in_(owners))
            elif rule.criteria:
                from app.engine.filters import compile_filter

                meta = self.registry.get(obj)
                clauses.append(compile_filter(meta, criteria_to_filter(rule.criteria), r, ctx=None))
        return or_(*clauses)

    def _parent_access(
        self, obj: ObjectMeta, r: RecordAlias, *, edit: bool, depth: int
    ) -> ColumnElement[bool]:
        """Detail records follow their master; activities follow the record they relate to."""
        parent_field = obj.master_field
        if parent_field is None:
            parent_field = obj.fields.get("related_to")
        if parent_field is None or depth >= MAX_PARENT_DEPTH:
            return self._private_access(obj.api_name, r, edit=edit, depth=depth)
        options: list[ColumnElement[bool]] = []
        for target in parent_field.targets:
            parent = aliased(Record)
            link = aliased(RecordLink)
            pred = self._predicate(target, parent, edit=edit, depth=depth + 1)
            if isinstance(pred, False_):
                continue
            conditions: list[ColumnElement[bool]] = [
                link.from_record_id == r.id,
                link.field_api_name == parent_field.api_name,
                parent.object_api_name == target,
            ]
            if pred is not None:
                conditions.append(pred)
            joined = select(literal(1)).select_from(link).join(parent, parent.id == link.to_record_id)
            options.append(exists(joined.where(*conditions)))
        # Records without a parent (e.g. a personal task) fall back to ownership.
        options.append(self._private_access(obj.api_name, r, edit=edit, depth=depth))
        return or_(*options)

    def _portal(self, obj: ObjectMeta, r: RecordAlias, *, depth: int) -> ColumnElement[bool]:
        ids = [i for i in (self.contact_id, self.account_id) if i is not None]
        if obj.api_name == "contact":
            return r.id == self.contact_id if self.contact_id else false()
        if obj.api_name == "account":
            return r.id == self.account_id if self.account_id else false()
        clauses: list[ColumnElement[bool]] = [r.created_by_id == self.user_id]
        for fname in obj.portal_fields:
            if ids:
                clauses.append(r.data[fname].astext.in_([str(i) for i in ids]))
        parent_field = obj.master_field or obj.fields.get("related_to")
        if parent_field is not None and depth < MAX_PARENT_DEPTH:
            for target in parent_field.targets:
                if target not in self.registry.objects or not self.policy.object(target).read:
                    continue
                parent = aliased(Record)
                link = aliased(RecordLink)
                parent_pred = self._portal(self.registry.get(target), parent, depth=depth + 1)
                visible_to_portal: ColumnElement[bool] = true()
                if "is_public" in obj.fields:
                    visible_to_portal = r.data["is_public"].astext == "true"
                clauses.append(
                    and_(
                        visible_to_portal,
                        exists(
                            select(literal(1))
                            .select_from(link)
                            .join(parent, parent.id == link.to_record_id)
                            .where(
                                link.from_record_id == r.id,
                                link.field_api_name == parent_field.api_name,
                                parent.object_api_name == target,
                                parent.is_deleted == false(),
                                parent_pred,
                            )
                        ),
                    )
                )
        return or_(*clauses)

    def _predicate(
        self, obj: str, r: RecordAlias, *, edit: bool, depth: int = 0
    ) -> ColumnElement[bool] | None:
        access = self.policy.object(obj)
        if not access.read or (edit and not access.edit):
            return false()
        meta = self.registry.objects.get(obj)
        if meta is None:
            return false()
        if self.policy.is_portal:
            return self._portal(meta, r, depth=depth)
        if access.modify_all or (access.view_all and not edit):
            return None
        owd = self.owd(obj)
        if owd == SharingAccess.READ_WRITE.value or (owd == SharingAccess.READ.value and not edit):
            return None
        if owd == SharingAccess.CONTROLLED_BY_PARENT.value:
            return self._parent_access(meta, r, edit=edit, depth=depth)
        return self._private_access(obj, r, edit=edit, depth=depth)

    def readable(self, obj: str, r: RecordAlias = Record) -> ColumnElement[bool] | None:
        """None = every record of the object is readable."""
        return self._predicate(obj, r, edit=False)

    def editable(self, obj: str, r: RecordAlias = Record) -> ColumnElement[bool] | None:
        return self._predicate(obj, r, edit=True)

    def where_readable(self, obj: str, r: RecordAlias = Record) -> ColumnElement[bool]:
        pred = self.readable(obj, r)
        return pred if pred is not None else true()

    def where_editable(self, obj: str, r: RecordAlias = Record) -> ColumnElement[bool]:
        pred = self.editable(obj, r)
        return pred if pred is not None else true()

    def can(self, db: Session, record: Record, *, edit: bool) -> bool:
        pred = self.editable(record.object_api_name) if edit else self.readable(record.object_api_name)
        if pred is None:
            return True
        return bool(db.scalar(select(literal(True)).where(Record.id == record.id, pred)))


_org_cache = new_cache(256)
_user_cache = new_cache(4096)


def _detached(obj: Any) -> Any:
    """A transient copy holding only column values, safe to share across sessions and threads."""
    mapper = sa_inspect(type(obj))
    return type(obj)(**{attr.key: getattr(obj, attr.key) for attr in mapper.column_attrs})


def _org_sharing(db: Session) -> tuple[dict[str, SharingDefault], dict[str, list[SharingRule]]]:
    defaults = {d.object_api_name: _detached(d) for d in db.scalars(select(SharingDefault))}
    rules: dict[str, list[SharingRule]] = {}
    for rule in db.scalars(select(SharingRule)):
        rules.setdefault(rule.object_api_name, []).append(_detached(rule))
    return defaults, rules


def _user_memberships(
    db: Session, policy: AccessPolicy, ancestors: frozenset[uuid.UUID]
) -> tuple[frozenset[uuid.UUID], frozenset[uuid.UUID]]:
    group_ids: set[uuid.UUID] = set()
    group_ids.update(
        db.scalars(select(GroupMember.group_id).where(GroupMember.user_id == policy.user_id)).all()
    )
    if policy.role_id is not None:
        group_ids.update(
            db.scalars(
                select(GroupMember.group_id).where(
                    or_(
                        GroupMember.role_id == policy.role_id,
                        and_(GroupMember.include_subordinates, GroupMember.role_id.in_(ancestors)),
                    )
                )
            ).all()
        )
    queue_ids = frozenset(
        db.scalars(select(QueueMember.queue_id).where(QueueMember.user_id == policy.user_id)).all()
    )
    return frozenset(group_ids), queue_ids


def build_sharing_context(db: Session, policy: AccessPolicy, registry: Registry) -> SharingContext:
    # Cached per security revision (app.core.cache): sharing settings per tenant, memberships per user.
    tenant, security = tenant_of(db), revisions(db).security
    defaults, rules = _org_cache.get_or_build(db, (tenant, "org", security), lambda: _org_sharing(db))
    ancestors: frozenset[uuid.UUID] = frozenset()
    if policy.role_path:
        ancestors = frozenset(uuid.UUID(p) for p in policy.role_path.strip("/").split("/") if p)
    group_ids, queue_ids = _user_cache.get_or_build(
        db,
        (tenant, "user", policy.user_id, policy.role_id, security),
        lambda: _user_memberships(db, policy, ancestors),
    )
    contact_id = account_id = None
    if policy.is_portal:
        user = db.get(User, policy.user_id)
        contact_id = user.contact_id if user else None
        if contact_id is not None:
            contact = db.get(Record, contact_id)
            if contact is not None and contact.data.get("account"):
                account_id = uuid.UUID(str(contact.data["account"]))
    return SharingContext(
        policy=policy,
        registry=registry,
        defaults=defaults,
        rules=rules,
        group_ids=group_ids,
        queue_ids=queue_ids,
        ancestor_role_ids=ancestors,
        contact_id=contact_id,
        account_id=account_id,
    )
