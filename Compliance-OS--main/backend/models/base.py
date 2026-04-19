"""SQLAlchemy declarative base with common mixins."""

import uuid
import datetime
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ComplianceOS models."""
    pass


class TimestampMixin:
    """Adds created_at / updated_at to any model."""
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )


def generate_uuid() -> str:
    return str(uuid.uuid4())
