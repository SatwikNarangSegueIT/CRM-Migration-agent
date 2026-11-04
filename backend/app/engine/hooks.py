"""Object hooks and custom actions (plan v3, section 3: "Business logic").

Standard objects and industry packs register Python hooks that run inside the same transaction as the
write. `before_*` hooks may change `change.data` (the values about to be stored) or raise an AppError;
`after_*` hooks see the saved record and may write other records through `change.svc`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.engine.records import RecordService
    from app.models import Record


class Event(StrEnum):
    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"
    BEFORE_UPDATE = "before_update"
    AFTER_UPDATE = "after_update"
    BEFORE_DELETE = "before_delete"
    AFTER_DELETE = "after_delete"


@dataclass
class Change:
    svc: RecordService
    object_api_name: str
    record: Record | None
    # Values about to be stored (before_*) / stored (after_*).
    data: dict[str, Any]
    # Values before the change (updates and deletes).
    old: dict[str, Any] = field(default_factory=dict)
    # Names of fields the caller changed (updates); every supplied field on create.
    changed: set[str] = field(default_factory=set)
    # System columns the hook may set on create/update.
    system: dict[str, Any] = field(default_factory=dict)

    def is_changed(self, name: str) -> bool:
        return name in self.changed

    def value(self, name: str) -> Any:
        return self.data.get(name)


Hook = Callable[[Change], None]


@dataclass(frozen=True)
class Action:
    object_api_name: str
    name: str
    label: str
    handler: Callable[[RecordService, Record, dict[str, Any]], dict[str, Any]]
    # The user must be able to edit the record (most actions change it).
    requires_edit: bool = True
    # Optional extra check, e.g. a pack's custom permission. Returns an error message or None.
    guard: Callable[[RecordService, Record], str | None] | None = None
    # Shown on the record page when this returns True (UI hint only; the handler re-checks).
    visible: Callable[[Record], bool] | None = None
    pack_key: str | None = None
    # Customer-portal users may run it on records they can see (e.g. signing an agreement).
    portal: bool = False
    # Only the client may run it (an e-signature): staff never see or run it.
    client_only: bool = False


_hooks: dict[tuple[str, Event], list[tuple[str | None, Hook]]] = {}
_actions: dict[tuple[str, str], Action] = {}


def on(object_api_name: str, *events: Event, pack_key: str | None = None) -> Callable[[Hook], Hook]:
    def decorator(fn: Hook) -> Hook:
        for event in events:
            _hooks.setdefault((object_api_name, event), []).append((pack_key, fn))
        return fn

    return decorator


def action(
    object_api_name: str,
    name: str,
    label: str,
    *,
    requires_edit: bool = True,
    guard: Callable[[RecordService, Record], str | None] | None = None,
    visible: Callable[[Record], bool] | None = None,
    pack_key: str | None = None,
    portal: bool = False,
    client_only: bool = False,
) -> Callable[[Callable[[RecordService, Record, dict[str, Any]], dict[str, Any]]], Any]:
    def decorator(
        fn: Callable[[RecordService, Record, dict[str, Any]], dict[str, Any]],
    ) -> Callable[[RecordService, Record, dict[str, Any]], dict[str, Any]]:
        _actions[(object_api_name, name)] = Action(
            object_api_name,
            name,
            label,
            fn,
            requires_edit,
            guard,
            visible,
            pack_key,
            portal or client_only,
            client_only,
        )
        return fn

    return decorator


_locks: dict[str, Callable[[Record], bool]] = {}


def locked_when(object_api_name: str, predicate: Callable[[Record], bool]) -> None:
    """Records the pack's update rules refuse to change (a signed agreement, an append-only ledger row,
    billed time) are shown without Edit or Delete. The rules still enforce it; this is the UI hint."""
    _locks[object_api_name] = predicate


def is_locked(record: Record) -> bool:
    predicate = _locks.get(record.object_api_name)
    return bool(predicate and predicate(record))


def hooks_for(object_api_name: str, event: Event, enabled_packs: frozenset[str]) -> list[Hook]:
    return [
        fn for pack, fn in _hooks.get((object_api_name, event), []) if pack is None or pack in enabled_packs
    ]


def get_action(object_api_name: str, name: str) -> Action | None:
    return _actions.get((object_api_name, name))


def actions_for(object_api_name: str, enabled_packs: frozenset[str]) -> list[Action]:
    return [
        a
        for (obj, _), a in _actions.items()
        if obj == object_api_name and (a.pack_key is None or a.pack_key in enabled_packs)
    ]


def ref(value: Any) -> uuid.UUID | None:
    """Lookup value (str) -> UUID."""
    if value is None or value == "":
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
