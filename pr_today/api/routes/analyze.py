"""POST /analyze route — triggers PR risk analysis via the existing engine."""

import logging

from fastapi import APIRouter, HTTPException

from pr_today.api.schemas import AnalyzeRequest, AnalyzeResponse
from pr_today.services.risk_engine_service import analyze_pr

logger = logging.getLogger("pr_today.api.routes.analyze")

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
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
        raise HTTPException(status_code=422, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except LookupError as le:
        raise HTTPException(status_code=404, detail=str(le))
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
