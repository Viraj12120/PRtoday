"""Database session management and initialization for PRtoday V2.

Supports both PostgreSQL (asyncpg) for the API server and SQLite (aiosqlite)
for backward-compatible CLI usage. The driver is selected based on DATABASE_URL.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pr_today.models import Base

logger = logging.getLogger("pr_today.database")

# ──────────────────────────────────────────────────────────────────────────────
# Engine & session factory — lazily initialized via `init_db()`
# ──────────────────────────────────────────────────────────────────────────────
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _resolve_database_url() -> str:
    """Resolve the database URL from settings, with SQLite local fallback."""
    # Late import to avoid circular dependency at module-load time
    from pr_today.config import settings

    url = settings.DATABASE_URL

    # SQLite fallback: ensure directory exists
    if url.startswith("sqlite"):
        db_dir = Path.home() / ".pr_today"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "history.db"
        url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        logger.info("Using SQLite database at %s", db_path)
    else:
        logger.info("Using database: %s", url.split("@")[-1] if "@" in url else url)

    return url


def _get_engine_kwargs(url: str) -> dict:
    """Return engine kwargs appropriate for the database driver."""
    kwargs: dict = {"echo": False}
    if url.startswith("postgresql"):
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True
    return kwargs


def get_engine() -> AsyncEngine:
    """Return the current async engine, creating it if needed."""
    global _engine
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_async_engine(url, **_get_engine_kwargs(url))
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the current session maker, creating it if needed."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def init_db() -> None:
    """Initialize database tables if they do not exist.

    For production, prefer Alembic migrations. This is kept for
    quick local dev and CLI backward compatibility.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database engine disposed.")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional database session context."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
