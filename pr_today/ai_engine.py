"""AI review engine for PRtoday using litellm."""

import json
import logging
from dataclasses import dataclass
from typing import List

import litellm

from pr_today.config import settings
from pr_today.risk_engine import RiskResult

logger = logging.getLogger("pr_today.ai_engine")


@dataclass
class AIReview:
    """Dataclass representing the result of an AI code review."""

    summary: str
    failure_scenarios: List[str]
    reviewer_focus_areas: List[str]


class AIEngine:
    """Engine to perform AI-assisted reviews of code diffs using litellm."""

    def review(self, diff: str, risk_result: RiskResult) -> AIReview:
        """Analyze a diff and risk metrics to generate structured code review feedback.

        Args:
            diff: The git diff of the PR.
            risk_result: The calculated RiskResult from the RiskEngine.

        Returns:
            An AIReview containing summary, failure scenarios, and focus areas.
        """
        logger.debug("Calling litellm with model: %s", settings.AI_MODEL)

        # Truncate diff to 6000 characters
        truncated_diff = diff[:6000]

        system_prompt = (
            "You are a senior code reviewer analyzing a pull request diff.\n"
            "Analyze the changes and identify potential failure scenarios, "
            "architectural issues, and focus areas for human reviewers.\n"
            "You must return your response in JSON format matching the schema:\n"
            "{\n"
            '  "summary": "A short paragraph summarizing the changes and main risks.",\n'
            '  "failure_scenarios": ["scenario 1", "scenario 2"],\n'
            '  "reviewer_focus_areas": ["area 1", "area 2"]\n'
            "}\n"
            "Ensure the output is valid JSON and nothing else."
        )

        user_prompt = (
            f"Repository Risk Score: {risk_result.score}/100\n"
            f"Risk Level: {risk_result.level}\n"
            f"Blast Radius: {', '.join(risk_result.blast_radius)}\n\n"
            f"Diff:\n{truncated_diff}"
        )

        try:
            # Set API keys in litellm if configured in settings
            if settings.GEMINI_API_KEY:
                litellm.gemini_api_key = settings.GEMINI_API_KEY
            if settings.OPENAI_API_KEY:
                litellm.openai_api_key = settings.OPENAI_API_KEY
            if settings.HF_TOKEN:
                litellm.api_key = settings.HF_TOKEN

            response = litellm.completion(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                timeout=30,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Received empty response from AI model.")

            data = json.loads(content)
            return AIReview(
                summary=data.get("summary", "No summary provided."),
                failure_scenarios=data.get("failure_scenarios", []),
                reviewer_focus_areas=data.get("reviewer_focus_areas", []),
            )

        except Exception as e:
            logger.error("AI review failed: %s", str(e), exc_info=True)
            return AIReview(
                summary=f"AI review temporarily unavailable (degraded state: {str(e)}).",
                failure_scenarios=[
                    "Unable to predict failure scenarios due to system error."
                ],
                reviewer_focus_areas=[
                    "Inspect diff manually for edge cases and correctness."
                ],
            )
