"""
Multi-tenant service — tenant creation, isolation, workspace management.
"""

import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.tenant import Tenant
from backend.models.subscription import Subscription, PlanTier
from backend.models.base import generate_uuid
from backend.utils.logger import logger


def _slugify(name: str) -> str:
    """Convert name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug[:128]


async def create_tenant(
    db: AsyncSession,
    name: str,
    industry: str = "corporate",
    max_seats: int = 5,
) -> Tenant:
    """Create a new tenant with a free subscription."""
    slug = _slugify(name)

    # Check for duplicate slug
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    existing = result.scalar_one_or_none()
    if existing:
        slug = f"{slug}-{generate_uuid()[:8]}"

    tenant = Tenant(
        id=generate_uuid(),
        name=name,
        slug=slug,
        industry=industry,
        max_seats=max_seats,
    )
    db.add(tenant)
    await db.flush()

    # Create free subscription
    subscription = Subscription(
        id=generate_uuid(),
        tenant_id=tenant.id,
        plan=PlanTier.FREE,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(tenant)

    logger.info(f"Tenant created: {tenant.name} ({tenant.id})")
    return tenant


async def get_tenant(db: AsyncSession, tenant_id: str):
    """Fetch tenant by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()
