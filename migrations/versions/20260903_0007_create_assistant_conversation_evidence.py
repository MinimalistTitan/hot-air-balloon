"""create assistant conversation evidence

Revision ID: 20260903_0007
Revises: 20260901_0006
Create Date: 2026-09-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260903_0007"
down_revision: str | None = "20260901_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("evidence_json", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id", "owner_user_id"],
            ["assistant_conversations.id", "assistant_conversations.owner_user_id"],
            name="fk_assistant_conversation_evidence_conversation_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_conversation_evidence"),
        sa.UniqueConstraint("exchange_id", name="uq_assistant_conversation_evidence_exchange"),
    )
    op.create_index(
        "ix_assistant_conversation_evidence_owner_conversation_created",
        "assistant_conversation_evidence",
        ["owner_user_id", "conversation_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_conversation_evidence_expires_at",
        "assistant_conversation_evidence",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_conversation_evidence_expires_at",
        table_name="assistant_conversation_evidence",
    )
    op.drop_index(
        "ix_assistant_conversation_evidence_owner_conversation_created",
        table_name="assistant_conversation_evidence",
    )
    op.drop_table("assistant_conversation_evidence")
