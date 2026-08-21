from dataclasses import dataclass

from langchain_openai import OpenAIEmbeddings

from app.modules.assistant.application.ports import EmbeddingPort


@dataclass(slots=True)
class OpenAIEmbeddingClient(EmbeddingPort):
    api_key: str
    model: str
    base_url: str

    async def embed(self, text: str) -> list[float]:
        client = OpenAIEmbeddings(
            openai_api_key=self.api_key,
            model=self.model,
            openai_api_base=self.base_url,
        )
        return await client.aembed_query(text)
