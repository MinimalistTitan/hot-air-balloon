from app.core.config import Settings


def test_settings_accepts_provider_neutral_names() -> None:
    settings = Settings(
        smoke_enabled=True,
        chat_model="gpt-4.1",
        chat_api_key="chat-secret",
        embedding_model="text-embedding-3-small",
        embedding_api_key="embedding-secret",
        timeout_seconds=30.0,
    )

    assert settings.smoke_enabled is True
    assert settings.chat_model == "gpt-4.1"
    assert settings.chat_api_key.get_secret_value() == "chat-secret"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_api_key.get_secret_value() == "embedding-secret"
    assert settings.timeout_seconds == 30.0
