from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.container import get_container
from app.modules.documents.presentation.schemas import UploadDocumentResponse
from app.modules.documents.application.commands import UploadDocumentCommand
from app.modules.documents.domain.errors import (
    DocumentTooLargeError,
    DocumentUnsupportedContentTypeError,
)
from app.modules.documents.wiring import DocumentsModule

router = APIRouter(prefix="/documents", tags=["documents"])
def get_documents_module(request: Request) -> DocumentsModule:
    module = get_container(request).documents

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document upload is not configured",
        )

    return module


async def read_limited_upload(upload: UploadFile, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise DocumentTooLargeError("uploaded file exceeds max size")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    module: Annotated[
        DocumentsModule,
        Depends(get_documents_module),
    ],
    file: Annotated[UploadFile, File(...)],
    source: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UploadDocumentResponse:
    del source  # reserved for future metadata persistence
    content_type = file.content_type or "application/octet-stream"
   

    if content_type not in module.upload_policy.allowed_content_types:
        raise DocumentUnsupportedContentTypeError("unsupported content type")

    payload = await read_limited_upload(file, module.upload_policy.max_bytes)
    
    result = await module.upload_document.execute(
        UploadDocumentCommand(
            original_filename=file.filename or "uploaded-file",
            content_type=content_type,
            content_bytes=payload,
            request_id=request.headers.get("x-request-id"),
            idempotency_key=idempotency_key,
        )
    )
     
    return UploadDocumentResponse.model_validate(result)