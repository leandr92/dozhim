"""campaign message manual fallback comment

Revision ID: 20260427_0004
Revises: 20260427_0003
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0004"
down_revision = "20260427_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaign_messages", sa.Column("manual_fallback_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_messages", "manual_fallback_comment")
