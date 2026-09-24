import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pr_today.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_orchestrator_run_success():
    with patch("pr_today.orchestrator.Github") as mock_github, \
         patch("pr_today.orchestrator.RiskEngine.analyze") as mock_analyze, \
         patch("pr_today.orchestrator.AIEngine.review", new_callable=AsyncMock) as mock_review, \
         patch("pr_today.orchestrator.get_session") as mock_get_session, \
         patch("pr_today.orchestrator.httpx.AsyncClient") as mock_client:
         
        # Setup mocks
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_user = MagicMock()
        mock_user.login = "testuser"
        mock_pr.user = mock_user
        mock_pr.title = "Test PR"
        mock_repo.get_pull.return_value = mock_pr
        mock_github.return_value.get_repo.return_value = mock_repo
        
        mock_file = MagicMock()
        mock_file.filename = "a.py"
        mock_file.patch = "diff content"
        mock_pr.get_files.return_value = [mock_file]
        
        mock_risk_result = MagicMock()
        mock_risk_result.score = 50
        mock_risk_result.level = "MEDIUM"
        mock_risk_result.breakdown = {
            "db_migrations": 0,
            "config_changes": 0,
            "dependency_shifts": 0,
        }
        mock_risk_result.blast_radius = []
        mock_risk_result.missing_tests = []
        mock_analyze.return_value = mock_risk_result
        
        mock_ai_review = MagicMock()
        mock_ai_review.summary = "summary"
        mock_ai_review.failure_scenarios = []
        mock_ai_review.reviewer_focus_areas = []
        mock_review.return_value = mock_ai_review
        
        mock_session = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "diff content"
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        orchestrator = Orchestrator()
        result = await orchestrator.run("org/repo", 1, no_ai=False)
        
        assert result.repo == "org/repo"
        assert result.pr_number == 1
        assert result.risk_score == 50
        assert result.risk_level == "MEDIUM"
        assert result.ai_summary == "summary"

@pytest.mark.asyncio
async def test_orchestrator_run_no_ai():
    with patch("pr_today.orchestrator.Github") as mock_github, \
         patch("pr_today.orchestrator.RiskEngine.analyze") as mock_analyze, \
         patch("pr_today.orchestrator.get_session") as mock_get_session, \
         patch("pr_today.orchestrator.httpx.AsyncClient") as mock_client:
         
        # Setup mocks
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_user = MagicMock()
        mock_user.login = "testuser"
        mock_pr.user = mock_user
        mock_pr.title = "Test PR"
        mock_repo.get_pull.return_value = mock_pr
        mock_github.return_value.get_repo.return_value = mock_repo
        
        mock_file = MagicMock()
        mock_file.filename = "a.py"
        mock_file.patch = "diff content"
        mock_pr.get_files.return_value = [mock_file]
        
        mock_risk_result = MagicMock()
        mock_risk_result.score = 50
        mock_risk_result.level = "MEDIUM"
        mock_risk_result.breakdown = {
            "db_migrations": 0,
            "config_changes": 0,
            "dependency_shifts": 0,
        }
        mock_risk_result.blast_radius = []
        mock_risk_result.missing_tests = []
        mock_analyze.return_value = mock_risk_result
        
        mock_session = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "diff content"
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        orchestrator = Orchestrator()
        result = await orchestrator.run("org/repo", 1, no_ai=True)
        
        assert result.repo == "org/repo"
        assert result.pr_number == 1
        assert result.ai_summary == "AI review disabled."
