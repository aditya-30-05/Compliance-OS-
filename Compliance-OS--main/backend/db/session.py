"""
Async SQLAlchemy session management.
Supports both SQLite (dev) and PostgreSQL (prod).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from backend.config import settings
from backend.models.base import Base

# Determine pool class based on database type
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Engine configuration depends on the dialect
engine_args = {
    "echo": settings.DEBUG,
}

if is_sqlite:
    engine_args["poolclass"] = NullPool
else:
    engine_args["pool_size"] = settings.DB_POOL_SIZE
    engine_args["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_args["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_args["pool_recycle"] = 3600
    engine_args["pool_pre_ping"] = True

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

async def init_db():
    """Initialize database tables. In production, use Alembic."""
    async with engine.begin() as conn:
        # In actual production, we'd rely on Alembic migrations
        # but keep this for dev/test environments.
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Dispose engine on shutdown."""
    await engine.dispose()
