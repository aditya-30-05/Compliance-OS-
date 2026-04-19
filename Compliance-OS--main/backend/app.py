"""
ComplianceOS — Production FastAPI Application
==============================================
Enterprise-grade AI regulatory intelligence platform.

Features:
- Multi-tenant architecture with RBAC
- Real Groq LLM pipeline with heuristic fallback
- PDF/DOCX document ingestion + extraction
- ChromaDB vector search (RAG)
- JWT authentication with refresh tokens
- Rate limiting + security headers
- Backward-compatible with existing frontend
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.session import engine
from backend.models.base import Base
from backend.utils.security_headers import SecurityHeadersMiddleware
from backend.utils.logger import logger


# ── Lifespan: DB init on startup ───────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("🚀 ComplianceOS v2.0 starting...")

    # Create tables (dev mode — production uses Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables ready")

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

    logger.info(f"✅ Upload dir: {settings.UPLOAD_DIR}")
    logger.info(f"✅ ChromaDB dir: {settings.CHROMA_PERSIST_DIR}")
    logger.info(f"✅ Debug mode: {settings.DEBUG}")
    logger.info(f"✅ AI Model: {settings.GROQ_MODEL}")

    yield

    logger.info("🛑 ComplianceOS shutting down...")
    await engine.dispose()


import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# ── Monitoring ──────────────────────────────────────────────────────
if settings.SENTRY_DSN and "your-dsn-here" not in settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=settings.ENV,
    )
    logger.info("📡 Sentry Monitoring Active")


# ── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="ComplianceOS API",
    description="AI-Powered Regulatory Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── Middleware ──────────────────────────────────────────────────────

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ──────────────────────────────────────────────────────

from backend.routes.auth_routes import router as auth_router
from backend.routes.analysis_routes import router as analysis_router
from backend.routes.chat_routes import router as chat_router
from backend.routes.document_routes import router as document_router
from backend.routes.admin_routes import router as admin_router
from backend.routes.billing_routes import router as billing_router

app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(admin_router)
app.include_router(billing_router)


# ── Static Files (serve existing frontend) ──────────────────────────

# Determine the project root (parent of backend/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mount static assets if they exist
static_dirs = ["static", "assets"]
for dir_name in static_dirs:
    static_path = os.path.join(PROJECT_ROOT, dir_name)
    if os.path.isdir(static_path):
        app.mount(f"/{dir_name}", StaticFiles(directory=static_path), name=dir_name)


# ── Frontend page routes (backward-compatible) ─────────────────────

@app.get("/")
async def serve_index():
    index_path = os.path.join(PROJECT_ROOT, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "ComplianceOS API v2.0 — frontend not found"}


@app.get("/analytics")
@app.get("/analytics.html")
async def serve_analytics():
    path = os.path.join(PROJECT_ROOT, "analytics.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Analytics page not found"}


@app.get("/realtime")
@app.get("/realtime_feed.html")
async def serve_realtime():
    path = os.path.join(PROJECT_ROOT, "realtime_feed.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Realtime feed page not found"}


@app.get("/login")
@app.get("/login.html")
async def serve_login():
    path = os.path.join(PROJECT_ROOT, "login.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Login page not found"}


@app.get("/signup")
@app.get("/signup.html")
async def serve_signup():
    path = os.path.join(PROJECT_ROOT, "signup.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Signup page not found"}


@app.get("/profile")
@app.get("/profile.html")
async def serve_profile():
    path = os.path.join(PROJECT_ROOT, "profile.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Profile page not found"}


@app.get("/billing")
@app.get("/billing.html")
async def serve_billing():
    path = os.path.join(PROJECT_ROOT, "billing.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Billing page not found"}


@app.get("/admin")
@app.get("/admin.html")
async def serve_admin():
    path = os.path.join(PROJECT_ROOT, "admin.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": "Admin dashboard not found"}


# ── Backward-compatible legacy endpoints ────────────────────────────

@app.get("/stats")
async def legacy_stats():
    """Redirect legacy /stats → /api/stats"""
    from backend.routes.admin_routes import get_stats
    from backend.db.session import get_db

    async for db in get_db():
        return await get_stats(db=db, current_user=None)


# ── Catch-all for any remaining .html files ─────────────────────────

@app.get("/{filename}.html")
async def serve_html(filename: str):
    path = os.path.join(PROJECT_ROOT, f"{filename}.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"message": f"Page '{filename}' not found"}
