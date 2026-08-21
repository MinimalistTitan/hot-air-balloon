"""create assistant memory records

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0002"
down_revision: str | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_memory_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("site_code", sa.String(length=64), nullable=True),
        sa.Column("required_permissions", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_turn_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("vector_namespace", sa.String(length=128), nullable=False),
        sa.Column("vector_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sync_last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_memory_records")),
        sa.UniqueConstraint("vector_id", name=op.f("uq_assistant_memory_records_vector_id")),
    )
    for column in ("owner_user_id", "source_document_id", "expires_at", "synced_at"):
        op.create_index(
            op.f(f"ix_assistant_memory_records_{column}"),
            "assistant_memory_records",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("synced_at", "expires_at", "source_document_id", "owner_user_id"):
        op.drop_index(op.f(f"ix_assistant_memory_records_{column}"), table_name="assistant_memory_records")
    op.drop_table("assistant_memory_records")
