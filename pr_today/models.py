"""Database models for PRtoday."""

from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import DateTime, Integer, String, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


class AnalysisResult(Base):
    """ORM model representing the analysis result of a Pull Request."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    
    # JSON columns
    blast_radius: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    missing_tests: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    
    # AI review fields
    ai_summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_failures: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    ai_focus_areas: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    
    # Metadata and detection flags
    files_changed: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    db_migrations_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config_changes_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dependency_changes_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<AnalysisResult repo={self.repo} pr={self.pr_number} score={self.risk_score}>"
