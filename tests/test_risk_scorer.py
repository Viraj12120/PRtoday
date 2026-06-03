"""Tests for the deterministic risk scorer."""
from pr_sentinel.risk.scorer import (
    calculate_risk, RiskLevel, _score_file_volume,
    _score_critical_paths, _score_critical_files,
    _classify_risk_level,
)


def _make_file(filename: str, additions: int = 10, deletions: int = 5) -> dict:
    return {
        "filename": filename,
        "status": "modified",
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
        "patch": "",
    }


class TestRiskLevelClassification:
    def test_low_risk(self):
        assert _classify_risk_level(10) == RiskLevel.LOW

    def test_medium_risk(self):
        assert _classify_risk_level(30) == RiskLevel.MEDIUM

    def test_high_risk(self):
        assert _classify_risk_level(55) == RiskLevel.HIGH

    def test_critical_risk(self):
        assert _classify_risk_level(80) == RiskLevel.CRITICAL

    def test_boundary_low_medium(self):
        assert _classify_risk_level(24) == RiskLevel.LOW
        assert _classify_risk_level(25) == RiskLevel.MEDIUM

    def test_boundary_medium_high(self):
        assert _classify_risk_level(49) == RiskLevel.MEDIUM
        assert _classify_risk_level(50) == RiskLevel.HIGH

    def test_boundary_high_critical(self):
        assert _classify_risk_level(74) == RiskLevel.HIGH
        assert _classify_risk_level(75) == RiskLevel.CRITICAL


class TestFileVolumeScoring:
    def test_small_changeset(self):
        score, factors = _score_file_volume(3, 20, 10)
        assert score == 0
        assert len(factors) == 0

    def test_moderate_changeset(self):
        score, factors = _score_file_volume(12, 50, 30)
        assert score >= 5
        assert any("Moderate Change Set" in f.name for f in factors)

    def test_large_changeset(self):
        score, factors = _score_file_volume(25, 100, 50)
        assert score >= 10
        assert any("Large Change Set" in f.name for f in factors)

    def test_massive_changeset(self):
        score, factors = _score_file_volume(55, 1500, 600)
        assert score >= 15 + 12  # massive files + massive diff


class TestCriticalPathScoring:
    def test_auth_path(self):
        files = [_make_file("src/auth/middleware.py")]
        score, factors = _score_critical_paths(files)
        assert score > 0
        assert any("auth" in f.name.lower() for f in factors)

    def test_migration_path(self):
        files = [_make_file("db/migrations/001_add_users.sql")]
        score, factors = _score_critical_paths(files)
        assert score > 0
        assert any("migration" in f.name.lower() for f in factors)

    def test_no_critical_paths(self):
        files = [_make_file("src/components/Button.tsx")]
        score, factors = _score_critical_paths(files)
        assert score == 0
        assert len(factors) == 0

    def test_multiple_critical_paths(self):
        files = [
            _make_file("src/auth/login.py"),
            _make_file("db/migrations/002.sql"),
            _make_file("infrastructure/terraform/main.tf"),
        ]
        score, factors = _score_critical_paths(files)
        assert score > 15  # Multiple critical paths triggered
        assert len(factors) >= 2


class TestCriticalFileScoring:
    def test_dockerfile_change(self):
        files = [_make_file("Dockerfile")]
        score, factors = _score_critical_files(files)
        assert score == 8
        assert factors[0].name == "Critical File Modified: Dockerfile"

    def test_env_production(self):
        files = [_make_file(".env.production")]
        score, factors = _score_critical_files(files)
        assert score == 15

    def test_no_critical_files(self):
        files = [_make_file("src/app.py")]
        score, factors = _score_critical_files(files)
        assert score == 0


class TestCalculateRisk:
    def test_trivial_pr(self):
        files = [_make_file("README.md", 2, 1)]
        report = calculate_risk(files)
        assert report.score < 25
        assert report.level == RiskLevel.LOW
        assert report.total_files_changed == 1

    def test_risky_pr(self):
        files = [
            _make_file("src/auth/middleware.py", 100, 50),
            _make_file("db/migrations/003_payment.sql", 80, 0),
            _make_file("Dockerfile", 20, 10),
            _make_file(".env.production", 5, 2),
            _make_file("src/payment/handler.py", 200, 100),
        ] + [_make_file(f"src/module_{i}.py", 30, 10) for i in range(15)]
        report = calculate_risk(files)
        assert report.score >= 50
        assert report.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert len(report.triggered_factors) > 3

    def test_score_clamped_to_100(self):
        # Generate a huge PR that would overflow
        files = [
            _make_file(f"src/auth/file_{i}.py", 500, 500) for i in range(60)
        ] + [
            _make_file("Dockerfile"),
            _make_file(".env.production"),
            _make_file("docker-compose.yml"),
            _make_file("db/migrations/big.sql"),
        ]
        report = calculate_risk(files)
        assert report.score <= 100

    def test_empty_pr(self):
        report = calculate_risk([])
        assert report.score == 0
        assert report.level == RiskLevel.LOW
