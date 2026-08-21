import asyncio
from dataclasses import dataclass, field
from typing import Any

from pinecone import Pinecone

from app.modules.assistant.application.ports import VectorIndexPort, VectorRecord


@dataclass(slots=True)
class PineconeVectorIndex(VectorIndexPort):
    api_key: str
    index_name: str
    _index: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = Pinecone(api_key=self.api_key).Index(self.index_name)

    async def upsert(self, namespace: str, records: list[VectorRecord]) -> None:
        vectors = [
            {"id": record.vector_id, "values": record.values, "metadata": record.metadata}
            for record in records
        ]
        await asyncio.to_thread(self._index.upsert, vectors=vectors, namespace=namespace)

    async def fetch_ids(self, namespace: str, vector_ids: list[str]) -> set[str]:
        response = await asyncio.to_thread(self._index.fetch, ids=vector_ids, namespace=namespace)
        vectors: dict[str, object] = response.vectors
        return set(vectors)

    async def list_ids(self, namespace: str) -> set[str]:
        def list_ids() -> set[str]:
            return {
                vector_id
                for page in self._index.list(namespace=namespace)
                for vector_id in page
            }

        return await asyncio.to_thread(list_ids)

    async def delete_ids(self, namespace: str, vector_ids: list[str]) -> None:
        if vector_ids:
            await asyncio.to_thread(self._index.delete, ids=vector_ids, namespace=namespace)
