"""Unit tests for the RiskEngine."""

from pr_today.risk_engine import RiskEngine


def test_low_risk_pr():
    """A low risk PR changing only 1 markdown file should score in 0-33 range."""
    engine = RiskEngine()
    diff = "diff --git a/README.md b/README.md\n+Some documentation updates"
    files = ["README.md"]
    
    result = engine.analyze(diff, files)
    assert 0 <= result.score <= 33
    assert result.level == "LOW"


def test_high_risk_pr():
    """A high risk PR with migrations, config modifications, and 10 source files should score in 67-100 range."""
    engine = RiskEngine()
    diff = """diff --git a/migrations/versions/123_add_user.py b/migrations/versions/123_add_user.py
+CREATE TABLE users (id INT);
diff --git a/settings.py b/settings.py
+API_KEY = "supersecret"
"""
    files = [
        "migrations/versions/123_add_user.py",
        "settings.py",
        "pr_today/cli.py",
        "pr_today/config.py",
        "pr_today/models.py",
        "pr_today/database.py",
        "pr_today/risk_engine.py",
        "pr_today/ai_engine.py",
        "pr_today/orchestrator.py",
        "pr_today/dashboard.py",
        "pr_today/main.py",
        "pr_today/utils.py",
    ]

    result = engine.analyze(diff, files)
    assert 67 <= result.score <= 100
    assert result.level == "HIGH"


def test_medium_risk_pr():
    """A medium risk PR with 5 source files and no database migrations should score in 34-66 range."""
    engine = RiskEngine()
    # Trigger config dimension via settings patterns in the diff to ensure score falls in 34-66
    diff = """diff --git a/pr_today/cli.py b/pr_today/cli.py
+API_TOKEN = "xyz"
"""
    files = [
        "pr_today/cli.py",
        "pr_today/config.py",
        "pr_today/models.py",
        "pr_today/database.py",
        "pr_today/risk_engine.py",
    ]

    result = engine.analyze(diff, files)
    assert 34 <= result.score <= 66
    assert result.level == "MEDIUM"


def test_blast_radius():
    """Blast radius mapping should identify parent modules from changed files."""
    engine = RiskEngine()
    files = [
        "pr_today/risk_engine.py",
        "tests/test_risk_engine.py",
        "main.py",
    ]
    result = engine.analyze("", files)
    assert result.blast_radius == ["pr_today", "root", "tests"]


def test_missing_tests():
    """Missing test detection should flag a changed source file that has no corresponding test file."""
    engine = RiskEngine()
    # The file "pr_today/untested_module.py" does not have "tests/test_untested_module.py" on disk
    files = [
        "pr_today/untested_module.py",
    ]
    result = engine.analyze("", files)
    assert "pr_today/untested_module.py" in result.missing_tests


def test_determinism():
    """Deterministic scoring guarantees identical results for the same input called repeatedly."""
    engine = RiskEngine()
    diff = "diff --git a/pr_today/cli.py\n+some changes"
    files = ["pr_today/cli.py"]

    result1 = engine.analyze(diff, files)
    result2 = engine.analyze(diff, files)

    assert result1.score == result2.score
    assert result1.level == result2.level
    assert result1.breakdown == result2.breakdown
    assert result1.blast_radius == result2.blast_radius
    assert result1.missing_tests == result2.missing_tests


def test_dependency_change_increases_score():
    """Changing requirements.txt should trigger dependency dimension and increase the score."""
    engine = RiskEngine()
    
    # Baseline PR with 1 source file (no dependencies, no migrations, no configs)
    res_base = engine.analyze("", ["pr_today/cli.py"])
    
    # PR with the same file plus a requirements.txt change
    res_dep = engine.analyze("", ["pr_today/cli.py", "requirements.txt"])
    
    assert res_dep.score > res_base.score
    assert res_dep.breakdown["dependency_shifts"] == 100.0
