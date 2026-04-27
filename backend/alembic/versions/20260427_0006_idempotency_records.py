"""idempotency records table

Revision ID: 20260427_0006
Revises: 20260427_0005
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0006"
down_revision = "20260427_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_idempotency_records_lookup",
        "idempotency_records",
        ["key", "method", "path"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_lookup", table_name="idempotency_records")
    op.drop_table("idempotency_records")
