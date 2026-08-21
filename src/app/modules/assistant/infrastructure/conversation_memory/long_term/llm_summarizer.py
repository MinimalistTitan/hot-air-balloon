from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.modules.assistant.application.ports import ConversationTurn


class ConversationSummary(BaseModel):
    summary: str
    salient_facts: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class LlmSummarizer:
    llm: ChatOpenAI

    async def summarize(self, turns: list[ConversationTurn]) -> ConversationSummary:
        if not turns:
            return ConversationSummary(summary="", salient_facts=[])

        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Summarize this assistant conversation for long-term user memory.",
                ),
                (
                    "human",
                    (
                        "Conversation transcript:\n{transcript}\n\n"
                        "Return summary and salient_facts. Facts must be durable preferences, constraints, "
                        "or recurring intents."
                    ),
                ),
            ]
        )
        chain = prompt | self.llm.with_structured_output(ConversationSummary)
        raw = await chain.ainvoke({"transcript": transcript})
        parsed = (
            ConversationSummary.model_validate(raw)
            if isinstance(raw, dict)
            else cast(ConversationSummary, raw)
        )
        return ConversationSummary(
            summary=parsed.summary.strip(),
            salient_facts=[fact.strip() for fact in parsed.salient_facts if fact.strip()],
        )
