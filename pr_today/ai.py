"""
PR Today - AI Review Engine.

Integrates with multi-provider models using LiteLLM to generate change summaries,
predict failure scenarios, and suggest test improvements.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import litellm
from pr_today.auth import get_token

logger = logging.getLogger("pr_today.ai")


@dataclass
class AiReviewReport:
    """The AI-generated review report for a PR."""
    summary: str = ""
    failure_scenarios: List[str] = field(default_factory=list)
    reviewer_focus: List[str] = field(default_factory=list)
    suggested_tests: List[str] = field(default_factory=list)
    error: Optional[str] = None


class AiClient:
    """Client for interacting with LLM models using LiteLLM."""

    def __init__(self, token: Optional[str] = None, model: Optional[str] = None):
        # Default to Hugging Face Qwen if model not specified
        self.model = model or os.environ.get("AI_MODEL") or "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct"
        
        # Load the specific credential depending on the target model provider
        if "gemini" in self.model:
            self.token = token or os.environ.get("GEMINI_API_KEY") or get_token("gemini")
            if self.token:
                os.environ["GEMINI_API_KEY"] = self.token
        elif "openai" in self.model:
            self.token = token or os.environ.get("OPENAI_API_KEY") or get_token("openai")
            if self.token:
                os.environ["OPENAI_API_KEY"] = self.token
        else:
            self.token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY") or get_token("hf")
            if self.token:
                os.environ["HUGGINGFACE_API_KEY"] = self.token

    def _has_key(self) -> bool:
        """Check if api key is configured for the chosen model."""
        if "gemini" in self.model:
            return bool(os.environ.get("GEMINI_API_KEY"))
        if "openai" in self.model:
            return bool(os.environ.get("OPENAI_API_KEY"))
        return bool(os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN"))

    def generate_review(self, files: List[Dict[str, Any]]) -> AiReviewReport:
        """
        Generate AI review using LiteLLM with a deterministic fallback.
        """
        if not self._has_key():
            return self._generate_fallback(files, "API token/credentials not configured.")

        # Construct file summary and diff info to keep payload size reasonable
        files_summary = []
        full_diff = []
        for f in files:
            filename = f.get("filename", "")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            files_summary.append(f"{filename} (+{additions}/-{deletions})")
            
            patch = f.get("patch")
            if patch:
                full_diff.append(f"--- a/{filename}\n+++ b/{filename}\n{patch}")

        files_summary_str = "\n".join(files_summary)
        diff_str = "\n\n".join(full_diff)[:6000]  # Truncate to avoid exceeding context limits

        system_prompt = (
            "You are an expert software engineer and security auditor.\n"
            "Analyze the provided code changes (diff) and metadata.\n"
            "Provide an analysis in JSON format with the following keys:\n"
            "- \"summary\": A brief one-sentence or two-sentence description of the overall changes.\n"
            "- \"failure_scenarios\": A list of 2-3 potential production failure scenarios caused by these changes.\n"
            "- \"reviewer_focus\": A list of 2-3 critical areas/files that code reviewers should pay close attention to.\n"
            "- \"suggested_tests\": A list of 2-3 specific test cases or testing strategies that should be added to cover these changes.\n\n"
            "Do not output any markdown formatting, explanation, or code blocks outside the JSON. Return ONLY the raw JSON."
        )

        user_prompt = f"PR Files Changed:\n{files_summary_str}\n\nDiff:\n{diff_str}"

        raw_content: Optional[str] = None
        try:
            response = litellm.completion(  # type: ignore
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty response received from AI model")
            
            # Find the JSON boundaries to strip any markdown code blocks or model commentary
            start_idx = raw_content.find("{")
            end_idx = raw_content.rfind("}")
            if start_idx == -1 or end_idx == -1:
                raise ValueError("Could not find JSON object in AI response")
            
            content = raw_content[start_idx:end_idx + 1]
            data = json.loads(content)
            return AiReviewReport(
                summary=data.get("summary", ""),
                failure_scenarios=data.get("failure_scenarios", []),
                reviewer_focus=data.get("reviewer_focus", []),
                suggested_tests=data.get("suggested_tests", []),
            )
        except Exception as e:
            try:
                with open("d:\\PR\\debug_response.txt", "w", encoding="utf-8") as f:
                    f.write(f"Error: {str(e)}\n\nRaw Content:\n{raw_content}")
            except Exception:
                pass
            logger.warning(f"AI generation failed: {str(e)}. Falling back to deterministic review.")
            return self._generate_fallback(files, str(e))

    def _generate_fallback(self, files: List[Dict[str, Any]], error_msg: str) -> AiReviewReport:
        """Fallback deterministic analysis when AI is unavailable."""
        filenames = [f.get("filename", "") for f in files]
        summary = f"Analyzed {len(files)} files deterministically. AI review is offline."
        
        failure_scenarios = []
        reviewer_focus = []
        suggested_tests = []
        
        has_db = any("db" in f.lower() or "migration" in f.lower() for f in filenames)
        has_config = any("config" in f.lower() or f.endswith((".json", ".toml", ".yaml", ".yml", ".env")) for f in filenames)
        has_auth = any("auth" in f.lower() or "security" in f.lower() for f in filenames)

        if has_db:
            failure_scenarios.append("Database lock contention or slow queries if migration lacks indexes.")
            reviewer_focus.append("Database schema migration scripts and backward compatibility.")
            suggested_tests.append("Verify migration rollback works and test with large/realistic datasets.")
        
        if has_config:
            failure_scenarios.append("Misconfigured production environment variables leading to startup crashes.")
            reviewer_focus.append("Configuration file changes and variable schema validation.")
            suggested_tests.append("Verify config load validation and add environment validation tests.")

        if has_auth:
            failure_scenarios.append("Authentication bypass or token leakage via misconfigured endpoints/logs.")
            reviewer_focus.append("Authentication middleware and authorization decorators.")
            suggested_tests.append("Add unit tests for unauthorized requests and check log statements for sensitive info.")

        if not failure_scenarios:
            failure_scenarios.append("Regression in modified functional components.")
            reviewer_focus.append("Core logic changes in modified source files.")
            suggested_tests.append("Write unit tests targeting modified functions/classes.")

        return AiReviewReport(
            summary=summary,
            failure_scenarios=failure_scenarios,
            reviewer_focus=reviewer_focus,
            suggested_tests=suggested_tests,
            error=error_msg
        )
