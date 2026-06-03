"""
PR Sentinel Risk Engine - Deterministic Scoring Module.

Calculates a risk score (0-100) based on weighted analysis of PR file changes.
AI must EXPLAIN risk, not CALCULATE risk. This module is the single source of truth.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskFactor:
    """A single identified risk factor from the PR analysis."""
    name: str
    description: str
    weight: float  # 0.0 - 1.0 contribution to total score
    triggered: bool = False


@dataclass
class RiskReport:
    """The complete deterministic risk assessment for a PR."""
    score: int  # 0-100
    level: RiskLevel
    factors: List[RiskFactor] = field(default_factory=list)
    total_files_changed: int = 0
    total_additions: int = 0
    total_deletions: int = 0

    @property
    def triggered_factors(self) -> List[RiskFactor]:
        return [f for f in self.factors if f.triggered]


# --- Risk Factor Definitions & Weights ---
# Each factor has a base weight. The final score is the sum of triggered weights,
# normalized to 0-100.

# Critical directories that indicate high-risk changes
CRITICAL_PATHS = {
    "auth": 15,
    "authentication": 15,
    "middleware": 12,
    "security": 15,
    "payment": 15,
    "billing": 12,
    "database": 12,
    "migration": 15,
    "migrations": 15,
    "db": 10,
    "infrastructure": 12,
    "infra": 12,
    "terraform": 12,
    "k8s": 10,
    "kubernetes": 10,
    "docker": 8,
    "ci": 8,
    "cd": 8,
    ".github/workflows": 8,
    "secrets": 18,
    "crypto": 15,
    "session": 12,
    "oauth": 12,
}

# Config files that are risky to modify
CRITICAL_FILES = {
    "Dockerfile": 8,
    "docker-compose.yml": 8,
    "docker-compose.yaml": 8,
    ".env": 12,
    ".env.example": 5,
    ".env.production": 15,
    "package.json": 6,
    "package-lock.json": 4,
    "requirements.txt": 6,
    "Pipfile": 6,
    "Pipfile.lock": 4,
    "pyproject.toml": 6,
    "poetry.lock": 4,
    "go.mod": 6,
    "go.sum": 4,
    "Cargo.toml": 6,
    "Cargo.lock": 4,
    "Gemfile": 6,
    "Gemfile.lock": 4,
    "nginx.conf": 10,
    "webpack.config.js": 6,
    "tsconfig.json": 5,
    "babel.config.js": 5,
    ".eslintrc": 3,
    "jest.config.js": 3,
    "Makefile": 5,
    "Procfile": 8,
    "serverless.yml": 10,
    "terraform.tfvars": 12,
}

# File extensions that indicate dependency/config changes
DEPENDENCY_EXTENSIONS = {".lock", ".sum", ".resolved"}


def _score_file_volume(total_files: int, total_additions: int, total_deletions: int) -> tuple[int, List[RiskFactor]]:
    """Score based on the sheer volume of changes."""
    factors = []
    score = 0

    # Files changed scoring
    if total_files >= 50:
        factors.append(RiskFactor("Massive Change Set", f"{total_files} files changed", 0.15, True))
        score += 15
    elif total_files >= 20:
        factors.append(RiskFactor("Large Change Set", f"{total_files} files changed", 0.10, True))
        score += 10
    elif total_files >= 10:
        factors.append(RiskFactor("Moderate Change Set", f"{total_files} files changed", 0.05, True))
        score += 5

    # Lines changed scoring
    total_lines = total_additions + total_deletions
    if total_lines >= 2000:
        factors.append(RiskFactor("Massive Diff", f"{total_lines} lines changed", 0.12, True))
        score += 12
    elif total_lines >= 500:
        factors.append(RiskFactor("Large Diff", f"{total_lines} lines changed", 0.08, True))
        score += 8
    elif total_lines >= 200:
        factors.append(RiskFactor("Moderate Diff", f"{total_lines} lines changed", 0.04, True))
        score += 4

    return score, factors


def _score_critical_paths(files: List[Dict[str, Any]]) -> tuple[int, List[RiskFactor]]:
    """Score based on modifications to critical directories."""
    factors = []
    score = 0
    triggered_paths = set()

    for f in files:
        filename = f.get("filename", "")
        parts = filename.replace("\\", "/").lower().split("/")
        for part in parts:
            if part in CRITICAL_PATHS and part not in triggered_paths:
                triggered_paths.add(part)
                weight = CRITICAL_PATHS[part]
                factors.append(RiskFactor(
                    f"Critical Path Modified: {part}/",
                    f"Changes detected in '{part}/' directory",
                    weight / 100,
                    True
                ))
                score += weight

    return min(score, 40), factors  # Cap critical path contribution at 40


def _score_critical_files(files: List[Dict[str, Any]]) -> tuple[int, List[RiskFactor]]:
    """Score based on modifications to known critical config files."""
    factors = []
    score = 0
    triggered_files = set()

    for f in files:
        filename = f.get("filename", "")
        basename = filename.replace("\\", "/").split("/")[-1]
        if basename in CRITICAL_FILES and basename not in triggered_files:
            triggered_files.add(basename)
            weight = CRITICAL_FILES[basename]
            factors.append(RiskFactor(
                f"Critical File Modified: {basename}",
                f"Configuration file '{basename}' was changed",
                weight / 100,
                True
            ))
            score += weight

    return min(score, 25), factors  # Cap config file contribution at 25


def _score_dependency_changes(files: List[Dict[str, Any]]) -> tuple[int, List[RiskFactor]]:
    """Score based on dependency/lockfile changes."""
    factors = []
    score = 0
    dep_files = []

    for f in files:
        filename = f.get("filename", "")
        ext = "." + filename.split(".")[-1] if "." in filename else ""
        if ext in DEPENDENCY_EXTENSIONS:
            dep_files.append(filename)

    if dep_files:
        weight = min(len(dep_files) * 4, 12)
        factors.append(RiskFactor(
            "Dependency Changes",
            f"{len(dep_files)} dependency/lock files modified",
            weight / 100,
            True
        ))
        score += weight

    return score, factors


def _classify_risk_level(score: int) -> RiskLevel:
    """Classify numeric score into discrete risk levels."""
    if score >= 75:
        return RiskLevel.CRITICAL
    elif score >= 50:
        return RiskLevel.HIGH
    elif score >= 25:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def calculate_risk(files: List[Dict[str, Any]]) -> RiskReport:
    """
    Main entry point. Calculates a deterministic risk score for a PR.

    Args:
        files: List of file dicts with keys: filename, status, additions, deletions, changes, patch

    Returns:
        RiskReport with score, level, and triggered risk factors.
    """
    total_files = len(files)
    total_additions = sum(f.get("additions", 0) for f in files)
    total_deletions = sum(f.get("deletions", 0) for f in files)

    all_factors: List[RiskFactor] = []
    total_score = 0

    # 1. File volume scoring
    vol_score, vol_factors = _score_file_volume(total_files, total_additions, total_deletions)
    total_score += vol_score
    all_factors.extend(vol_factors)

    # 2. Critical path scoring
    path_score, path_factors = _score_critical_paths(files)
    total_score += path_score
    all_factors.extend(path_factors)

    # 3. Critical file scoring
    file_score, file_factors = _score_critical_files(files)
    total_score += file_score
    all_factors.extend(file_factors)

    # 4. Dependency change scoring
    dep_score, dep_factors = _score_dependency_changes(files)
    total_score += dep_score
    all_factors.extend(dep_factors)

    # Clamp to 0-100
    final_score = max(0, min(100, total_score))
    level = _classify_risk_level(final_score)

    return RiskReport(
        score=final_score,
        level=level,
        factors=all_factors,
        total_files_changed=total_files,
        total_additions=total_additions,
        total_deletions=total_deletions,
    )
