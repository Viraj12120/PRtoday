"""API Authentication middleware and dependencies."""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from pr_today.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency to verify the API key."""
    if not settings.API_AUTH_TOKEN:
        # If no auth token is configured, allow all (dev mode)
        return "anonymous"

    if api_key != settings.API_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return "authenticated_user"
