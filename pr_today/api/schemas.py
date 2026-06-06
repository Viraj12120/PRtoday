"""Pydantic schemas for the PR Today API request/response models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Request Schemas
# ──────────────────────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """POST /analyze request body."""

    repo: str = Field(
        ...,
        description="Repository in 'owner/name' format.",
        examples=["Viraj12120/PRtoday"],
    )
    pr_number: int = Field(
        ...,
        description="Pull request number to analyze.",
        gt=0,
        examples=[42],
    )
    user_id: str = Field(
        ...,
        description="Identifier of the requesting user.",
        examples=["user-abc-123"],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Response Schemas
# ──────────────────────────────────────────────────────────────────────────────


class AnalyzeResponse(BaseModel):
    """POST /analyze response body."""

    risk_score: int = Field(..., ge=0, le=100, description="Overall risk score 0-100.")
    blast_radius: List[str] = Field(
        ..., description="List of impacted modules/packages."
    )
    files_changed: List[str] = Field(..., description="List of changed file paths.")
    ai_summary: Optional[str] = Field(
        None, description="AI-generated summary of the PR changes."
    )
    security_findings: List[str] = Field(
        default_factory=list,
        description="Security-related findings (secrets, config changes).",
    )


class HealthResponse(BaseModel):
    """GET /health response body."""

    status: str = Field("ok", description="Service status.")
    db: bool = Field(..., description="Database connectivity.")
    redis: bool = Field(..., description="Redis connectivity.")


class HistoryItem(BaseModel):
    """Single item in the GET /history response."""

    id: int
    repo: str
    pr_number: int
    risk_score: int
    risk_level: str
    blast_radius: List[str]
    files_changed: List[str]
    ai_summary: Optional[str] = None
    security_findings: List[str] = Field(default_factory=list)
    created_at: datetime


class HistoryResponse(BaseModel):
    """GET /history response body."""

    count: int
    results: List[HistoryItem]
