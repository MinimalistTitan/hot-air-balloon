from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.database import Base
from app.core.sqlalchemy_types import UTCDateTime


class AssistantConversationRecord(Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "owner_user_id",
            name="uq_assistant_conversations_id_owner_user_id",
        ),
        Index(
            "ix_assistant_conversations_last_turn_id",
            "last_turn_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_turn_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    consolidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ConversationTurnRecord(Base):
    __tablename__ = "assistant_conversation_turns"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "owner_user_id"],
            ["assistant_conversations.id", "assistant_conversations.owner_user_id"],
            name="fk_assistant_conversation_turns_conversation_owner",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        index=True,
        nullable=True,
    )
