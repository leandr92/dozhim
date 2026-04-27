"""people templates and batches runtime columns

Revision ID: 20260427_0008
Revises: 20260427_0007
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0008"
down_revision = "20260427_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("manager_person_id", sa.String(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "task_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("title_template", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_deadline_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("verification_policy", sa.JSON(), nullable=False),
        sa.Column("escalation_policy", sa.JSON(), nullable=False),
        sa.Column("calendar_policy", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column("task_batches", sa.Column("result", sa.JSON(), nullable=True))
    op.add_column("task_batches", sa.Column("error", sa.JSON(), nullable=True))
    op.add_column("task_batches", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_batches", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("task_batches", "finished_at")
    op.drop_column("task_batches", "started_at")
    op.drop_column("task_batches", "error")
    op.drop_column("task_batches", "result")
    op.drop_table("task_templates")
    op.drop_table("people")
