"""Semgrep-based SAST engine for deep semantic analysis of Pull Requests."""

import json
import logging
import os
import subprocess
import tempfile
from typing import List, Dict, Any

import git

logger = logging.getLogger(__name__)

class SastEngine:
    def __init__(self, repo_path: str, files_changed: List[str]):
        self.repo_path = repo_path
        self.files_changed = files_changed

    def run_sast(self) -> List[Dict[str, Any]]:
        """Clone the PR and run semgrep against the changed files."""
        if not self.files_changed:
            return []

        # Only scan actual files, skip deleted ones
        # Actually Semgrep will just ignore files that don't exist
        findings = []
        try:
            logger.info("Running Semgrep on %d changed files...", len(self.files_changed))
            
            # Filter out files that don't exist (e.g. deleted files)
            existing_files = [f for f in self.files_changed if os.path.exists(os.path.join(self.repo_path, f))]
            if not existing_files:
                return []
                
                cmd = [
                    "semgrep",
                    "scan",
                    "--json",
                    "--config=auto",
                    "--quiet"
                ]
                for f in existing_files:
                    cmd.extend(["--include", f])
                    
                result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
                
                if result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        for finding in data.get("results", []):
                            # Simplify the finding for the AI context
                            findings.append({
                                "rule_id": finding.get("check_id"),
                                "message": finding.get("extra", {}).get("message"),
                                "severity": finding.get("extra", {}).get("severity"),
                                "file": finding.get("path"),
                                "line": finding.get("start", {}).get("line"),
                            })
                    except json.JSONDecodeError:
                        logger.error("Failed to parse Semgrep JSON output")
                        logger.debug("Semgrep output: %s", result.stdout)
                
                if result.stderr:
                    logger.debug("Semgrep stderr: %s", result.stderr)

        except Exception as e:
            logger.error("SAST Engine failed: %s", str(e), exc_info=True)
        
        return findings
