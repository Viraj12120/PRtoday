"""Unit tests for the Typer CLI."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from pr_today.cli import app
from pr_today.config import settings
from pr_today.models import AnalysisResult

runner = CliRunner()


@pytest.fixture
def mock_analysis_result() -> AnalysisResult:
    """Fixture returning a mock populated AnalysisResult."""
    import datetime
    return AnalysisResult(
        id=1,
        repo="org/repo",
        pr_number=42,
        risk_score=50,
        risk_level="MEDIUM",
        blast_radius=["pr_today"],
        missing_tests=[],
        ai_summary="AI review summary",
        ai_failures=["Failure 1"],
        ai_focus_areas=["Focus 1"],
        files_changed=["pr_today/cli.py"],
        db_migrations_detected=False,
        config_changes_detected=False,
        dependency_changes_detected=False,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


def test_cli_analyze_invokes_orchestrator(mock_analysis_result):
    """Verify analyze command invokes orchestrator and dashboard correctly."""
    with patch("pr_today.cli.Orchestrator.run", new_callable=AsyncMock) as mock_run, \
         patch("pr_today.cli.Dashboard.render") as mock_render, \
         patch("pr_today.cli.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("pr_today.cli.Github") as mock_github:
         
        mock_run.return_value = mock_analysis_result
        mock_github.return_value.get_repo.return_value.get_pull.return_value.user.login = "test_user"

        result = runner.invoke(app, ["analyze", "--repo", "org/repo", "--pr", "42"])
        
        assert result.exit_code == 0
        mock_init_db.assert_called_once()
        mock_run.assert_called_once_with("org/repo", 42, no_ai=False)
        mock_render.assert_called_once_with(mock_analysis_result, author="test_user")


def test_cli_analyze_no_ai_flag(mock_analysis_result):
    """Verify analyze command passes no_ai flag correctly to the orchestrator."""
    with patch("pr_today.cli.Orchestrator.run", new_callable=AsyncMock) as mock_run, \
         patch("pr_today.cli.Dashboard.render") as mock_render, \
         patch("pr_today.cli.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("pr_today.cli.Github") as mock_github:
         
        mock_run.return_value = mock_analysis_result
        mock_github.return_value.get_repo.return_value.get_pull.return_value.user.login = "test_user"

        result = runner.invoke(app, ["analyze", "--repo", "org/repo", "--pr", "42", "--no-ai"])
        
        assert result.exit_code == 0
        mock_run.assert_called_once_with("org/repo", 42, no_ai=True)


def test_cli_auth_success():
    """Verify auth command prints success message when GitHub token is valid."""
    with patch("pr_today.cli.Github") as mock_github:
        mock_user = MagicMock()
        mock_user.login = "test_user"
        mock_user.raw_headers = {"x-oauth-scopes": "repo, read:org"}
        mock_github.return_value.get_user.return_value = mock_user

        with patch.object(settings, "GITHUB_PAT", "valid_pat"):
            result = runner.invoke(app, ["auth"])
            
            assert result.exit_code == 0
            assert "Authentication Successful" in result.output
            assert "@test_user" in result.output
            assert "repo, read:org" in result.output


def test_cli_history_renders_table(mock_analysis_result):
    """Verify history command retrieves records and displays them in a Rich table."""
    mock_session = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [mock_analysis_result]
    mock_session.execute.return_value = mock_execute_result

    with patch("pr_today.cli.get_session") as mock_get_session, \
         patch("pr_today.cli.init_db", new_callable=AsyncMock):
         
        # Use MagicMock for async context manager behavior
        mock_get_session.return_value.__aenter__.return_value = mock_session

        result = runner.invoke(app, ["history", "--limit", "5"])
        
        assert result.exit_code == 0
        assert "PRtoday Analysis History" in result.output
        assert "#42" in result.output
        assert "org/repo" in result.output


def test_cli_missing_github_pat_validation():
    """Verify that a missing GITHUB_PAT triggers a clean ValidationError exit rather than a traceback."""
    with patch.object(settings, "GITHUB_PAT", ""):
        result = runner.invoke(app, ["auth"])
        
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "GITHUB_PAT is not set" in result.output
