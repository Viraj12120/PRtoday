import pytest
from pr_today.dashboard import Dashboard
from pr_today.models import AnalysisResult
from datetime import datetime, timezone


def test_dashboard_render_smoke():
    dashboard = Dashboard()
    result = AnalysisResult(
        repo="test/repo",
        pr_number=1,
        risk_score=95,
        risk_level="CRITICAL",
        files_changed=["a.py"],
        db_migrations_detected=True,
        config_changes_detected=True,
        dependency_changes_detected=True,
        ai_summary="Bad code.",
        ai_failures=["Will crash"],
        ai_focus_areas=["Check lines 10-20"],
        blast_radius=["test/repo"],
        missing_tests=["a.py"],
        created_at=datetime.now(timezone.utc),
    )
    # Just verify it doesn't crash
    dashboard.render(result, "testuser")
