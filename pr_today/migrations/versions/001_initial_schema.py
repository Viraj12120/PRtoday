"""Initial schema — analyses and users tables.

Revision ID: 001
Revises: None
Create Date: 2026-06-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── analyses table ──────────────────────────────────────────────────
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("repo", sa.String(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("blast_radius", sa.JSON(), nullable=False),
        sa.Column(
            "blast_radius_json",
            sa.JSON(),
            nullable=True,
            comment="Structured blast radius for API responses",
        ),
        sa.Column("missing_tests", sa.JSON(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_failures", sa.JSON(), nullable=False),
        sa.Column("ai_focus_areas", sa.JSON(), nullable=False),
        sa.Column("security_findings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("files_changed", sa.JSON(), nullable=False),
        sa.Column(
            "db_migrations_detected", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "config_changes_detected", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "dependency_changes_detected",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create index on (repo, pr_number) for fast lookups
    op.create_index("ix_analyses_repo_pr", "analyses", ["repo", "pr_number"])

    # ── users table ─────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_analyses_repo_pr", table_name="analyses")
    op.drop_table("analyses")
