"""SQLAlchemy ORM models.

Import models here so Alembic's autogenerate sees them via ``Base.metadata``.
Phase 0 ships no concrete tables yet — the data model (plan §8) lands in Phase 1.
"""

from app.models.base import Base

__all__ = ["Base"]
