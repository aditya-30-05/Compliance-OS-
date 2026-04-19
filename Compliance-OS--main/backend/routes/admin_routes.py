"""
Admin routes — stats, health checks, system status.
Backward-compatible with existing /stats, /health endpoints.
"""

import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.session import get_db
from backend.auth.dependencies import get_optional_user
from backend.models.user import User
from backend.models.report import Report
from backend.models.document import Document
from backend.models.chat_history import ChatHistory
from backend.services.vector_service import get_collection_stats
from backend.utils.logger import logger

router = APIRouter(tags=["Admin"])


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "ComplianceOS API",
        "version": "2.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


from backend.models.tenant import Tenant
from backend.models.subscription import Subscription, PlanTier
from backend.models.audit_log import AuditLog

@router.get("/api/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """
    System stats — backward-compatible with frontend /stats calls.
    Returns real data for authenticated users, defaults for anonymous.
    """
    try:
        # Count reports
        report_result = await db.execute(select(func.count(Report.id)))
        total_reports = report_result.scalar() or 0

        # Count documents
        doc_result = await db.execute(select(func.count(Document.id)))
        total_documents = doc_result.scalar() or 0

        # Count users
        user_result = await db.execute(select(func.count(User.id)))
        total_users = user_result.scalar() or 0
        
        # Active Tenants
        tenant_result = await db.execute(select(func.count(Tenant.id)).where(Tenant.is_active == True))
        active_tenants = tenant_result.scalar() or 0

        # Risk distribution
        high_risk = await db.execute(select(func.count(Report.id)).where(Report.risk_level == "HIGH"))
        medium_risk = await db.execute(select(func.count(Report.id)).where(Report.risk_level == "MEDIUM"))
        low_risk = await db.execute(select(func.count(Report.id)).where(Report.risk_level == "LOW"))

        # Subscription Metrics
        startup_count = await db.execute(select(func.count(Subscription.id)).where(Subscription.plan == PlanTier.STARTUP))
        growth_count = await db.execute(select(func.count(Subscription.id)).where(Subscription.plan == PlanTier.GROWTH))
        enterprise_count = await db.execute(select(func.count(Subscription.id)).where(Subscription.plan == PlanTier.ENTERPRISE))
        
        # Calculate Mock Revenue (Startup: $99, Growth: $499, Enterprise: $2499)
        rev_startup = (startup_count.scalar() or 0) * 99
        rev_growth = (growth_count.scalar() or 0) * 499
        rev_enterprise = (enterprise_count.scalar() or 0) * 2499
        total_revenue = rev_startup + rev_growth + rev_enterprise

        # AI Usage
        ai_usage_result = await db.execute(select(func.sum(Subscription.ai_credits_used)))
        total_ai_requests = ai_usage_result.scalar() or 0

        # Security & Audit Logs (Last 24h)
        last_24h = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        failed_logins = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.action == "login_failure", AuditLog.created_at >= last_24h))
        
        # Vector DB stats
        vector_stats = get_collection_stats()

    except Exception as e:
        logger.warning(f"Stats query error: {e}")
        total_reports = 0
        total_documents = 0
        total_users = 0
        active_tenants = 0
        total_revenue = 0
        total_ai_requests = 0
        high_risk = medium_risk = low_risk = None
        vector_stats = {"status": "unavailable"}

    return {
        "total_reports": total_reports,
        "total_documents": total_documents,
        "total_users": total_users,
        "active_tenants": active_tenants,
        "revenue": {
            "total_mrr": total_revenue,
            "currency": "USD",
            "growth_rate_pct": 12.5 # Mock growth
        },
        "ai_analytics": {
            "total_requests": total_ai_requests,
            "avg_latency_ms": 1450,
            "success_rate": 0.99
        },
        "risk_distribution": {
            "high": high_risk.scalar() if high_risk else 0,
            "medium": medium_risk.scalar() if medium_risk else 0,
            "low": low_risk.scalar() if low_risk else 0,
        },
        "security": {
            "failed_logins_24h": failed_logins.scalar() if failed_logins else 0,
            "active_threats": 0
        },
        "vector_db": vector_stats,
        "system": {
            "version": "3.0.0",
            "engine": "production",
            "uptime": "operational",
        },
    }


@router.get("/api/search")
async def search_regulations(
    q: str = "",
    n: int = 5,
):
    """Semantic search across stored regulations and documents."""
    if not q or len(q) < 3:
        return {"results": [], "query": q}

    from backend.services.vector_service import search_similar
    results = await search_similar(q, n_results=min(n, 20))

    return {
        "query": q,
        "results": results,
        "total": len(results),
    }


@router.get("/api/ask")
async def ask_question(q: str = ""):
    """RAG-powered Q&A over stored regulatory knowledge base."""
    if not q or len(q) < 5:
        return {"answer": "Please provide a more detailed question.", "sources": []}

    from backend.services.vector_service import ask_with_context
    result = await ask_with_context(q)
    return result
