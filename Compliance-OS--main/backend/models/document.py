"""Uploaded document model."""

from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    original_filename = Column(String(512), nullable=False)
    stored_path = Column(String(1024), nullable=False)
    file_type = Column(String(16), nullable=False)  # pdf, docx, txt
    file_size_bytes = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    status = Column(String(32), default="uploaded")  # uploaded, processing, processed, failed

    # Multi-tenant isolation
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="documents")
    tenant = relationship("Tenant", back_populates="documents")

    def __repr__(self):
        return f"<Document {self.original_filename} status={self.status}>"
