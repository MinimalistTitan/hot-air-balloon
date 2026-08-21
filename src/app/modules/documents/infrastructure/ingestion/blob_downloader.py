from typing import Protocol, runtime_checkable


@runtime_checkable
class BlobDownloaderPort(Protocol):
    async def download(self, *, container: str, blob_name: str) -> bytes: ...
