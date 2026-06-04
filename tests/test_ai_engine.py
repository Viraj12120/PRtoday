"""Unit tests for the AIEngine."""

import json
from unittest.mock import MagicMock, patch

import litellm
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


def test_ai_engine_success(dummy_risk_result):
    """Test that AIEngine returns structured review correctly when litellm succeeds."""
    engine = AIEngine()
    
    mock_choices = MagicMock()
    mock_choices.message.content = json.dumps({
        "summary": "This PR implements new features.",
        "failure_scenarios": ["Scenario A", "Scenario B"],
        "reviewer_focus_areas": ["Focus A"]
    })
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choices]

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        review = engine.review("diff_content", dummy_risk_result)
        
        assert isinstance(review, AIReview)
        assert review.summary == "This PR implements new features."
        assert review.failure_scenarios == ["Scenario A", "Scenario B"]
        assert review.reviewer_focus_areas == ["Focus A"]
        mock_completion.assert_called_once()


def test_ai_engine_graceful_degradation_on_timeout(dummy_risk_result):
    """Test timeout exceptions inside litellm degrade gracefully to fallback review."""
    engine = AIEngine()

    with patch("litellm.completion", side_effect=Exception("Timeout error")) as mock_completion:
        review = engine.review("diff_content", dummy_risk_result)
        
        assert isinstance(review, AIReview)
        assert "AI review temporarily unavailable" in review.summary
        assert len(review.failure_scenarios) == 1
        assert "Unable to predict" in review.failure_scenarios[0]
        mock_completion.assert_called_once()


def test_ai_engine_prompt_integrity(dummy_risk_result):
    """Verify that system prompt constructed for litellm contains key integrity word 'reviewer'."""
    engine = AIEngine()
    mock_choices = MagicMock()
    mock_choices.message.content = json.dumps({
        "summary": "summary",
        "failure_scenarios": [],
        "reviewer_focus_areas": []
    })
    mock_response = MagicMock()
    mock_response.choices = [mock_choices]

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        engine.review("diff_content", dummy_risk_result)
        
        kwargs = mock_completion.call_args[1]
        messages = kwargs["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")["content"]
        
        assert "reviewer" in system_msg


def test_ai_engine_truncates_diff(dummy_risk_result):
    """Verify that diff is truncated to 6000 chars before calling litellm."""
    engine = AIEngine()
    mock_choices = MagicMock()
    mock_choices.message.content = json.dumps({
        "summary": "summary",
        "failure_scenarios": [],
        "reviewer_focus_areas": []
    })
    mock_response = MagicMock()
    mock_response.choices = [mock_choices]

    long_diff = "A" * 10000

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        engine.review(long_diff, dummy_risk_result)
        
        kwargs = mock_completion.call_args[1]
        messages = kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")["content"]
        
        # Extracted user diff should be max 6000 + some metadata header characters
        assert len(long_diff) > 6000
        # The prompt should contain a truncated diff
        assert "A" * 6000 in user_msg
        assert "A" * 6001 not in user_msg
