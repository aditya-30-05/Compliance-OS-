"""Tenant / Organization model for multi-tenancy."""

from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(128), unique=True, nullable=False, index=True)
    industry = Column(String(64), default="corporate")
    max_seats = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)

    # Relationships
    users = relationship("User", back_populates="tenant")
    reports = relationship("Report", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")
    subscription = relationship("Subscription", back_populates="tenant", uselist=False)

    def __repr__(self):
        return f"<Tenant {self.name}>"
