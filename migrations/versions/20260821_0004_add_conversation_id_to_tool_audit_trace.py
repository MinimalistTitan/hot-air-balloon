"""add conversation id to tool audit and trace

Revision ID: 20260821_0004
Revises: 20260820_0003
Create Date: 2026-08-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0004"
down_revision: str | None = "20260820_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assistant_tool_audit_records",
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "assistant_tool_trace_events",
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_assistant_tool_audit_records_conversation_id"),
        "assistant_tool_audit_records",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_tool_trace_events_conversation_id"),
        "assistant_tool_trace_events",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assistant_tool_trace_events_conversation_id"),
        table_name="assistant_tool_trace_events",
    )
    op.drop_index(
        op.f("ix_assistant_tool_audit_records_conversation_id"),
        table_name="assistant_tool_audit_records",
    )
    op.drop_column("assistant_tool_trace_events", "conversation_id")
    op.drop_column("assistant_tool_audit_records", "conversation_id")
