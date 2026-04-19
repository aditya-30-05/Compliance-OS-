"""
Analysis routes — regulatory compliance analysis via AI engine.
Backward-compatible with the existing frontend /analyze endpoint.
"""

import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.db.session import get_db
from backend.auth.dependencies import get_optional_user
from backend.models.user import User
from backend.models.report import Report
from backend.models.base import generate_uuid
from backend.services.ai_engine import run_ai_pipeline
from backend.services.vector_service import embed_document
from backend.utils.rate_limiter import ai_limiter
from backend.utils.sanitizer import sanitize_text
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Analysis"])


class AnalyzeRequest(BaseModel):
    regulation_text: str = Field(min_length=10, max_length=50000)
    industry: str = Field(default="banking", max_length=64)
    company_name: str = Field(default="Your Organization", max_length=128)


class AnalyzeResponse(BaseModel):
    status: str
    report: dict
    report_id: Optional[str] = None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_compliance(
    body: AnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Run multi-agent AI compliance analysis.
    Works for both authenticated and anonymous users (backward compat).
    Authenticated users get: report persistence, vector embeddings, usage tracking.
    """
    ai_limiter.check(request)

    regulation_text = sanitize_text(body.regulation_text, max_length=50000)
    industry = sanitize_text(body.industry, max_length=64).lower()
    company = sanitize_text(body.company_name, max_length=128)

    logger.info(f"Analysis requested: industry={industry}, text_length={len(regulation_text)}")

    # Run AI pipeline
    try:
        report_data = await run_ai_pipeline(regulation_text, industry, company)
    except Exception as e:
        logger.error(f"AI pipeline error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI analysis failed. Please try again.")

    report_id = None

    # Persist report if user is authenticated
    if current_user:
        try:
            report_id = generate_uuid()
            risk_level = "UNKNOWN"
            if isinstance(report_data.get("risk_analysis"), dict):
                risk_level = report_data["risk_analysis"].get("risk_level", "UNKNOWN")

            report = Report(
                id=report_id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                title=f"{industry.upper()} Compliance Analysis",
                regulation_text=regulation_text[:5000],
                industry=industry,
                risk_level=risk_level,
                report_json=report_data,
            )
            db.add(report)
            await db.commit()

            # Embed into vector DB for future RAG queries
            try:
                await embed_document(
                    text=regulation_text,
                    doc_id=report_id,
                    collection_name="regulations",
                    metadata={"industry": industry, "type": "regulation", "user_id": current_user.id},
                )
            except Exception as e:
                logger.warning(f"Vector embedding skipped: {e}")

        except Exception as e:
            logger.error(f"Report persistence error: {e}")
            # Don't fail the request — return the report even if persistence fails

    return AnalyzeResponse(status="success", report=report_data, report_id=report_id)


@router.get("/reports")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """List reports for the authenticated user's tenant, or return empty for anon."""
    if not current_user:
        return {"reports": [], "total": 0}

    from sqlalchemy import select, desc
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == current_user.tenant_id)
        .order_by(desc(Report.created_at))
        .limit(50)
    )
    reports = result.scalars().all()

    return {
        "reports": [
            {
                "id": r.id,
                "title": r.title,
                "industry": r.industry,
                "risk_level": r.risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
        "total": len(reports),
    }


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Get a specific report by ID."""
    from sqlalchemy import select
    query = select(Report).where(Report.id == report_id)

    # Tenant isolation for authenticated users
    if current_user:
        query = query.where(Report.tenant_id == current_user.tenant_id)

    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "title": report.title,
        "industry": report.industry,
        "risk_level": report.risk_level,
        "report": report.report_json,
        "regulation_text": report.regulation_text,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
