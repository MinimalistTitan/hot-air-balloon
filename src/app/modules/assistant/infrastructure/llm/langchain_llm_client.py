from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class LangChainChatModelFactory:
    settings: Settings

    def build(self) -> ChatOpenAI:
        # TODO: add dedicated assistant model settings if you want a model distinct from smoke-check model
        return ChatOpenAI(
            api_key=self.settings.chat_api_key,
            model=self.settings.chat_model,
            base_url=self.settings.chat_base_url,
            temperature=0.0,
            timeout=self.settings.timeout_seconds,
        )