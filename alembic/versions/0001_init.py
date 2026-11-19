"""Инициализация: таблица журнала действий.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("campaign_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("campaign_actions")
