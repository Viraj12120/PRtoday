"""Database session management and initialization for PRtoday."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pr_today.models import Base

# XDG-compliant path for history database
DB_DIR = Path.home() / ".pr_today"
DB_PATH = DB_DIR / "history.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"

# Ensure the database directory exists
DB_DIR.mkdir(parents=True, exist_ok=True)

# Create async engine and session factory
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional database session context."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
