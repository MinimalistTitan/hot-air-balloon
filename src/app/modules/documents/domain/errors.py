from app.shared.domain.errors import DomainError


class DocumentTooLargeError(DomainError):
    code = "document_too_large"


class DocumentUnsupportedContentTypeError(DomainError):
    code = "document_unsupported_content_type"


class DocumentAlreadyExistsError(DomainError):
    code = "document_already_exists"


class StorageUploadFailedError(DomainError):
    code = "storage_upload_failed"