from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.database import Base
from app.core.sqlalchemy_types import UTCDateTime


class AssistantConversationRecord(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_turn_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    consolidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ConversationTurnRecord(Base):
    __tablename__ = "assistant_conversation_turns"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        index=True,
        nullable=True,
    )
