"""assignment meeting fields

Revision ID: 20260428_0010
Revises: 20260427_0009
Create Date: 2026-04-28 10:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_0010"
down_revision = "20260427_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_assignments", sa.Column("meeting_event_id", sa.String(), nullable=True))
    op.add_column("task_assignments", sa.Column("meeting_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_assignments", sa.Column("meeting_status", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_assignments", "meeting_status")
    op.drop_column("task_assignments", "meeting_start_at")
    op.drop_column("task_assignments", "meeting_event_id")
