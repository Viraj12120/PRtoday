"""Deterministic risk scoring engine for PRtoday."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class RiskResult:
    """Dataclass representing the result of a PR risk analysis."""

    score: int
    level: str  # LOW, MEDIUM, HIGH
    breakdown: Dict[str, float]
    blast_radius: List[str]
    missing_tests: List[str]


class RiskEngine:
    """Deterministic engine to analyze pull request risk based on diff and file list."""

    def analyze(self, pr_diff: str, files: List[str]) -> RiskResult:
        """Analyze a PR's files and diff to compute a deterministic risk score.

        Args:
            pr_diff: The git diff string of the pull request.
            files: A list of file paths modified in the pull request.

        Returns:
            A RiskResult containing score, level, breakdown, blast radius, and missing tests.
        """
        # 1. Volume & Criticality (30% weight)
        score_vol = self._calculate_volume_score(files)

        # 2. DB Migration Detection (30% weight)
        score_db = self._detect_db_migrations(pr_diff, files)

        # 3. Config/Secret Changes (25% weight)
        score_config = self._detect_config_changes(pr_diff, files)

        # 4. Dependency Shifts (15% weight)
        score_dep = self._detect_dependency_shifts(pr_diff, files)

        # Calculate final weighted score
        weighted_score = (
            score_vol * 0.30 + score_db * 0.30 + score_config * 0.25 + score_dep * 0.15
        )
        score = int(round(weighted_score))

        # Ensure score is within 0-100 range
        score = max(0, min(100, score))

        # Determine level based on thresholds: LOW 0-33, MEDIUM 34-66, HIGH 67-100
        if score <= 33:
            level = "LOW"
        elif score <= 66:
            level = "MEDIUM"
        else:
            level = "HIGH"

        # Calculate blast radius: map changed files to their parent package/module
        blast_radius = self._calculate_blast_radius(files)

        # Detect missing tests
        missing_tests = self._detect_missing_tests(files)

        breakdown = {
            "volume_and_criticality": float(round(score_vol, 2)),
            "db_migrations": float(round(score_db, 2)),
            "config_changes": float(round(score_config, 2)),
            "dependency_shifts": float(round(score_dep, 2)),
        }

        return RiskResult(
            score=score,
            level=level,
            breakdown=breakdown,
            blast_radius=blast_radius,
            missing_tests=missing_tests,
        )

    def _calculate_volume_score(self, files: List[str]) -> float:
        """Calculate score based on volume and criticality of changed files."""
        if not files:
            return 0.0

        total_criticality = 0.0
        for f in files:
            path = Path(f)
            # Determine file type and multiplier
            if self._is_migration_file(f):
                multiplier = 5.0
            elif self._is_config_file(f):
                multiplier = 4.0
            elif self._is_dependency_file(f):
                multiplier = 3.0
            elif self._is_test_file(f):
                multiplier = 1.0
            elif path.suffix in (
                ".py",
                ".js",
                ".ts",
                ".go",
                ".rs",
                ".java",
                ".cpp",
                ".c",
            ):
                multiplier = 2.0
            else:
                multiplier = 0.5
            total_criticality += multiplier

        # Map to 0-100 scale: e.g. total criticality of 10 matches 100 score
        # Let's use: score = min(total_criticality * 10, 100)
        return min(total_criticality * 10.0, 100.0)

    def _detect_db_migrations(self, pr_diff: str, files: List[str]) -> float:
        """Detect database migrations in files or diff content."""
        # Check files list
        for f in files:
            if self._is_migration_file(f):
                return 100.0

        # Check diff patterns
        db_patterns = [
            r"(?i)\bALTER\s+TABLE\b",
            r"(?i)\bCREATE\s+TABLE\b",
            r"(?i)\bDROP\s+TABLE\b",
            r"(?i)\bADD\s+COLUMN\b",
        ]
        for pattern in db_patterns:
            if re.search(pattern, pr_diff):
                return 100.0

        return 0.0

    def _detect_config_changes(self, pr_diff: str, files: List[str]) -> float:
        """Detect configuration or secret changes."""
        # Check files list
        for f in files:
            if self._is_config_file(f):
                return 100.0

        # Check diff for secrets or key patterns
        secret_patterns = [
            r"(?i)api[-_]?key",
            r"(?i)secret[-_]?key",
            r"(?i)password",
            r"(?i)token",
            r"(?i)auth[-_]?token",
        ]
        for pattern in secret_patterns:
            if re.search(pattern, pr_diff):
                return 100.0

        return 0.0

    def _detect_dependency_shifts(self, pr_diff: str, files: List[str]) -> float:
        """Detect changes in dependency files."""
        for f in files:
            if self._is_dependency_file(f):
                return 100.0
        return 0.0

    def _calculate_blast_radius(self, files: List[str]) -> List[str]:
        """Map changed files to their parent module/package."""
        modules = set()
        for f in files:
            path = Path(f)
            parts = path.parts
            if len(parts) > 1:
                # E.g. pr_today/risk_engine.py -> pr_today
                modules.add(parts[0])
            else:
                # Root files
                modules.add("root")
        return sorted(list(modules))

    def _detect_missing_tests(self, files: List[str]) -> List[str]:
        """Check if changed source files have corresponding test files."""
        missing = []
        for f in files:
            path = Path(f)
            # Only check source files (e.g. .py), skip tests, migrations, config, dependency files
            if (
                path.suffix == ".py"
                and not self._is_test_file(f)
                and not self._is_migration_file(f)
                and not self._is_config_file(f)
                and not self._is_dependency_file(f)
            ):
                # E.g. pr_today/risk_engine.py -> tests/test_risk_engine.py
                # or tests/pr_today/test_risk_engine.py
                parts = list(path.parts)
                if parts:
                    filename = parts[-1]
                    test_filename = f"test_{filename}"

                    # Formulate expected test path: replace first component with 'tests'
                    # and prefix filename with 'test_'
                    expected_test_path = Path("tests") / test_filename
                    expected_nested_test_path = (
                        Path("tests") / Path(*parts[:-1]) / test_filename
                    )

                    # Check if test file is in files list or exists on disk
                    if not (
                        expected_test_path.exists()
                        or expected_nested_test_path.exists()
                    ):
                        missing.append(f)
        return missing

    def _is_migration_file(self, filename: str) -> bool:
        """Check if file is related to DB migrations."""
        path = Path(filename)
        return (
            "migration" in filename.lower()
            or "alembic" in filename.lower()
            or "versions" in path.parts
        )

    def _is_config_file(self, filename: str) -> bool:
        """Check if file is a config file or settings."""
        path = Path(filename)
        return (
            path.name == ".env"
            or "settings.py" in filename
            or path.suffix in (".yml", ".yaml", ".toml")
            # But exclude pyproject.toml as it is handled by dependencies
            and path.name != "pyproject.toml"
        )

    def _is_dependency_file(self, filename: str) -> bool:
        """Check if file specifies dependencies."""
        name = Path(filename).name
        return name in ("requirements.txt", "pyproject.toml", "package.json", "Gemfile")

    def _is_test_file(self, filename: str) -> bool:
        """Check if file is a test file."""
        path = Path(filename)
        return (
            path.name.lower().startswith("test_")
            or path.name.lower().endswith("_test")
            or path.suffix == ".py"
            and path.name.lower().startswith("test")
            or "tests" in path.parts
            or "test" in path.parts
        )
