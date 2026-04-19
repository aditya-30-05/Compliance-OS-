"""Chat history model for persistent conversation storage."""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class ChatHistory(Base, TimestampMixin):
    __tablename__ = "chat_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    session_id = Column(String(64), nullable=True)
    role = Column(String(16), nullable=False, default="user")  # user | assistant | system
    message = Column(Text, nullable=False)
    industry = Column(String(64), nullable=True)

    # Relationships
    user = relationship("User", back_populates="chat_history")

    def __repr__(self):
        return f"<ChatHistory {self.role} session={self.session_id}>"
