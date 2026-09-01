"""harden assistant conversation ownership

Revision ID: 20260901_0006
Revises: 20260822_0005
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0006"
down_revision: str | None = "20260822_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_CONSTRAINT = "uq_assistant_conversations_id_owner_user_id"
TURN_OWNER_FOREIGN_KEY = "fk_assistant_conversation_turns_conversation_owner"
RETENTION_INDEX = "ix_assistant_conversations_last_turn_id"


def upgrade() -> None:
    # Resolve a missing conversation owner only when all known turns agree on
    # exactly one non-null owner. Ambiguous or wholly unowned data is rejected
    # below instead of being silently assigned or deleted.
    # op.execute(
    #     sa.text(
    #         """
    #         WITH resolved_owners AS (
    #             SELECT
    #                 conversation_id,
    #                 MIN(owner_user_id::text)::uuid AS owner_user_id
    #             FROM assistant_conversation_turns
    #             WHERE owner_user_id IS NOT NULL
    #             GROUP BY conversation_id
    #             HAVING COUNT(DISTINCT owner_user_id) = 1
    #         )
    #         UPDATE assistant_conversations AS conversations
    #         SET owner_user_id = resolved_owners.owner_user_id
    #         FROM resolved_owners
    #         WHERE conversations.id = resolved_owners.conversation_id
    #           AND conversations.owner_user_id IS NULL
    #         """
    #     )
    # )
    # op.execute(
    #     sa.text(
    #         """
    #         UPDATE assistant_conversation_turns AS turns
    #         SET owner_user_id = conversations.owner_user_id
    #         FROM assistant_conversations AS conversations
    #         WHERE turns.conversation_id = conversations.id
    #           AND turns.owner_user_id IS NULL
    #           AND conversations.owner_user_id IS NOT NULL
    #         """
    #     )
    # )
    # op.execute(
    #     sa.text(
    #         """
    #         DO $$
    #         BEGIN
    #             IF EXISTS (
    #                 SELECT 1
    #                 FROM assistant_conversations
    #                 WHERE owner_user_id IS NULL
    #             ) THEN
    #                 RAISE EXCEPTION
    #                     'Cannot enforce assistant ownership: unowned conversations remain';
    #             END IF;

    #             IF EXISTS (
    #                 SELECT 1
    #                 FROM assistant_conversation_turns AS turns
    #                 LEFT JOIN assistant_conversations AS conversations
    #                   ON conversations.id = turns.conversation_id
    #                 WHERE conversations.id IS NULL
    #                    OR turns.owner_user_id IS NULL
    #                    OR turns.owner_user_id IS DISTINCT FROM conversations.owner_user_id
    #             ) THEN
    #                 RAISE EXCEPTION
    #                     'Cannot enforce assistant ownership: orphaned or mismatched turns remain';
    #             END IF;
    #         END
    #         $$;
    #         """
    #     )
    # )

    op.alter_column(
        "assistant_conversations",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "assistant_conversation_turns",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_unique_constraint(
        OWNER_CONSTRAINT,
        "assistant_conversations",
        ["id", "owner_user_id"],
    )
    op.create_foreign_key(
        TURN_OWNER_FOREIGN_KEY,
        "assistant_conversation_turns",
        "assistant_conversations",
        ["conversation_id", "owner_user_id"],
        ["id", "owner_user_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        RETENTION_INDEX,
        "assistant_conversations",
        ["last_turn_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(RETENTION_INDEX, table_name="assistant_conversations")
    op.drop_constraint(
        TURN_OWNER_FOREIGN_KEY,
        "assistant_conversation_turns",
        type_="foreignkey",
    )
    op.drop_constraint(
        OWNER_CONSTRAINT,
        "assistant_conversations",
        type_="unique",
    )
    op.alter_column(
        "assistant_conversation_turns",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "assistant_conversations",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
