"""FastAPI application for PR Today V2.

Provides a REST API wrapping the existing risk engine, orchestrator,
and AI review engine. Manages lifecycle of database and Redis connections.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pr_today.api.routes import analyze, health, history
from pr_today.database import close_db, init_db

logger = logging.getLogger("pr_today.api")


# ──────────────────────────────────────────────────────────────────────────────
# Redis connection (lazy, optional)
# ──────────────────────────────────────────────────────────────────────────────
_redis_client = None


async def get_redis():
    """Return the shared Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            from pr_today.config import settings

            if settings.REDIS_URL:
                import redis.asyncio as aioredis

                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
                # Verify connectivity
                await _redis_client.ping()
                logger.info("Redis connected: %s", settings.REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable: %s", e)
            _redis_client = None
    return _redis_client


# ──────────────────────────────────────────────────────────────────────────────
# Application lifespan
# ──────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of database and Redis."""
    logger.info("PR Today API starting up...")
    await init_db()
    await get_redis()
    yield
    # Shutdown
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed.")
    await close_db()
    logger.info("PR Today API shut down.")


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app factory
# ──────────────────────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="PR Today",
        description="AI-assisted PR risk assessment API — wrapping the deterministic risk engine.",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS — allow all origins for development; tighten in production
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    application.include_router(health.router, tags=["Health"])
    application.include_router(analyze.router, tags=["Analysis"])
    application.include_router(history.router, tags=["History"])

    from fastapi.responses import RedirectResponse

    @application.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/docs")

    return application


# Module-level app instance for `uvicorn pr_today.api.main:app`
app = create_app()
