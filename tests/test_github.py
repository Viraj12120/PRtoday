import pytest
from unittest import mock
from pr_sentinel.github import GithubClient, GithubClientError

@mock.patch('pr_sentinel.github.get_github_token')
def test_github_client_no_token(mock_get_token):
    mock_get_token.return_value = None
    with pytest.raises(GithubClientError) as exc:
        GithubClient()
    assert "GitHub token not found" in str(exc.value)

@mock.patch('pr_sentinel.github.Github')
@mock.patch('pr_sentinel.github.get_github_token')
def test_get_pull_request(mock_get_token, mock_github_class):
    mock_get_token.return_value = "fake_token"
    
    # Setup mock github instance
    mock_gh_instance = mock.Mock()
    mock_github_class.return_value = mock_gh_instance
    mock_repo = mock.Mock()
    mock_gh_instance.get_repo.return_value = mock_repo
    mock_pr = mock.Mock()
    mock_pr.title = "Test PR"
    mock_repo.get_pull.return_value = mock_pr
    
    client = GithubClient()
    pr = client.get_pull_request("org/repo", 1)
    
    assert pr.title == "Test PR"
    mock_gh_instance.get_repo.assert_called_with("org/repo")
    mock_repo.get_pull.assert_called_with(1)
