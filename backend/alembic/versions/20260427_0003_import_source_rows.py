"""imports source rows

Revision ID: 20260427_0003
Revises: 20260427_0002
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0003"
down_revision = "20260427_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("imports", sa.Column("source_rows", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("imports", "source_rows")
