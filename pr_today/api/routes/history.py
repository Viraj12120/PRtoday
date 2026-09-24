"""GET /history route — retrieve past analysis results."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from pr_today.api.middleware.auth import verify_api_key
from pr_today.api.schemas import HistoryItem, HistoryResponse
from pr_today.database import get_session
from pr_today.models import AnalysisResult

logger = logging.getLogger("pr_today.api.routes.history")

router = APIRouter()


@router.get(
    "/history", response_model=HistoryResponse, dependencies=[Depends(verify_api_key)]
)
async def history_endpoint(
    repo: Optional[str] = Query(None, description="Filter by repository (owner/name)."),
    limit: int = Query(20, ge=1, le=100, description="Max results to return."),
    cursor: Optional[int] = Query(
        None, description="Cursor for pagination (last seen ID)."
    ),
) -> HistoryResponse:
    """Retrieve historical PR analysis results, optionally filtered by repo."""
    logger.info("History request: repo=%s limit=%d cursor=%s", repo, limit, cursor)

    async with get_session() as session:
        # We order by ID desc instead of created_at desc to make cursor pagination reliable
        stmt = select(AnalysisResult).order_by(AnalysisResult.id.desc())

        if cursor is not None:
            stmt = stmt.where(AnalysisResult.id < cursor)

        if repo:
            stmt = stmt.where(AnalysisResult.repo == repo)

        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        records = list(result.scalars().all())

    items = [
        HistoryItem(
            id=r.id,
            repo=r.repo,
            pr_number=r.pr_number,
            risk_score=r.risk_score,
            risk_level=r.risk_level,
            blast_radius=r.blast_radius,
            files_changed=r.files_changed,
            ai_summary=r.ai_summary,
            security_findings=r.security_findings if r.security_findings else [],
            created_at=r.created_at,
        )
        for r in records
    ]

    next_cursor = items[-1].id if len(items) == limit else None

    return HistoryResponse(count=len(items), results=items, next_cursor=next_cursor)
