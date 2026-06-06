"""Configuration management for PRtoday using Pydantic Settings."""

import logging
import os
import sys
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    GITHUB_PAT: str = Field(
        ...,
        description="GitHub Personal Access Token for API requests.",
    )
    AI_MODEL: str = Field(
        ...,
        description="LiteLLM-compatible model identifier (e.g. gemini/gemini-2.5-flash).",
    )
    LOG_LEVEL: str = Field(
        "INFO",
        description="Logging level for the application (DEBUG, INFO, WARNING, ERROR).",
    )

    # Optional provider tokens
    HF_TOKEN: Optional[str] = Field(
        None,
        description="Hugging Face API token.",
    )
    GEMINI_API_KEY: Optional[str] = Field(
        None,
        description="Google Gemini API key.",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        None,
        description="OpenAI API key.",
    )

    # Database and infrastructure
    DATABASE_URL: str = Field(
        "sqlite+aiosqlite:///~/.pr_today/history.db",
        description="Async database URL. Use postgresql+asyncpg:// for API server.",
    )
    REDIS_URL: Optional[str] = Field(
        None,
        description="Redis URL for caching analysis results (e.g. redis://localhost:6379/0).",
    )

    # API server
    API_HOST: str = Field(
        "0.0.0.0",
        description="Host to bind the API server.",
    )
    API_PORT: int = Field(
        8000,
        description="Port for the API server.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("GITHUB_PAT", mode="before")
    @classmethod
    def validate_github_pat(cls, v: Optional[str]) -> str:
        """Ensure GITHUB_PAT is not empty or None."""
        if not v or not v.strip():
            raise ValueError(
                "GITHUB_PAT environment variable is missing or empty. "
                "Please configure it in your environment or .env file."
            )
        return v.strip()


# Global settings instance


if "pytest" in sys.modules or "unittest" in sys.modules:
    os.environ.setdefault("GITHUB_PAT", "dummy_pat_for_testing")
    os.environ.setdefault("AI_MODEL", "dummy_model_for_testing")

try:
    settings = Settings()
except Exception as e:
    # Print a user-friendly error and exit if validation fails

    print(f"Configuration Error: {e}", file=sys.stderr)
    sys.exit(1)


def setup_logging() -> None:
    """Set up the global logging configuration based on settings."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
