import pytest
from typer.testing import CliRunner
from unittest import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pr_sentinel.cli import app
from pr_sentinel.db import Base

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup isolated in-memory database during integration testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with mock.patch("pr_sentinel.db.engine", test_engine), \
         mock.patch("pr_sentinel.db.SessionLocal", TestSessionLocal):
        yield


@mock.patch("pr_sentinel.github.GithubClient.get_pr_files")
@mock.patch("pr_sentinel.github.GithubClient.get_pull_request")
@mock.patch("litellm.completion")
@mock.patch("pr_sentinel.github.get_github_token", return_value="fake_token")
def test_analyze_e2e_flow(mock_get_token, mock_completion, mock_get_pr, mock_get_files):
    # Mock GitHub Client responses
    mock_pr = mock.Mock()
    mock_pr.title = "CI Infrastructure Refactoring"
    mock_get_pr.return_value = mock_pr

    mock_get_files.return_value = [
        {"filename": "Dockerfile", "additions": 10, "deletions": 2, "patch": "@@ -1,3 +1,5 @@"},
        {"filename": "src/app.py", "additions": 50, "deletions": 10, "patch": "@@ -1,5 +1,9 @@"}
    ]

    # Mock LiteLLM response
    mock_response = mock.Mock()
    mock_response.choices = [
        mock.Mock(
            message=mock.Mock(
                content='{"summary": "Refactors CI workflow.", "failure_scenarios": [], "reviewer_focus": [], "suggested_tests": []}'
            )
        )
    ]
    mock_completion.return_value = mock_response

    # Execute analyze command
    result = runner.invoke(app, ["analyze", "--repo", "org/repo", "--pr", "12"])

    # Assert CLI executed successfully
    assert result.exit_code == 0
    assert "PR Information" in result.stdout
    assert "Risk Score" in result.stdout
    assert "Test Coverage" in result.stdout

    # Execute history command to verify the analysis run was persisted
    history_result = runner.invoke(app, ["history"])
    assert history_result.exit_code == 0
    assert "CI" in history_result.stdout
    assert "Infrastructure" in history_result.stdout

