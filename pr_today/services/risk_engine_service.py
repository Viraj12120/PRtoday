"""Risk engine service — async wrapper around the existing Orchestrator.

This is the bridge between the FastAPI routes and the existing risk engine.
It does NOT modify any risk scoring logic. It wraps, caches, and reshapes.
"""

import hashlib
import json
import logging
from typing import Optional

from pr_today.api.schemas import AnalyzeResponse
from pr_today.orchestrator import Orchestrator, OrchestratorError

logger = logging.getLogger("pr_today.services.risk_engine_service")

# Cache TTL: 10 minutes for analysis results
CACHE_TTL_SECONDS = 600


def _cache_key(repo: str, pr_number: int) -> str:
    """Generate a deterministic Redis cache key for a PR analysis."""
    raw = f"pr_today:analysis:{repo}:{pr_number}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _extract_security_findings(
    config_detected: bool,
    breakdown: dict,
    files: list[str],
) -> list[str]:
    """Derive security findings from the risk engine's config/secret detection.

    The risk engine flags config_changes when it finds patterns like
    api_key, secret_key, password, token, auth_token in the diff.
    We surface those as explicit security findings.
    """
    findings: list[str] = []

    if config_detected:
        findings.append(
            "Configuration or secret-related changes detected in this PR. "
            "Review for leaked credentials, API keys, or tokens."
        )

    # Check for specific sensitive file patterns
    sensitive_patterns = [".env", "secrets", "credentials", "key"]
    for f in files:
        f_lower = f.lower()
        for pattern in sensitive_patterns:
            if pattern in f_lower:
                findings.append(f"Sensitive file modified: {f}")
                break

    if breakdown.get("config_changes", 0) > 0:
        findings.append(
            "Risk engine scored config_changes > 0: "
            "secrets or configuration patterns found in diff."
        )

    return findings


async def _get_cached_result(
    repo: str, pr_number: int
) -> Optional[AnalyzeResponse]:
    """Attempt to retrieve a cached analysis result from Redis."""
    try:
        from pr_today.api.main import get_redis

        redis_client = await get_redis()
        if redis_client is None:
            return None

        key = _cache_key(repo, pr_number)
        cached = await redis_client.get(key)
        if cached:
            logger.info("Cache hit for %s PR #%d", repo, pr_number)
            data = json.loads(cached)
            return AnalyzeResponse(**data)
    except Exception as e:
        logger.warning("Redis cache read failed: %s", e)
    return None


async def _set_cached_result(
    repo: str, pr_number: int, response: AnalyzeResponse
) -> None:
    """Store an analysis result in Redis with TTL."""
    try:
        from pr_today.api.main import get_redis

        redis_client = await get_redis()
        if redis_client is None:
            return

        key = _cache_key(repo, pr_number)
        await redis_client.setex(key, CACHE_TTL_SECONDS, response.model_dump_json())
        logger.info("Cached result for %s PR #%d (TTL=%ds)", repo, pr_number, CACHE_TTL_SECONDS)
    except Exception as e:
        logger.warning("Redis cache write failed: %s", e)


async def analyze_pr(
    repo: str,
    pr_number: int,
    user_id: str,
) -> AnalyzeResponse:
    """Run the full PR analysis pipeline and return an API response.

    1. Check Redis cache for existing result
    2. Delegate to Orchestrator.run() (which calls RiskEngine + AIEngine)
    3. Extract security findings from breakdown
    4. Cache the result in Redis
    5. Return the shaped AnalyzeResponse

    The existing risk_engine.py and orchestrator.py are called UNCHANGED.
    """
    # 1. Check cache
    cached = await _get_cached_result(repo, pr_number)
    if cached is not None:
        return cached

    # 2. Run the orchestrator (wraps RiskEngine + AIEngine)
    orchestrator = Orchestrator()
    try:
        result = await orchestrator.run(repo, pr_number)
    except OrchestratorError as e:
        error_msg = str(e)
        if "Invalid GitHub Personal Access Token" in error_msg:
            raise PermissionError(error_msg)
        elif "not found" in error_msg.lower():
            raise LookupError(error_msg)
        else:
            raise

    # 3. Extract security findings
    breakdown = {
        "config_changes": 1.0 if result.config_changes_detected else 0.0,
    }
    security_findings = _extract_security_findings(
        config_detected=result.config_changes_detected,
        breakdown=breakdown,
        files=result.files_changed,
    )

    # Also persist security_findings back to the DB record
    try:
        from pr_today.database import get_session

        async with get_session() as session:
            from sqlalchemy import update
            from pr_today.models import AnalysisResult

            await session.execute(
                update(AnalysisResult)
                .where(AnalysisResult.id == result.id)
                .values(
                    security_findings=security_findings,
                    blast_radius_json={
                        "modules": result.blast_radius,
                        "files_count": len(result.files_changed),
                    },
                )
            )
    except Exception as e:
        logger.warning("Failed to update security_findings in DB: %s", e)

    # 4. Build response
    response = AnalyzeResponse(
        risk_score=result.risk_score,
        blast_radius=result.blast_radius,
        files_changed=result.files_changed,
        ai_summary=result.ai_summary,
        security_findings=security_findings,
    )

    # 5. Cache in Redis
    await _set_cached_result(repo, pr_number, response)

    logger.info(
        "Analysis complete: repo=%s pr=#%d score=%d user=%s",
        repo,
        pr_number,
        result.risk_score,
        user_id,
    )
    return response
