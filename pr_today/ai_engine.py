"""AI review engine for PRtoday using litellm."""

import hashlib
import json
import logging
import re
import time
from typing import List, Optional

import litellm
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from pr_today import cache
from pr_today.config import settings
from pr_today.prompts import PROMPT_VERSION, SYSTEM_PROMPT_V2, USER_PROMPT_TEMPLATE_V2
from pr_today.risk_engine import RiskResult

logger = logging.getLogger("pr_today.ai_engine")


class AIReview(BaseModel):
    """Pydantic model representing the result of an AI code review."""

    summary: str = Field(default="No summary provided.")
    change_classification: str = Field(default="UNKNOWN")
    architectural_impact: str = Field(default="Not assessed.")
    failure_scenarios: List[str] = Field(default_factory=list)
    reviewer_focus_areas: List[str] = Field(default_factory=list)
    security_notes: str = Field(default="Not assessed.")
    testing_gaps: str = Field(default="Not assessed.")

    # AI Metrics
    ai_tokens_prompt: Optional[int] = None
    ai_tokens_completion: Optional[int] = None
    ai_cost_usd: Optional[float] = None
    ai_latency_ms: Optional[int] = None
    ai_model_used: Optional[str] = None
    confidence_score: int = Field(default=100)


class AIEngine:
    """Engine to perform AI-assisted reviews of code diffs using litellm."""

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
    async def _call_litellm_with_retry(
        self, model: str, system_prompt: str, user_prompt: str
    ) -> litellm.ModelResponse:
        return await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            timeout=30,
        )

    async def review(
        self,
        diff: str,
        risk_result: RiskResult,
        sast_findings: list = None,
        ast_context: str = None,
        ci_status: str = None,
    ) -> AIReview:
        """Analyze a diff and risk metrics to generate structured code review feedback."""
        logger.debug("Calling litellm with model: %s", settings.AI_MODEL)

        try:
            info = litellm.get_model_info(settings.AI_MODEL)
            max_tokens = info.get("max_tokens", 4000)
        except Exception:
            max_tokens = 4000

        # Reserve 1000 tokens for system prompt and output; approx 4 chars per token
        max_chars = max(1000, (max_tokens - 1000) * 4)
        is_truncated = len(diff) > max_chars
        truncated_diff = self._smart_truncate_diff(diff, max_chars)

        # Count diff stats for richer context
        lines_added = sum(
            1
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        lines_removed = sum(
            1
            for line in diff.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )

        system_prompt = SYSTEM_PROMPT_V2
        user_prompt = USER_PROMPT_TEMPLATE_V2.format(
            score=risk_result.score,
            level=risk_result.level,
            blast_radius=", ".join(risk_result.blast_radius),
            file_count=len(risk_result.blast_radius),
            lines_added=lines_added,
            lines_removed=lines_removed,
            ci_status=ci_status or "CI status unavailable.",
            sast_findings=(
                json.dumps(sast_findings, indent=2)
                if sast_findings
                else "No SAST findings detected."
            ),
            ast_context=ast_context or "AST context unavailable.",
            truncated_diff=truncated_diff,
        )

        # Check cache first
        cache_key = None
        try:
            diff_hash = hashlib.sha256(truncated_diff.encode("utf-8")).hexdigest()
            cache_key = (
                f"pr_today:ai_cache:{PROMPT_VERSION}:{settings.AI_MODEL}:{diff_hash}"
            )
            redis_client = await cache.get_redis()
            if redis_client:
                cached_res = await redis_client.get(cache_key)
                if cached_res:
                    logger.info("AI review cache hit for key: %s", cache_key)
                    return AIReview.model_validate_json(cached_res)
        except Exception as e:
            logger.warning("Failed to read from cache: %s", str(e))

        start_time = time.monotonic()
        try:
            # Set API keys in litellm if configured in settings
            if settings.GEMINI_API_KEY:
                litellm.gemini_api_key = settings.GEMINI_API_KEY
            if settings.OPENAI_API_KEY:
                litellm.openai_api_key = settings.OPENAI_API_KEY
            if settings.HF_TOKEN:
                litellm.api_key = settings.HF_TOKEN

            used_model = settings.AI_MODEL
            fallback_used = False
            try:
                response = await self._call_litellm_with_retry(
                    settings.AI_MODEL, system_prompt, user_prompt
                )
            except Exception as e:
                logger.warning("Primary model failed: %s", str(e))
                if settings.AI_FALLBACK_MODEL:
                    logger.info("Trying fallback model: %s", settings.AI_FALLBACK_MODEL)
                    used_model = settings.AI_FALLBACK_MODEL
                    fallback_used = True
                    response = await self._call_litellm_with_retry(
                        settings.AI_FALLBACK_MODEL, system_prompt, user_prompt
                    )
                else:
                    raise

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Received empty response from AI model.")

            cost = None
            try:
                cost = litellm.completion_cost(completion_response=response)
                if cost:
                    logger.debug("AI Request cost: $%.6f", cost)
                    if (
                        settings.AI_MAX_COST_PER_REQUEST
                        and cost > settings.AI_MAX_COST_PER_REQUEST
                    ):
                        logger.warning(
                            "Cost exceeded max allowed limit: %s > %s",
                            cost,
                            settings.AI_MAX_COST_PER_REQUEST,
                        )
            except Exception as e:
                logger.debug("Could not calculate AI cost: %s", str(e))

            tokens_prompt = None
            tokens_completion = None
            if hasattr(response, "usage") and response.usage:
                tokens_prompt = response.usage.prompt_tokens
                tokens_completion = response.usage.completion_tokens
                logger.debug(
                    "Tokens - Prompt: %s, Completion: %s",
                    tokens_prompt,
                    tokens_completion,
                )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Calculate Confidence Score based on truncation, volume, and fallback
            confidence = 100
            if is_truncated:
                excess = len(diff) - max_chars
                penalty = min(30, int((excess / 1000) * 5))  # Up to 30% penalty
                confidence -= penalty
            if lines_added + lines_removed > 1000:
                penalty = min(20, int(((lines_added + lines_removed - 1000) / 100) * 2))
                confidence -= penalty
            if fallback_used:
                confidence -= 15
            confidence = max(0, min(100, confidence))

            review_obj = AIReview.model_validate_json(content)
            review_obj.ai_tokens_prompt = tokens_prompt
            review_obj.ai_tokens_completion = tokens_completion
            review_obj.ai_cost_usd = cost
            review_obj.ai_latency_ms = latency_ms
            review_obj.ai_model_used = used_model
            review_obj.confidence_score = confidence

            # Save to cache
            if cache_key:
                try:
                    redis_client = await cache.get_redis()
                    if redis_client:
                        await redis_client.setex(
                            cache_key,
                            settings.AI_CACHE_TTL_SECONDS,
                            review_obj.model_dump_json(),
                        )
                except Exception as e:
                    logger.warning("Failed to write to cache: %s", str(e))

            return review_obj

        except Exception as e:
            error_msg = str(e)
            if "RetryError" in error_msg and hasattr(e, "last_attempt"):
                try:
                    error_msg = str(e.last_attempt.exception().__class__.__name__)
                except:
                    pass

            logger.error("AI review failed after retries: %s", error_msg)
            return AIReview(
                summary=f"AI review temporarily unavailable (degraded state: {error_msg}).",
                failure_scenarios=[
                    "Unable to predict failure scenarios due to system error."
                ],
                reviewer_focus_areas=[
                    "Inspect diff manually for edge cases and correctness."
                ],
                ai_latency_ms=int((time.monotonic() - start_time) * 1000),
                confidence_score=0,
            )

    def _smart_truncate_diff(self, diff: str, max_chars: int) -> str:
        """Intelligently truncate a diff by prioritizing high-risk files."""
        if len(diff) <= max_chars:
            return diff

        # Split the diff into file blocks
        blocks = re.split(r"(^diff --git )", diff, flags=re.MULTILINE)

        if len(blocks) < 3:
            return diff[:max_chars]

        file_chunks = []

        # Iterate through blocks in pairs of (delimiter, content)
        for i in range(1, len(blocks), 2):
            chunk = blocks[i] + blocks[i + 1]

            # Determine filename to score it
            filename = ""
            match = re.search(r"^a/(.*?)\s+b/", blocks[i + 1])
            if match:
                filename = match.group(1)

            # Score chunk
            score = 0
            filename_lower = filename.lower()
            if "migration" in filename_lower or "alembic" in filename_lower:
                score = 100
            elif (
                ".env" in filename_lower
                or "settings" in filename_lower
                or filename_lower.endswith((".yml", ".yaml", ".toml"))
            ):
                score = 90
            elif filename_lower in (
                "requirements.txt",
                "pyproject.toml",
                "package.json",
                "go.mod",
            ):
                score = 80
            elif filename_lower.endswith(
                (".py", ".js", ".ts", ".go", ".java", ".rs", ".cpp", ".c")
            ):
                score = 50
            else:
                score = 10

            file_chunks.append((score, chunk))

        # Sort chunks by score descending
        file_chunks.sort(key=lambda x: x[0], reverse=True)

        truncated = blocks[0]  # Add prefix if any (usually empty)
        for score, chunk in file_chunks:
            if len(truncated) + len(chunk) <= max_chars:
                truncated += chunk
            else:
                remaining = max_chars - len(truncated)
                if remaining > 500:
                    truncated += (
                        chunk[:remaining]
                        + "\n...[DIFF TRUNCATED DUE TO TOKEN LIMITS]..."
                    )
                break

        return truncated
