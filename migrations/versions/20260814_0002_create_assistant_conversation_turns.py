"""create assistant conversation turns

Revision ID: 20260814_0002
Revises: d38fb5db49a1
Create Date: 2026-08-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "d38fb5db49a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversation_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_conversation_turns")),
    )
    op.create_index(
        op.f("ix_assistant_conversation_turns_conversation_id"),
        "assistant_conversation_turns",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_conversation_turns_owner_user_id"),
        "assistant_conversation_turns",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_conversation_turns_expires_at"),
        "assistant_conversation_turns",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_turn_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_conversations")),
    )
    op.create_index(
        op.f("ix_assistant_conversations_owner_user_id"),
        "assistant_conversations",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assistant_conversations_owner_user_id"),
        table_name="assistant_conversations",
    )
    op.drop_table("assistant_conversations")
    op.drop_index(
        op.f("ix_assistant_conversation_turns_expires_at"),
        table_name="assistant_conversation_turns",
    )
    op.drop_index(
        op.f("ix_assistant_conversation_turns_owner_user_id"),
        table_name="assistant_conversation_turns",
    )
    op.drop_index(
        op.f("ix_assistant_conversation_turns_conversation_id"),
        table_name="assistant_conversation_turns",
    )
    op.drop_table("assistant_conversation_turns")
