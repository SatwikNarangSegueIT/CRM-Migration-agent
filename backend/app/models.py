"""Import every model module here so Alembic autogenerate sees all tables.

Domain models are added from phase 1 onwards.
"""

from app.db.base import Base

__all__ = ["Base"]
