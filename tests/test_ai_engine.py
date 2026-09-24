"""Unit tests for the AIEngine."""

import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from pr_today.ai_engine import AIEngine, AIReview
from pr_today.risk_engine import RiskResult


@pytest.fixture
def dummy_risk_result() -> RiskResult:
    """Fixture containing a basic RiskResult."""
    return RiskResult(
        score=45,
        level="MEDIUM",
        breakdown={"volume_and_criticality": 50.0},
        blast_radius=["pr_today"],
        missing_tests=[],
    )


@pytest.mark.asyncio
async def test_ai_engine_success(dummy_risk_result):
    """Test that AIEngine returns structured review correctly when litellm succeeds."""
    engine = AIEngine()

    mock_choices = MagicMock()
    mock_choices.message.content = json.dumps(
        {
            "summary": "This PR implements new features.",
            "failure_scenarios": ["Scenario A", "Scenario B"],
            "reviewer_focus_areas": ["Focus A"],
        }
    )

    mock_response = MagicMock()
    mock_response.choices = [mock_choices]

    with patch("pr_today.ai_engine.AIEngine._call_litellm_with_retry", new_callable=AsyncMock, return_value=mock_response) as mock_completion:
        review = await engine.review("diff_content", dummy_risk_result)

        assert isinstance(review, AIReview)
        assert review.summary == "This PR implements new features."
        assert review.failure_scenarios == ["Scenario A", "Scenario B"]
        assert review.reviewer_focus_areas == ["Focus A"]
        mock_completion.assert_called_once()


@pytest.mark.asyncio
async def test_ai_engine_graceful_degradation_on_timeout(dummy_risk_result):
    """Test timeout exceptions inside litellm degrade gracefully to fallback review."""
    engine = AIEngine()

    with patch(
        "pr_today.ai_engine.AIEngine._call_litellm_with_retry", new_callable=AsyncMock, side_effect=Exception("Timeout error")
    ) as mock_completion:
        review = await engine.review("diff_content", dummy_risk_result)

        assert isinstance(review, AIReview)
        assert "AI review temporarily unavailable" in review.summary
        assert len(review.failure_scenarios) == 1
        assert "Unable to predict" in review.failure_scenarios[0]
        assert mock_completion.call_count >= 1


@pytest.mark.asyncio
async def test_ai_engine_prompt_integrity(dummy_risk_result):
    """Verify that system prompt constructed for litellm contains key integrity word 'reviewer'."""
    engine = AIEngine()
    mock_choices = MagicMock()
    mock_choices.message.content = json.dumps(
        {"summary": "summary", "failure_scenarios": [], "reviewer_focus_areas": []}
    )
    mock_response = MagicMock()
    mock_response.choices = [mock_choices]

    with patch("pr_today.ai_engine.AIEngine._call_litellm_with_retry", new_callable=AsyncMock, return_value=mock_response) as mock_completion:
        await engine.review("diff_content", dummy_risk_result)

        args, kwargs = mock_completion.call_args
        # _call_litellm_with_retry takes model, system_prompt, user_prompt
        system_msg = args[1] if len(args) > 1 else kwargs.get("system_prompt", "")

        assert "reviewer" in system_msg


