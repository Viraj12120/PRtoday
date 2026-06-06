"""GET /health route — checks database and Redis connectivity."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from pr_today.api.schemas import HealthResponse
from pr_today.database import get_engine

logger = logging.getLogger("pr_today.api.routes.health")

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    """Return service health status including database and Redis checks."""

    # Check database connectivity
    db_ok = False
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("Database health check failed: %s", e)

    # Check Redis connectivity
    redis_ok = False
    try:
        from pr_today.api.main import get_redis

        redis_client = await get_redis()
        if redis_client is not None:
            await redis_client.ping()
            redis_ok = True
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db=db_ok,
        redis=redis_ok,
    )
