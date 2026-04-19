"""Compliance report model."""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    doc_name = Column(String(512), nullable=False)
    industry = Column(String(64), nullable=False)
    risk_level = Column(String(16), nullable=False)
    authority = Column(String(64), default="Global Regulator")
    regulation_text = Column(Text, nullable=True)
    full_report = Column(JSON, nullable=False)
    ai_model_used = Column(String(64), default="heuristic")
    processing_time_ms = Column(Integer, nullable=True)

    # Multi-tenant isolation
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="reports")
    tenant = relationship("Tenant", back_populates="reports")

    def __repr__(self):
        return f"<Report {self.doc_name} risk={self.risk_level}>"
