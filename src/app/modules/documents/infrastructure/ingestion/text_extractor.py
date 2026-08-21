from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader


class TextExtractionError(ValueError):
    pass


class TextExtractor:
    def extract(self, *, content_type: str, payload: bytes) -> str:
        try:
            if content_type in {"text/plain", "text/markdown"}:
                return payload.decode("utf-8")
            if content_type == "application/pdf":
                return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)
            if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                document = DocxDocument(BytesIO(payload))
                return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except Exception as exception:
            raise TextExtractionError("Document text extraction failed") from exception
        raise TextExtractionError(f"Unsupported document content type: {content_type}")
