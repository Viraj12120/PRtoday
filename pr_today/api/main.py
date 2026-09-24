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
from pr_today.cache import close_cache, init_cache
from pr_today.database import close_db, init_db

logger = logging.getLogger("pr_today.api")

# ──────────────────────────────────────────────────────────────────────────────
# Application lifespan
# ──────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of database and Redis."""
    logger.info("PR Today API starting up...")
    await init_db()
    await init_cache()
    yield
    # Shutdown
    await close_cache()
    await close_db()
    logger.info("PR Today API shut down.")


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app factory
# ──────────────────────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from pr_today.api.errors import setup_exception_handlers
    from pr_today.config import settings

    application = FastAPI(
        title="PR Today",
        description="AI-assisted PR risk assessment API — wrapping the deterministic risk engine.",
        version="2.0.0",
        lifespan=lifespan,
    )

    setup_exception_handlers(application)

    # CORS — controlled via config
    origins = [
        orig.strip() for orig in settings.CORS_ORIGINS.split(",") if orig.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middlewares (order matters: applied from bottom up, so RequestId first, then RateLimit)
    from pr_today.api.middleware.rate_limit import RateLimitMiddleware
    from pr_today.api.middleware.request_id import RequestIdMiddleware

    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(RequestIdMiddleware)

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
