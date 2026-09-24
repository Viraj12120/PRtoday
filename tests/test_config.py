import pytest
from pr_today.config import settings


def test_missing_github_pat(monkeypatch):
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    with pytest.raises(
        ValueError, match="GITHUB_PAT environment variable is missing or empty"
    ):
        settings.validate_github_pat(None)


def test_empty_github_pat():
    with pytest.raises(
        ValueError, match="GITHUB_PAT environment variable is missing or empty"
    ):
        settings.validate_github_pat("   ")


def test_database_url_default():
    assert settings.DATABASE_URL.startswith("sqlite+aiosqlite:///")
