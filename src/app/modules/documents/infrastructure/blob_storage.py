from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from app.modules.documents.application.ports import BlobUploadResult


class AzureBlobStorage:
    def __init__(self, *, connection_string: str, container_name: str) -> None:
        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container_name

    async def start(self) -> None:
        # The Azure client initializes lazily.
        return None

    async def stop(self) -> None:
        await self._client.close()

    async def upload(
        self,
        *,
        document_id: UUID,
        filename: str,
        content_type: str,
        payload: bytes,
        sha256_hex: str,
    ) -> BlobUploadResult:
        now = datetime.now(UTC)
        safe_name = filename.replace("/", "_").replace("\\", "_")
        blob_name = f"{now:%Y/%m/%d}/{document_id}_{safe_name}"

        container = self._client.get_container_client(self._container_name)
        with suppress(ResourceExistsError):
            await container.create_container()
        blob = container.get_blob_client(blob_name)
        response = await blob.upload_blob(
            payload,
            overwrite=False,
            content_settings=ContentSettings(content_type=content_type),
            metadata={"sha256": sha256_hex},
        )

        return BlobUploadResult(
            container=self._container_name,
            blob_name=blob_name,
            blob_url=blob.url,
            etag=response.get("etag", ""),
        )

    async def download(self, *, container: str, blob_name: str) -> bytes:
        blob = self._client.get_container_client(container).get_blob_client(blob_name)
        return await (await blob.download_blob()).readall()
