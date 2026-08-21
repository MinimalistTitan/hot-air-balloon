"""fix assistant conversation schema for existing databases

Revision ID: 20260820_0001
Revises: 9c66222c34c7
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0001"
down_revision: str | None = "9c66222c34c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind: sa.engine.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(bind: sa.engine.Connection, table_name: str, index_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "assistant_conversations"):
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

    if not _index_exists(bind, "assistant_conversations", op.f("ix_assistant_conversations_owner_user_id")):
        op.create_index(
            op.f("ix_assistant_conversations_owner_user_id"),
            "assistant_conversations",
            ["owner_user_id"],
            unique=False,
        )

    if _table_exists(bind, "assistant_conversation_turns"):
        if not _column_exists(bind, "assistant_conversation_turns", "owner_user_id"):
            op.add_column("assistant_conversation_turns", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
        if not _column_exists(bind, "assistant_conversation_turns", "expires_at"):
            op.add_column(
                "assistant_conversation_turns",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )

        if not _index_exists(bind, "assistant_conversation_turns", op.f("ix_assistant_conversation_turns_owner_user_id")):
            op.create_index(
                op.f("ix_assistant_conversation_turns_owner_user_id"),
                "assistant_conversation_turns",
                ["owner_user_id"],
                unique=False,
            )
        if not _index_exists(bind, "assistant_conversation_turns", op.f("ix_assistant_conversation_turns_expires_at")):
            op.create_index(
                op.f("ix_assistant_conversation_turns_expires_at"),
                "assistant_conversation_turns",
                ["expires_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "assistant_conversation_turns"):
        if _index_exists(bind, "assistant_conversation_turns", op.f("ix_assistant_conversation_turns_expires_at")):
            op.drop_index(op.f("ix_assistant_conversation_turns_expires_at"), table_name="assistant_conversation_turns")
        if _index_exists(bind, "assistant_conversation_turns", op.f("ix_assistant_conversation_turns_owner_user_id")):
            op.drop_index(op.f("ix_assistant_conversation_turns_owner_user_id"), table_name="assistant_conversation_turns")
        if _column_exists(bind, "assistant_conversation_turns", "expires_at"):
            op.drop_column("assistant_conversation_turns", "expires_at")
        if _column_exists(bind, "assistant_conversation_turns", "owner_user_id"):
            op.drop_column("assistant_conversation_turns", "owner_user_id")

    if _table_exists(bind, "assistant_conversations"):
        if _index_exists(bind, "assistant_conversations", op.f("ix_assistant_conversations_owner_user_id")):
            op.drop_index(op.f("ix_assistant_conversations_owner_user_id"), table_name="assistant_conversations")
        op.drop_table("assistant_conversations")
