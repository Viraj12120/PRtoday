"""Orchestrator coordinating PR analysis workflow in PRtoday."""

import asyncio
import logging
from typing import List

import httpx
from github import BadCredentialsException, Github, RateLimitExceededException, UnknownObjectException
from sqlalchemy.future import select

from pr_today.ai_engine import AIEngine, AIReview
from pr_today.config import settings
from pr_today.database import get_session
from pr_today.models import AnalysisResult
from pr_today.risk_engine import RiskEngine, RiskResult

logger = logging.getLogger("pr_today.orchestrator")


class OrchestratorError(Exception):
    """Base exception for errors during Orchestrator execution."""
    pass


class Orchestrator:
    """Coordinates fetching data, running analysis engines, and persisting results."""

    def __init__(self) -> None:
        self.risk_engine = RiskEngine()
        self.ai_engine = AIEngine()

    async def run(self, repo: str, pr_number: int, no_ai: bool = False) -> AnalysisResult:
        """Execute the full PR risk analysis workflow.

        Args:
            repo: Repo in 'owner/repo' format.
            pr_number: Pull request ID.
            no_ai: Flag to skip AI review logic.

        Returns:
            The persisted AnalysisResult DB model instance.
        """
        logger.info("Starting analysis for %s PR #%d", repo, pr_number)

        # 1. Fetch metadata and diff from GitHub
        pr_metadata, diff_content = await self._fetch_github_data(repo, pr_number)

        # 2. Run deterministic RiskEngine
        logger.info("Running deterministic risk scorer...")
        risk_result = self.risk_engine.analyze(diff_content, pr_metadata["files"])

        # 3. Run AIEngine (if not disabled)
        ai_result: AIReview
        if no_ai:
            logger.info("AI review disabled, skipping AI analysis.")
            ai_result = AIReview(
                summary=None,  # type: ignore
                failure_scenarios=[],
                reviewer_focus_areas=[],
            )
        else:
            logger.info("Running AI review engine...")
            ai_result = self.ai_engine.review(diff_content, risk_result)

        # 4. Save to local SQLite database
        logger.info("Persisting analysis result to database...")
        result_model = AnalysisResult(
            repo=repo,
            pr_number=pr_number,
            risk_score=risk_result.score,
            risk_level=risk_result.level,
            blast_radius=risk_result.blast_radius,
            missing_tests=risk_result.missing_tests,
            ai_summary=ai_result.summary,
            ai_failures=ai_result.failure_scenarios,
            ai_focus_areas=ai_result.reviewer_focus_areas,
            files_changed=pr_metadata["files"],
            db_migrations_detected=risk_result.breakdown["db_migrations"] > 0,
            config_changes_detected=risk_result.breakdown["config_changes"] > 0,
            dependency_changes_detected=risk_result.breakdown["dependency_shifts"] > 0,
        )

        async with get_session() as session:
            session.add(result_model)
            # Ensure attributes are loaded before session context finishes committing
            await session.flush()
            # Refresh to ensure ID and timestamps are populated from SQLite
            await session.refresh(result_model)

        logger.info("Analysis completed successfully for %s PR #%d", repo, pr_number)
        return result_model

    async def _fetch_github_data(self, repo: str, pr_number: int) -> tuple[dict, str]:
        """Fetch metadata and diff content from GitHub with rate limit retries."""
        g = Github(settings.GITHUB_PAT)

        # Step 1: Fetch PR metadata using PyGithub (with retry once on rate limit)
        retries = 1
        while True:
            try:
                repo_obj = g.get_repo(repo)
                pr_obj = repo_obj.get_pull(pr_number)
                
                # Fetch files changed
                changed_files = [f.filename for f in pr_obj.get_files()]
                
                pr_metadata = {
                    "title": pr_obj.title,
                    "author": pr_obj.user.login,
                    "files": changed_files,
                }
                break
            except RateLimitExceededException:
                if retries > 0:
                    logger.warning("GitHub API rate limit exceeded. Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    retries -= 1
                    continue
                raise OrchestratorError("GitHub API rate limit exceeded. Please try again later.")
            except BadCredentialsException:
                raise OrchestratorError("Invalid GitHub Personal Access Token (GITHUB_PAT).")
            except UnknownObjectException:
                raise OrchestratorError(f"Repository '{repo}' or PR #{pr_number} not found on GitHub.")
            except Exception as e:
                raise OrchestratorError(f"GitHub client error: {str(e)}")

        # Step 2: Fetch PR diff using httpx
        headers = {
            "Authorization": f"token {settings.GITHUB_PAT}",
            "Accept": "application/vnd.github.v3.diff",
        }
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 401:
                    raise OrchestratorError("Invalid GitHub Personal Access Token (GITHUB_PAT) when fetching diff.")
                elif response.status_code == 404:
                    raise OrchestratorError(f"Diff not found for PR #{pr_number}.")
                response.raise_for_status()
                diff_content = response.text
        except httpx.HTTPError as he:
            raise OrchestratorError(f"HTTP error fetching diff from GitHub: {str(he)}")
        except Exception as e:
            raise OrchestratorError(f"Unexpected error fetching diff: {str(e)}")

        return pr_metadata, diff_content
