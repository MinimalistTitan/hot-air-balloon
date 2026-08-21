"""add document ingestion state

Revision ID: 20260820_0003
Revises: 20260820_0002
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0003"
down_revision: str | None = "20260820_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ingestion_error", sa.Text(), nullable=True))
    op.add_column("outbox", sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_outbox_ingested_at"), "outbox", ["ingested_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_ingested_at"), table_name="outbox")
    op.drop_column("outbox", "ingested_at")
    op.drop_column("documents", "ingestion_error")
