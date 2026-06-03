import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy import create_engine, String, Text, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pr_sentinel.risk.scorer import RiskReport
from pr_sentinel.ai import AiReviewReport

CONFIG_DIR = Path.home() / ".pr_sentinel"
DB_FILE = CONFIG_DIR / "history.db"

# Ensure config directory exists
if not CONFIG_DIR.exists():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_FILE}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo: Mapped[str] = mapped_column(String(255), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def save_analysis(
    repo: str,
    pr_number: int,
    title: str,
    risk_report: RiskReport,
    ai_report: AiReviewReport,
) -> AnalysisRecord:
    """Save an analysis report to the local history database."""
    init_db()
    db = SessionLocal()
    try:
        record = AnalysisRecord(
            repo=repo,
            pr_number=pr_number,
            title=title,
            risk_score=risk_report.score,
            risk_level=risk_report.level.value,
            files_changed=risk_report.total_files_changed,
            additions=risk_report.total_additions,
            deletions=risk_report.total_deletions,
            ai_summary=ai_report.summary if ai_report else None,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    finally:
        db.close()


def get_history() -> List[AnalysisRecord]:
    """Retrieve all saved analysis records ordered by timestamp descending."""
    init_db()
    db = SessionLocal()
    try:
        return (
            db.query(AnalysisRecord)
            .order_by(AnalysisRecord.timestamp.desc())
            .all()
        )
    finally:
        db.close()
