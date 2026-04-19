"""Audit log model for security and compliance tracking."""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(128), nullable=False)  # e.g. "login", "analyze", "upload"
    resource = Column(String(256), nullable=True)  # e.g. "report/<id>"
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    details = Column(Text, nullable=True)  # JSON string of extra context
    status = Column(String(32), default="success")  # success, failure, warning

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id}>"
