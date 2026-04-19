"""
ComplianceOS — Centralised Configuration
Uses pydantic-settings for type-safe env loading.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # ── App ──
    APP_NAME: str = "ComplianceOS"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    ENV: str = "production"  # development | staging | production

    # ── Database ──
    # Default to PostgreSQL for production readiness
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/complianceos"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # ── Security & JWT Auth ──
    SECRET_KEY: str = "MUST-BE-CHANGED-IN-PROD"
    JWT_SECRET: str = "MUST-BE-CHANGED-IN-PROD"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ACCOUNT_LOCKOUT_ATTEMPTS: int = 5

    # ── Groq AI ──
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_RETRIES: int = 3
    GROQ_TIMEOUT: int = 30
    
    # ── OpenAI ──
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TIMEOUT: int = 120
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_BASE_URL: Optional[str] = None

    # ── Anthropic (Claude) ──
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20240620"

    # ── Google Gemini ──
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # ── ChromaDB ──
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION_PREFIX: str = "cos"

    # ── File Upload ──
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"
    UPLOAD_DIR: str = "./uploads"

    # ── Email / SMTP ──
    SMTP_HOST: str = "smtp.resend.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = "resend"
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "onboarding@complianceos.com"
    ENABLE_EMAIL: bool = False

    # ── Billing (Stripe / Razorpay) ──
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_SUCCESS_URL: str = "https://complianceos.com/billing.html?status=success"
    STRIPE_CANCEL_URL: str = "https://complianceos.com/billing.html?status=cancel"

    # ── Monitoring ──
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["https://complianceos.com", "http://localhost:8000"]

    # ── Paths ──
    FRONTEND_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()
