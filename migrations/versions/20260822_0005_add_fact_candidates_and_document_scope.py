"""add fact candidates and document scope

Revision ID: 20260822_0005
Revises: 20260821_0004
Create Date: 2026-08-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0005"
down_revision: str | None = "20260821_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("site_code", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_documents_site_code"), "documents", ["site_code"], unique=False)
    op.create_table(
        "assistant_memory_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("statement_sha256", sa.String(length=64), nullable=False),
        sa.Column("fact_class", sa.String(length=32), nullable=False),
        sa.Column("entity_refs", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_turn_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("explicitly_stated", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("decision_reason", sa.String(length=128), nullable=False),
        sa.Column("promoted_memory_record_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["promoted_memory_record_id"],
            ["assistant_memory_records.id"],
            name=op.f(
                "fk_assistant_memory_candidates_promoted_memory_record_id_assistant_memory_records"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_memory_candidates")),
    )
    op.create_index(
        "ix_assistant_memory_candidates_owner_hash",
        "assistant_memory_candidates",
        ["owner_user_id", "statement_sha256"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_memory_candidates_conversation_created",
        "assistant_memory_candidates",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_memory_candidates_expires_at"),
        "assistant_memory_candidates",
        ["expires_at"],
    )
    op.create_index(
        "uq_assistant_memory_records_active_user_fact",
        "assistant_memory_records",
        ["owner_user_id", "kind", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND owner_user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_assistant_memory_records_active_user_fact", table_name="assistant_memory_records"
    )
    op.drop_index(
        op.f("ix_assistant_memory_candidates_expires_at"), table_name="assistant_memory_candidates"
    )
    op.drop_index(
        "ix_assistant_memory_candidates_conversation_created",
        table_name="assistant_memory_candidates",
    )
    op.drop_index(
        "ix_assistant_memory_candidates_owner_hash", table_name="assistant_memory_candidates"
    )
    op.drop_table("assistant_memory_candidates")
    op.drop_index(op.f("ix_documents_site_code"), table_name="documents")
    op.drop_column("documents", "site_code")
