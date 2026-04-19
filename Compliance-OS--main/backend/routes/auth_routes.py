"""
Authentication routes — register, login, refresh, profile.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_db
from backend.models.user import User, UserRole
from backend.models.base import generate_uuid
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt_handler import (
    create_access_token, 
    create_refresh_token, 
    verify_token, 
    create_reset_token
)
from backend.auth.dependencies import get_current_user
from backend.services.tenant_service import create_tenant
from backend.utils.rate_limiter import auth_limiter
from backend.utils.sanitizer import sanitize_email, sanitize_text
from backend.utils.email_service import send_password_reset_email, send_welcome_email
from backend.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / Response Schemas ──────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=128)
    company_name: str = Field(min_length=2, max_length=128)
    industry: str = Field(default="corporate", max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# ── Routes ──────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new user + create their tenant workspace."""
    auth_limiter.check(request)

    email = sanitize_email(body.email)
    full_name = sanitize_text(body.full_name, max_length=128)
    company_name = sanitize_text(body.company_name, max_length=128)

    # Check duplicate email
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Create tenant
    tenant = await create_tenant(db, name=company_name, industry=body.industry)

    # Create user
    user = User(
        id=generate_uuid(),
        email=email,
        full_name=full_name,
        hashed_password=hash_password(body.password),
        role=UserRole.ADMIN,  # First user = admin
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    token_data = {"sub": user.id, "email": user.email, "role": user.role.value, "tenant_id": user.tenant_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"New user registered: {email} (tenant: {tenant.slug})")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
            "company": company_name,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT tokens."""
    auth_limiter.check(request)

    email = sanitize_email(body.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    token_data = {"sub": user.id, "email": user.email, "role": user.role.value, "tenant_id": user.tenant_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"User logged in: {email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
        },
    )


@router.post("/refresh", response_model=dict)
async def refresh_token(body: RefreshRequest):
    """Refresh access token using refresh token."""
    payload = verify_token(body.refresh_token, expected_type="refresh")
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    token_data = {"sub": payload["sub"], "email": payload["email"], "role": payload["role"], "tenant_id": payload["tenant_id"]}
    new_access = create_access_token(token_data)
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me", response_model=dict)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "tenant_id": current_user.tenant_id,
        "is_active": current_user.is_active,
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Initiate password reset flow."""
    email = sanitize_email(body.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if user:
        token = create_reset_token(user.email)
        send_password_reset_email(user.email, token)
        logger.info(f"Password reset initiated for: {email}")
        
    # Always return same message to prevent account enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using token."""
    payload = verify_token(body.token, expected_type="reset")
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    email = payload["sub"]
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    logger.info(f"Password reset successful for: {email}")
    
    return {"message": "Password updated successfully"}
