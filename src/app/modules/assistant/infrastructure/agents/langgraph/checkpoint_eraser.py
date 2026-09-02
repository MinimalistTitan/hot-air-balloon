from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.assistant.application.ports import CheckpointErasePort
from app.modules.assistant.infrastructure.agents.langgraph.postgres_checkpointer import (
    PostgresCheckpointer,
)
from app.modules.assistant.infrastructure.agents.langgraph.thread_identity import derive_thread_id
from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass(frozen=True, slots=True)
class LangGraphCheckpointEraser(CheckpointErasePort):
    checkpointer: BaseCheckpointSaver[Any] | PostgresCheckpointer

    async def erase_conversation(
        self,
        owner_user_id: UUID,
        conversation_id: UUID,
    ) -> None:
        saver = (
            self.checkpointer.saver
            if isinstance(self.checkpointer, PostgresCheckpointer)
            else self.checkpointer
        )
        thread_ids = (
            derive_thread_id(
                owner_user_id=owner_user_id,
                conversation_id=conversation_id,
            ),
            str(conversation_id),
        )
        for thread_id in thread_ids:
            await saver.adelete_thread(thread_id)
