import pytest
from unittest import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pr_sentinel.db import Base, save_analysis, get_history
from pr_sentinel.risk.scorer import RiskReport, RiskLevel
from pr_sentinel.ai import AiReviewReport


@pytest.fixture(autouse=True)
def setup_in_memory_db():
    """Configure an isolated in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with mock.patch("pr_sentinel.db.engine", test_engine), \
         mock.patch("pr_sentinel.db.SessionLocal", TestSessionLocal):
        yield


def test_save_and_retrieve_analysis():
    # Arrange
    risk_report = RiskReport(
        score=45,
        level=RiskLevel.MEDIUM,
        total_files_changed=5,
        total_additions=120,
        total_deletions=30,
    )
    ai_report = AiReviewReport(
        summary="This PR updates database models.",
    )

    # Act
    record = save_analysis(
        repo="pallets/flask",
        pr_number=5000,
        title="Test PR",
        risk_report=risk_report,
        ai_report=ai_report,
    )

    # Assert
    assert record.id is not None
    assert record.repo == "pallets/flask"
    assert record.pr_number == 5000
    assert record.title == "Test PR"
    assert record.risk_score == 45
    assert record.risk_level == "MEDIUM"
    assert record.files_changed == 5
    assert record.additions == 120
    assert record.deletions == 30
    assert record.ai_summary == "This PR updates database models."

    # Verify retrieval
    history = get_history()
    assert len(history) == 1
    assert history[0].repo == "pallets/flask"
    assert history[0].pr_number == 5000
