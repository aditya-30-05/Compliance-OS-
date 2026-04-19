"""
Chat routes — AI copilot conversation with history persistence.
Backward-compatible with existing frontend /chat endpoint.
"""

import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from backend.db.session import get_db
from backend.auth.dependencies import get_optional_user
from backend.models.user import User
from backend.models.chat_history import ChatHistory
from backend.models.base import generate_uuid
from backend.services.ai_engine import chat_with_ai
from backend.utils.rate_limiter import ai_limiter
from backend.utils.sanitizer import sanitize_text
from backend.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    industry: str = Field(default="corporate", max_length=64)
    context: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    engine: str = "groq"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """AI chat — uses Groq LLM with heuristic fallback. Persists history when authenticated."""
    ai_limiter.check(request)

    message = sanitize_text(body.message, max_length=5000)
    industry = sanitize_text(body.industry, max_length=64)
    context = body.context if body.context else ""

    try:
        reply = await chat_with_ai(message, industry, context)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        reply = "I'm experiencing a temporary issue. Please try again in a moment."

    # Persist chat history for authenticated users
    if current_user:
        try:
            user_entry = ChatHistory(
                id=generate_uuid(),
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                role="user",
                content=message,
            )
            assistant_entry = ChatHistory(
                id=generate_uuid(),
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                role="assistant",
                content=reply,
            )
            db.add(user_entry)
            db.add(assistant_entry)
            await db.commit()
        except Exception as e:
            logger.warning(f"Chat history save failed: {e}")

    engine = "groq" if "heuristic" not in reply.lower() else "heuristic"
    return ChatResponse(reply=reply, engine=engine)


@router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get chat history for the current user."""
    if not current_user:
        return {"history": [], "total": 0}

    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
    )
    entries = result.scalars().all()

    # Reverse to chronological order
    entries = list(reversed(entries))

    return {
        "history": [
            {
                "role": e.role,
                "content": e.content,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "total": len(entries),
    }
