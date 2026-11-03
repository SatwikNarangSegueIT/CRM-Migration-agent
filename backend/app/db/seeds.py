"""Shipped default data, in the order the migrations apply it.

Each seed module is idempotent (inserts only missing rows). Migrations call the individual modules;
`apply_seeds` re-applies all of them, e.g. after a test truncates every table.
"""

from __future__ import annotations

from sqlalchemy import Connection


def apply_seeds(conn: Connection) -> None:
    from app.engine import standard_reports_v1, standard_v1
    from app.security import seed_v1

    seed_v1.apply(conn)
    standard_v1.apply(conn)
    standard_reports_v1.apply(conn)
