"""Revision-keyed in-process caches for per-request reference data.

Metadata (objects, fields, apps, packs) and security configuration (profiles, permissions, roles, groups,
queues, sharing) change rarely but were re-read on every request: 7-44 SQL round trips each. They are now
cached in memory, keyed by tenant and by two revision counters stored in the database
(``metadata_revision.revision`` and ``metadata_revision.security``):

* the session lookup reads both counters in the same SQL statement, so freshness costs no extra round trip
  and every API process sees a change as soon as it is committed;
* a change bumps its counter in the same transaction (metadata: ``bump_revision``; security: automatically,
  see ``app.security.revision``);
* a session with an uncommitted bump never stores into the shared cache, so a rollback cannot leave an entry
  that describes data which was never committed.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, NamedTuple, TypeVar

from sqlalchemy import text
from sqlalchemy.orm import Session

T = TypeVar("T")

DEFAULT_TENANT = "public"
_REVISIONS_KEY = "revisions"
_PENDING_KEY = "revision_pending"


class Revisions(NamedTuple):
    metadata: int
    security: int


def tenant_of(db: Session) -> str:
    """Tenant (schema) the session works in. Set by the tenancy layer; single-tenant installs use public."""
    return str(db.info.get("tenant", DEFAULT_TENANT))


def set_revisions(db: Session, metadata: int | None, security: int | None) -> None:
    db.info[_REVISIONS_KEY] = Revisions(int(metadata or 0), int(security or 0))


def revisions(db: Session) -> Revisions:
    """Revisions known for this session (from the session lookup), else read with one query."""
    known = db.info.get(_REVISIONS_KEY)
    if isinstance(known, Revisions):
        return known
    row = db.execute(text("SELECT revision, security FROM metadata_revision WHERE id = 1")).first()
    set_revisions(db, row[0] if row else 0, row[1] if row else 0)
    return db.info[_REVISIONS_KEY]  # type: ignore[no-any-return]


def mark_pending(db: Session, *, metadata: int | None = None, security: int | None = None) -> None:
    """Record an uncommitted bump: this session bypasses the shared cache until it commits or rolls back.

    Never queries (it runs inside flush events); known revisions are updated when new values are given.
    """
    known = db.info.get(_REVISIONS_KEY)
    if isinstance(known, Revisions) and (metadata is not None or security is not None):
        set_revisions(
            db,
            metadata if metadata is not None else known.metadata,
            security if security is not None else known.security,
        )
    elif metadata is not None and security is not None:
        set_revisions(db, metadata, security)
    db.info[_PENDING_KEY] = True


def clear_pending(db: Session) -> None:
    db.info.pop(_PENDING_KEY, None)


def forget_revisions(db: Session) -> None:
    db.info.pop(_REVISIONS_KEY, None)
    db.info.pop(_PENDING_KEY, None)


def cache_allowed(db: Session) -> bool:
    return not db.info.get(_PENDING_KEY, False)


class RevisionCache:
    """Small thread-safe LRU. Keys must include the tenant and the relevant revision(s)."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._data: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def get_or_build(self, db: Session, key: Hashable, build: Callable[[], T]) -> T:
        if not cache_allowed(db):
            return build()
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]  # type: ignore[no-any-return]
        value = build()
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_ALL: list[RevisionCache] = []


def new_cache(maxsize: int = 1024) -> RevisionCache:
    cache = RevisionCache(maxsize)
    _ALL.append(cache)
    return cache


def clear_all() -> None:
    """For tests and admin tooling."""
    for cache in _ALL:
        cache.clear()
