"""Configuration management for PRtoday using Pydantic Settings."""

import logging
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
try:
    settings = Settings()
except Exception as e:
    # Print a user-friendly error and exit if validation fails
    import sys
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
