import pytest
from pr_today.database import init_db, get_session, close_db
from unittest.mock import patch
from pr_today.models import AnalysisResult, User
from datetime import datetime, timezone

import uuid


@pytest.mark.asyncio
async def test_database_lifecycle():
    # Use in-memory DB for test
    with patch(
        "pr_today.database._resolve_database_url",
        return_value="sqlite+aiosqlite:///:memory:",
    ):
        await init_db()

    # Test session usage
    async with get_session() as session:
        # Create user
        uid = str(uuid.uuid4())
        user = User(
            id=uid,
            email=f"test_{uid}@example.com",
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)

        # Create analysis result
        result = AnalysisResult(
            repo="test/repo",
            pr_number=1,
            risk_score=50,
            risk_level="MEDIUM",
            blast_radius=[],
            missing_tests=[],
            ai_failures=[],
            ai_focus_areas=[],
            files_changed=["a.py"],
            db_migrations_detected=False,
            config_changes_detected=False,
            dependency_changes_detected=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(result)
        await session.commit()

        assert result.id is not None
        assert user.id is not None

    await close_db()
