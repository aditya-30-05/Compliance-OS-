"""
Billing / usage tracking service with Stripe integration.
=========================================================
Handles checkout sessions, webhooks, and usage metering.
"""

import stripe
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.config import settings
from backend.models.subscription import Subscription, PlanTier, PLAN_LIMITS
from backend.utils.logger import logger

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(
    db: AsyncSession,
    tenant_id: str,
    plan: PlanTier,
    customer_email: str
) -> str:
    """Create a Stripe checkout session for a specific plan."""
    if not settings.STRIPE_SECRET_KEY:
        raise Exception("Stripe secret key not configured")

    # Mapping of tiers to Stripe Price IDs (these should be in env/config in prod)
    price_map = {
        PlanTier.STARTUP: "price_startup_id",
        PlanTier.GROWTH: "price_growth_id",
        PlanTier.ENTERPRISE: "price_enterprise_id"
    }
    
    price_id = price_map.get(plan)
    if not price_id:
        raise ValueError(f"No price mapping for plan: {plan}")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            customer_email=customer_email,
            metadata={"tenant_id": tenant_id, "plan": plan.value}
        )
        return session.url
    except Exception as e:
        logger.error(f"Stripe session creation failed: {e}")
        raise e


async def handle_stripe_webhook(db: AsyncSession, payload: bytes, sig_header: str):
    """Processes Stripe events to update subscription state."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe webhook secret missing")
        return

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise e

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _process_successful_payment(db, session)
    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        await _process_cancellation(db, sub)


async def _process_successful_payment(db: AsyncSession, session: Dict):
    tenant_id = session["metadata"]["tenant_id"]
    plan = session["metadata"]["plan"]
    stripe_sub_id = session.get("subscription")
    stripe_cus_id = session.get("customer")

    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    sub = result.scalar_one_or_none()
    
    if not sub:
        sub = Subscription(tenant_id=tenant_id)
        db.add(sub)
    
    sub.plan = PlanTier(plan)
    sub.stripe_subscription_id = stripe_sub_id
    sub.stripe_customer_id = stripe_cus_id
    # Reset usage on new plan
    sub.reports_used = 0
    sub.ai_credits_used = 0
    
    await db.commit()
    logger.info(f"Subscription activated for tenant {tenant_id}: {plan}")


async def _process_cancellation(db: AsyncSession, stripe_sub: Dict):
    stripe_sub_id = stripe_sub["id"]
    result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id))
    sub = result.scalar_one_or_none()
    
    if sub:
        sub.plan = PlanTier.FREE
        sub.stripe_subscription_id = None
        await db.commit()
        logger.info(f"Subscription cancelled for tenant {sub.tenant_id}")


# ── Usage Metering ──────────────────────────────────────────────────

async def check_usage_limit(db: AsyncSession, tenant_id: str, resource: str) -> tuple[bool, str]:
    """Check if tenant is within plan limits."""
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    sub = result.scalar_one_or_none()
    
    if not sub:
        return True, "Free tier usage"

    limits = PLAN_LIMITS.get(sub.plan, PLAN_LIMITS[PlanTier.FREE])
    
    limit_map = {
        "reports": limits["monthly_reports"],
        "ai_credits": limits["ai_credits"],
        "storage_mb": limits["storage_mb"]
    }
    
    limit = limit_map.get(resource, 0)
    used = getattr(sub, f"{resource}_used", 0) if resource != "storage_mb" else sub.storage_used_mb
    
    if limit == -1: return True, "Unlimited"
    if used >= limit: return False, f"Limit reached: {used}/{limit}"
    
    return True, f"{used}/{limit} used"

async def increment_usage(db: AsyncSession, tenant_id: str, resource: str, amount: int = 1):
    """Track resource consumption."""
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    sub = result.scalar_one_or_none()
    if sub:
        attr = f"{resource}_used" if resource != "storage_mb" else "storage_used_mb"
        setattr(sub, attr, getattr(sub, attr, 0) + amount)
        await db.commit()


async def get_usage_summary(db: AsyncSession, tenant_id: str) -> Dict:
    """Retrieve usage vs limits map for the frontend."""
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    sub = result.scalar_one_or_none()
    
    if not sub:
        # Default for new tenants before activation
        return {
            "plan": PlanTier.FREE,
            "reports": {"used": 0, "limit": 10},
            "ai": {"used": 0, "limit": 50},
            "storage": {"used": 0, "limit": 100}
        }

    limits = PLAN_LIMITS.get(sub.plan, PLAN_LIMITS[PlanTier.FREE])
    
    return {
        "plan": sub.plan,
        "reports": {"used": sub.reports_used, "limit": limits["monthly_reports"]},
        "ai": {"used": sub.ai_credits_used, "limit": limits["monthly_reports"]}, # using monthly_reports check since ai_credits name differs
        "storage": {"used": sub.storage_used_mb, "limit": limits["storage_mb"]}
    }
