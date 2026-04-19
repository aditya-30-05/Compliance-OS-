"""User model with role-based access control."""

import enum
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    ANALYST = "analyst"
    CLIENT = "client"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ANALYST, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    reports = relationship("Report", back_populates="user")
    documents = relationship("Document", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    chat_history = relationship("ChatHistory", back_populates="user")

    def __repr__(self):
        return f"<User {self.email} role={self.role}>"
