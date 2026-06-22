"""Declarative base for all ORM models (SQLAlchemy 2 style)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All tables inherit from this."""
