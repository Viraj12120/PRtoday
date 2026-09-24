"""Pydantic schemas for the PR Today API request/response models."""

from datetime import datetime
from typing import List, Optional, Dict, Any

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
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH, CRITICAL.")
    blast_radius: List[str] = Field(
        ..., description="List of impacted modules/packages."
    )
    files_changed: List[str] = Field(..., description="List of changed file paths.")
    ai_summary: Optional[str] = Field(
        None, description="AI-generated executive summary of the PR changes."
    )
    change_classification: Optional[str] = Field(
        None, description="AI-classified change type: FEATURE, BUGFIX, REFACTOR, etc."
    )
    architectural_impact: Optional[str] = Field(
        None, description="AI assessment of architectural impact."
    )
    ai_failures: List[str] = Field(
        default_factory=list, description="AI-predicted failure scenarios."
    )
    ai_focus_areas: List[str] = Field(
        default_factory=list, description="AI-recommended reviewer focus areas."
    )
    security_notes: Optional[str] = Field(
        None, description="AI security observations."
    )
    testing_gaps: Optional[str] = Field(
        None, description="AI-identified testing gaps."
    )
    security_findings: List[Any] = Field(
        default_factory=list,
        description="Deterministic security-related findings (secrets, config changes).",
    )
    db_migrations_detected: bool = Field(False, description="Whether DB migrations were detected.")
    config_changes_detected: bool = Field(False, description="Whether config changes were detected.")
    dependency_changes_detected: bool = Field(False, description="Whether dependency changes were detected.")
    ai_tokens_prompt: Optional[int] = Field(None, description="Prompt tokens used.")
    ai_tokens_completion: Optional[int] = Field(None, description="Completion tokens used.")
    ai_cost_usd: Optional[float] = Field(None, description="Estimated AI cost in USD.")
    ai_latency_ms: Optional[int] = Field(None, description="AI response latency in ms.")
    ai_model_used: Optional[str] = Field(None, description="AI model identifier.")
    confidence_score: int = Field(..., description="System confidence score in the AI review accuracy (0-100).")


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
    security_findings: List[Any] = Field(default_factory=list)
    created_at: datetime


class HistoryResponse(BaseModel):
    """GET /history response body."""

    count: int
    results: List[HistoryItem]
    next_cursor: Optional[int] = Field(None, description="Cursor for the next page of results.")
