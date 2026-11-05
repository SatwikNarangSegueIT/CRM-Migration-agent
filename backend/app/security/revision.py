"""Automatic security-revision bump.

Any change to profiles, permissions, roles, groups, queues or sharing configuration - or to a user's profile,
role or active flag - increments ``metadata_revision.security`` in the same transaction, so cached
permissions and sharing contexts (app.core.cache) are rebuilt by every process. Covers ORM unit-of-work
changes and ORM bulk UPDATE/DELETE statements.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import ORMExecuteState, Session, UOWTransaction

from app.core.cache import clear_pending, forget_revisions, mark_pending
from app.models import (
    Group,
    GroupMember,
    Profile,
    ProfileFieldPermission,
    ProfileObjectPermission,
    ProfileSystemPermission,
    Queue,
    QueueMember,
    Role,
    SharingDefault,
    SharingRule,
    User,
)

SECURITY_MODELS: tuple[type[Any], ...] = (
    Profile,
    ProfileSystemPermission,
    ProfileObjectPermission,
    ProfileFieldPermission,
    Role,
    Group,
    GroupMember,
    Queue,
    QueueMember,
    SharingDefault,
    SharingRule,
)
# User attributes that change what the user may access.
USER_ACCESS_FIELDS = ("profile_id", "role_id", "is_active", "contact_id")
_FLAG = "security_changed"


def _user_access_changed(user: User) -> bool:
    state = inspect(user)
    return any(state.attrs[f].history.has_changes() for f in USER_ACCESS_FIELDS if f in state.attrs)


@event.listens_for(Session, "before_flush")
def _detect_changes(session: Session, _flush: UOWTransaction, _instances: Any) -> None:
    if session.info.get(_FLAG):
        return
    for obj in (*session.new, *session.dirty, *session.deleted):
        is_user_change = isinstance(obj, User) and (
            obj in session.new or obj in session.deleted or _user_access_changed(obj)
        )
        if isinstance(obj, SECURITY_MODELS) or is_user_change:
            session.info[_FLAG] = True
            mark_pending(session)
            return


@event.listens_for(Session, "do_orm_execute")
def _detect_bulk(state: ORMExecuteState) -> None:
    if not (state.is_update or state.is_delete) or state.bind_mapper is None:
        return
    cls = state.bind_mapper.class_
    if issubclass(cls, SECURITY_MODELS) or issubclass(cls, User):
        state.session.info[_FLAG] = True
        mark_pending(state.session)


@event.listens_for(Session, "before_commit")
def _bump(session: Session) -> None:
    session.flush()  # may itself detect security changes
    if not session.info.pop(_FLAG, False):
        return
    row = (
        session.connection()
        .execute(
            text(
                "INSERT INTO metadata_revision (id, revision, security) VALUES (1, 1, 2) "
                "ON CONFLICT (id) DO UPDATE SET security = metadata_revision.security + 1 "
                "RETURNING revision, security"
            )
        )
        .first()
    )
    if row is not None:
        mark_pending(session, metadata=int(row[0]), security=int(row[1]))


@event.listens_for(Session, "after_commit")
def _committed(session: Session) -> None:
    # This session's changes are committed, so caching is safe again. Forget the revisions it knew: other
    # sessions may have committed changes too, and a long-lived session (a job, a script) must see them.
    clear_pending(session)
    forget_revisions(session)


@event.listens_for(Session, "after_rollback")
def _rolled_back(session: Session) -> None:
    session.info.pop(_FLAG, None)
    forget_revisions(session)
