"""AST Engine for determining caller context and structural impact of changes."""

import logging
import os
import re
import subprocess
import tempfile
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class AstEngine:
    def __init__(self, repo_path: str, diff_content: str):
        self.repo_path = repo_path
        self.diff_content = diff_content

    def extract_caller_context(self) -> str:
        """Language-agnostic extraction of modified function calls to determine blast radius."""
        try:
            # 1. Extract modified function/method names from diff
            # This is a naive regex for MVP: matches def func_name( or class ClassName(
            # Also works for JS/TS: function funcName( or const funcName =
            modified_symbols = set()

            # Simple pattern to catch common definition names in diff additions/removals
            patterns = [
                r"^\+.*def\s+([a-zA-Z0-9_]+)\s*\(",
                r"^\+.*class\s+([a-zA-Z0-9_]+)\s*[:\(]",
                r"^\+.*function\s+([a-zA-Z0-9_]+)\s*\(",
                r"^\+.*const\s+([a-zA-Z0-9_]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>",
                r"^\+.*func\s+([a-zA-Z0-9_]+)\s*\(",  # Go
            ]

            for line in self.diff_content.splitlines():
                if not line.startswith("+") and not line.startswith("-"):
                    continue
                for p in patterns:
                    match = re.search(p, line)
                    if match:
                        modified_symbols.add(match.group(1))

            if not modified_symbols:
                return "No structural symbol modifications detected in diff."

            logger.info("Found modified symbols: %s", modified_symbols)

            # 2. Search repo for these symbols using grep to find callers
            context_results = []
            for symbol in modified_symbols:
                # Basic ripgrep or grep equivalent. Python's subprocess grep is easiest
                cmd = ["grep", "-rn", "-m", "10", f"\\b{symbol}\\b", "."]
                result = subprocess.run(
                    cmd, cwd=self.repo_path, capture_output=True, text=True
                )

                if result.stdout:
                    # Parse grep output to count usages and show samples
                    lines = result.stdout.strip().split("\n")
                    files_touching = len(
                        set([line.split(":")[0] for line in lines if ":" in line])
                    )

                    context_results.append(
                        f"Symbol '{symbol}' is referenced in {files_touching}+ files across the repo. "
                        f"Sample usages:\n" + "\n".join(lines[:3])
                    )

            if not context_results:
                return "Modified symbols have no internal callers detected."

            return "\n\n".join(context_results)

        except Exception as e:
            logger.error("AST Engine failed: %s", e)
            return "Failed to extract caller context."
