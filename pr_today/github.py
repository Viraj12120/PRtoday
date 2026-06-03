from typing import Optional, List, Dict, Any
from github import Github, Auth
from github.PullRequest import PullRequest
from pr_sentinel.auth import get_github_token

class GithubClientError(Exception):
    pass

class GithubClient:
    def __init__(self, token: Optional[str] = None):
        auth_token = token or get_github_token()
        if not auth_token:
            raise GithubClientError("GitHub token not found. Please run 'pr-sentinel auth' or set GITHUB_PAT.")
        
        self.auth = Auth.Token(auth_token)
        self.client = Github(auth=self.auth)

    def get_pull_request(self, repo_name: str, pr_number: int) -> PullRequest:
        try:
            repo = self.client.get_repo(repo_name)
            return repo.get_pull(pr_number)
        except Exception as e:
            raise GithubClientError(f"Failed to fetch PR {pr_number} from {repo_name}: {str(e)}")

    def get_pr_files(self, repo_name: str, pr_number: int) -> List[Dict[str, Any]]:
        pr = self.get_pull_request(repo_name, pr_number)
        files = []
        for file in pr.get_files():
            files.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch
            })
        return files
