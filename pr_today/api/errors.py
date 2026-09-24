"""Custom exceptions and structured error handlers for PR Today API."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("pr_today.api.errors")


class PRTodayAPIError(Exception):
    """Base class for all custom API exceptions."""

    def __init__(
        self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class PRNotFoundError(PRTodayAPIError):
    def __init__(self, repo: str, pr_number: int):
        super().__init__(
            message=f"Pull request #{pr_number} in {repo} not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class GitHubAuthError(PRTodayAPIError):
    def __init__(self, message: str = "Invalid GitHub credentials."):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class PRTooLargeError(PRTodayAPIError):
    def __init__(self, message: str = "Pull request diff is too large to analyze."):
        super().__init__(
            message=message, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with the FastAPI app."""

    @app.exception_handler(PRTodayAPIError)
    async def pr_today_api_error_handler(request: Request, exc: PRTodayAPIError):
        logger.warning(
            "API Error (status=%d, path=%s): %s",
            exc.status_code,
            request.url.path,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.__class__.__name__,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled Server Error (path=%s): %s",
            request.url.path,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "InternalServerError",
                    "message": "An unexpected error occurred processing your request.",
                }
            },
        )
