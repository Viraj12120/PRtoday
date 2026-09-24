"""POST /analyze route — triggers PR risk analysis via the existing engine."""

import logging

from fastapi import APIRouter, Depends

from pr_today.api.errors import GitHubAuthError, PRNotFoundError, PRTodayAPIError
from pr_today.api.middleware.auth import verify_api_key
from pr_today.api.schemas import AnalyzeRequest, AnalyzeResponse
from pr_today.services.risk_engine_service import analyze_pr

logger = logging.getLogger("pr_today.api.routes.analyze")

router = APIRouter()


@router.post(
    "/analyze", response_model=AnalyzeResponse, dependencies=[Depends(verify_api_key)]
)
async def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a pull request and return risk assessment.

    Delegates to the existing Orchestrator → RiskEngine → AIEngine pipeline.
    Results are persisted to the database and cached in Redis.
    """
    logger.info(
        "Analyze request: repo=%s pr=#%d user=%s",
        request.repo,
        request.pr_number,
        request.user_id,
    )

    try:
        result = await analyze_pr(
            repo=request.repo,
            pr_number=request.pr_number,
            user_id=request.user_id,
        )
        return result
    except ValueError as ve:
        raise PRTodayAPIError(message=str(ve), status_code=422)
    except PermissionError as pe:
        raise GitHubAuthError(message=str(pe))
    except LookupError:
        raise PRNotFoundError(repo=request.repo, pr_number=request.pr_number)
