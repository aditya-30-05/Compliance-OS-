"""Subscription / billing model."""

import enum
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin, generate_uuid


class PlanTier(str, enum.Enum):
    FREE = "free"
    STARTUP = "startup"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


# Plan limits configuration
PLAN_LIMITS = {
    PlanTier.FREE: {
        "monthly_reports": 10,
        "storage_mb": 100,
        "ai_credits": 50,
        "max_seats": 2,
    },
    PlanTier.STARTUP: {
        "monthly_reports": 100,
        "storage_mb": 1024,
        "ai_credits": 500,
        "max_seats": 10,
    },
    PlanTier.GROWTH: {
        "monthly_reports": 500,
        "storage_mb": 5120,
        "ai_credits": 2000,
        "max_seats": 50,
    },
    PlanTier.ENTERPRISE: {
        "monthly_reports": -1,  # unlimited
        "storage_mb": -1,
        "ai_credits": -1,
        "max_seats": -1,
    },
}


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), unique=True, nullable=False)
    plan = Column(Enum(PlanTier), default=PlanTier.FREE, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    current_period_end = Column(DateTime, nullable=True)

    # Usage counters (reset monthly)
    reports_used = Column(Integer, default=0)
    storage_used_mb = Column(Integer, default=0)
    ai_credits_used = Column(Integer, default=0)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription tenant={self.tenant_id} plan={self.plan}>"
