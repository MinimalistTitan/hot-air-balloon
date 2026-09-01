from hashlib import sha256
from uuid import UUID

THREAD_ID_VERSION = "v1"
THREAD_ID_PREFIX = f"assistant:{THREAD_ID_VERSION}:"
_THREAD_ID_DOMAIN = b"erp-assistant:langgraph-thread:v1\x00"


def derive_thread_id(*, owner_user_id: UUID, conversation_id: UUID) -> str:
    """Derive a stable checkpoint key from trusted conversation ownership."""

    digest = sha256(_THREAD_ID_DOMAIN + owner_user_id.bytes + conversation_id.bytes).hexdigest()
    return f"{THREAD_ID_PREFIX}{digest}"
