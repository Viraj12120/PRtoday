"""Database models for PRtoday V2."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


class AnalysisResult(Base):
    """ORM model representing the analysis result of a Pull Request.

    Table renamed from 'analysis_results' to 'analyses' for V2 API consistency.
    """

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)

    # JSON columns
    blast_radius: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    blast_radius_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Structured blast radius for API responses"
    )
    missing_tests: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # AI review fields
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_failures: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    ai_focus_areas: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # Security findings (derived from config/secret detection)
    security_findings: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Metadata and detection flags
    files_changed: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    db_migrations_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    config_changes_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    dependency_changes_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AnalysisResult repo={self.repo} pr={self.pr_number} score={self.risk_score}>"


class User(Base):
    """User model for tracking API consumers."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
