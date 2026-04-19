"""
Billing routes — checkout sessions and Stripe webhooks.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.db.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.subscription import PlanTier
from backend.services.billing_service import create_checkout_session, handle_stripe_webhook, get_usage_summary

router = APIRouter(prefix="/billing", tags=["Billing"])

class CheckoutRequest(BaseModel):
    plan: PlanTier

@router.post("/checkout")
async def create_billing_session(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for the user's tenant."""
    try:
        url = await create_checkout_session(
            db, 
            tenant_id=current_user.tenant_id, 
            plan=body.plan,
            customer_email=current_user.email
        )
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usage")
async def get_tenant_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current usage and limits for the tenant."""
    return await get_usage_summary(db, current_user.tenant_id)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Stripe webhook endpoint for subscription events."""
    payload = await request.body()
    try:
        await handle_stripe_webhook(db, payload, stripe_signature)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
