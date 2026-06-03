import pytest
from unittest import mock
import os
from pr_sentinel.ai import AiClient, AiReviewReport


def test_ai_client_no_token_fallback():
    # Clear tokens from environment for isolated test
    with mock.patch.dict(os.environ, {}, clear=True), mock.patch("pr_sentinel.ai.get_token", return_value=None):
        client = AiClient(token=None)
        assert not client._has_key()

        files = [
            {"filename": "db/migrations/001_init.sql", "additions": 10, "deletions": 0},
            {"filename": "pr_sentinel/auth.py", "additions": 5, "deletions": 2}
        ]
        report = client.generate_review(files)
        
        assert "AI review is offline" in report.summary
        assert report.error == "API token/credentials not configured."
        assert any("Database" in s for s in report.failure_scenarios)
        assert any("Authentication" in s for s in report.failure_scenarios)


@mock.patch("litellm.completion")
def test_ai_client_success(mock_completion):
    # Mock litellm completion response
    mock_response = mock.MagicMock()
    mock_response.choices = [
        mock.MagicMock(
            message=mock.MagicMock(
                content=json_response_content()
            )
        )
    ]
    mock_completion.return_value = mock_response

    client = AiClient(token="fake_token")
    files = [{"filename": "main.py", "additions": 20, "deletions": 10, "patch": "diff content"}]
    
    report = client.generate_review(files)
    
    assert report.summary == "This PR modifies the main function to handle errors."
    assert "regression" in report.failure_scenarios[0]
    assert "main.py" in report.reviewer_focus[0]
    assert "test main" in report.suggested_tests[0]
    assert report.error is None


@mock.patch("litellm.completion")
def test_ai_client_api_failure_fallback(mock_completion):
    mock_completion.side_effect = Exception("API rate limit exceeded")

    client = AiClient(token="fake_token")
    files = [{"filename": "main.py", "additions": 2, "deletions": 1}]
    
    report = client.generate_review(files)
    
    assert "AI review is offline" in report.summary
    assert report.error == "API rate limit exceeded"
    assert len(report.failure_scenarios) > 0


def json_response_content() -> str:
    return """
    {
        "summary": "This PR modifies the main function to handle errors.",
        "failure_scenarios": ["Potential regression in error handler"],
        "reviewer_focus": ["main.py: line 42"],
        "suggested_tests": ["Write a unit test for test main with invalid inputs"]
    }
    """
