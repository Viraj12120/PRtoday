"""Rate limiting middleware backed by Redis."""

import time

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from pr_today.cache import get_redis

# Simple fixed window rate limiting
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limits requests based on client IP using Redis."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        redis_client = await get_redis()

        if redis_client is None:
            # If Redis is unavailable, skip rate limiting
            return await call_next(request)

        # Use X-Forwarded-For if available, fallback to client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        current_minute = int(time.time() / RATE_LIMIT_WINDOW_SECONDS)
        key = f"ratelimit:{client_ip}:{current_minute}"

        try:
            # Increment request count
            count = await redis_client.incr(key)
            if count == 1:
                # Set expiry on first request in this window
                await redis_client.expire(key, RATE_LIMIT_WINDOW_SECONDS)

            if count > RATE_LIMIT_REQUESTS:
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        except Exception:
            # Fail open if Redis has an issue
            pass

        return await call_next(request)
