from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    service_name: str = "hot-air-balloon"
    environment: Environment = Environment.LOCAL
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = False
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)

    database_url: str = "postgresql+asyncpg://postgres:1234@localhost:5433/galaxy_universal"
    database_echo: bool = False
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)
    database_pool_recycle_seconds: int = Field(default=1800, ge=30)

    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    cors_origins: list[str] = []

    smoke_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_SMOKE_ENABLED", "APP_SMOKE_ENABLED"),
    )
    chat_model: str = Field(
        default="gpt-5.4",
        validation_alias=AliasChoices("APP_CHAT_MODEL", "APP_CHAT_MODEL"),
    )
    chat_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_CHAT_API_KEY",
            "APP_CHAT_API_KEY",
        ),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("APP_EMBEDDING_MODEL", "APP_EMBEDDING_MODEL"),
    )
    embedding_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_EMBEDDING_API_KEY",
            "APP_EMBEDDING_API_KEY",
        ),
    )
    timeout_seconds: float = Field(
        default=15.0,
        gt=1.0,
        le=120.0,
        validation_alias=AliasChoices("APP_TIMEOUT_SECONDS", "APP_TIMEOUT_SECONDS"),
    )
    context_budget_tokens: int = Field(default=8000, ge=1000, le=200_000)
    context_recent_turn_limit: int = Field(default=12, ge=0, le=100)
    short_term_retention_days: int = Field(default=90, ge=1)
    assistant_conversation_retention_days: int = Field(default=180, ge=1)
    long_term_memory_enabled: bool = False
    pinecone_api_key: SecretStr | None = None
    pinecone_index_name: str = "hot-air-balloon"
    pinecone_user_memory_namespace: str = "user-memory"
    pinecone_documents_namespace: str = "documents"
    long_term_recall_top_k: int = Field(default=6, ge=1, le=50)
    long_term_recall_min_score: float = Field(default=0.25, ge=0.0, le=1.0)
    vector_sync_batch_size: int = Field(default=64, ge=1, le=500)
    vector_sync_poll_interval_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    vector_reconciliation_interval_seconds: float = Field(default=86_400.0, ge=60.0)
    memory_retention_batch_size: int = Field(default=64, ge=1, le=500)
    memory_retention_poll_interval_seconds: float = Field(default=30.0, ge=1.0, le=3_600.0)
    consolidation_enabled: bool = False
    consolidation_idle_minutes: int = Field(default=30, ge=1, le=1440)
    summary_retention_days: int = Field(default=180, ge=1, le=3650)

    chat_base_url: str = Field(
        default="https://aiportalapi.stu-platform.live/jpe/v2",
        validation_alias=AliasChoices(
            "APP_CHAT_BASE_URL",
            "APP_BASE_URL",
            "BASE_URL",
        ),
    )

    # Document upload defaults
    documents_upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    documents_allowed_content_types: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    document_ingestion_enabled: bool = False
    document_ingestion_batch_size: int = Field(default=10, ge=1, le=100)
    document_ingestion_poll_interval_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    document_chunk_tokens: int = Field(default=500, ge=50, le=4_000)
    document_chunk_overlap_tokens: int = Field(default=60, ge=0, le=500)

    # Azure Blob Storage configuration
    azure_blob_enabled: bool = False
    azure_blob_connection_string: SecretStr | None = None
    azure_blob_container_name: str = "documents"

    # Kafka and outbox publisher configuration
    kafka_enabled: bool = False
    kafka_bootstrap_servers: list[str] = ["localhost:9092"]
    kafka_documents_topic: str = "document.uploaded.v1"
    kafka_client_id: str = "hot-air-balloon-api"
    outbox_publisher_enabled: bool = False
    outbox_publish_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    outbox_max_retries: int = Field(default=10, ge=1, le=1000)

    @model_validator(mode="after")
    def enforce_production_database(self) -> Self:
        if self.environment is Environment.PRODUCTION and self.database_url.startswith("sqlite"):
            msg = "Production requires a durable, externally managed database"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def enforce_smoke_config(self) -> Self:
        if not self.smoke_enabled:
            return self

        if self.chat_api_key is None:
            msg = "chat_api_key is required when smoke_enabled is true"
            raise ValueError(msg)

        if self.embedding_api_key is None:
            msg = "embedding_api_key is required when smoke_enabled is true"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def enforce_documents_integration(self) -> Self:
        if self.azure_blob_enabled:
            if self.azure_blob_connection_string is None:
                raise ValueError(
                    "azure_blob_connection_string is required when azure_blob_enabled is true"
                )
            if not self.azure_blob_container_name.strip():
                raise ValueError("azure_blob_container_name must not be empty")

        if self.kafka_enabled:
            if not self.kafka_bootstrap_servers:
                raise ValueError("kafka_bootstrap_servers must not be empty")
            if not self.kafka_documents_topic.strip():
                raise ValueError("kafka_documents_topic must not be empty")

        if self.outbox_publisher_enabled and not self.kafka_enabled:
            raise ValueError("outbox_publisher_enabled requires kafka_enabled=true")

        if self.document_ingestion_enabled:
            if not self.azure_blob_enabled:
                raise ValueError("document_ingestion_enabled requires azure_blob_enabled=true")
            if not self.long_term_memory_enabled:
                raise ValueError("document_ingestion_enabled requires long_term_memory_enabled=true")
            if self.document_chunk_overlap_tokens >= self.document_chunk_tokens:
                raise ValueError("document_chunk_overlap_tokens must be smaller than document_chunk_tokens")

        return self

    @model_validator(mode="after")
    def enforce_long_term_memory_integration(self) -> Self:
        if not self.long_term_memory_enabled:
            return self

        if self.pinecone_api_key is None:
            raise ValueError("pinecone_api_key is required when long_term_memory_enabled is true")
        if self.embedding_api_key is None:
            raise ValueError("embedding_api_key is required when long_term_memory_enabled is true")
        if not self.pinecone_index_name.strip():
            raise ValueError("pinecone_index_name must not be empty")

        if self.consolidation_enabled and self.chat_api_key is None:
            raise ValueError("chat_api_key is required when consolidation_enabled is true")

        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
