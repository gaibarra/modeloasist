"""Declarative Base for SQLAlchemy models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class enabling type hints across the ORM models."""

    pass
