from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    exotel_account_sid: str = ""
    exotel_subdomain: str = "api.in.exotel.com"
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_sender_id: str = "AIHELP"
    exotel_dlt_entity_id: str = ""
    exotel_dlt_template_id: str = ""

    sarvam_api_key: str = ""

    pinecone_api_key: str = ""
    pinecone_host: str = ""
    pinecone_index: str = ""

    # Provider selection
    provider: str = "ollama"  # "ollama" | "mistral"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    mistral_reasoning_model: str = "mistral-large-latest"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_flash_model: str = "minimax-m2.7:cloud"
    ollama_reasoning_model: str = "minimax-m2.7:cloud"
    ollama_embed_model: str = "nomic-embed-text:latest"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_username: str = ""
    redis_password: str = ""
    redis_pool_size: int = 20

    session_redis_enabled: bool = False
    session_ttl_minutes: int = 30

    llm_timeout_seconds: int = 30
    llm_cache_enabled: bool = False
    llm_cache_ttl_seconds: int = 3600

    weather_location: str = "Avadi"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    model_config = ConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def validate_required_keys() -> list[str]:
    """Check for missing or placeholder API keys."""
    settings = get_settings()
    issues = []

    placeholder_patterns = [
        "your_",
        "test-",
        "sk_test_",
        "pk_test_",
        "changeme",
        "replace_me",
    ]

    if settings.provider == "mistral":
        key = settings.mistral_api_key
        if not key or any(p in key.lower() for p in placeholder_patterns):
            issues.append("MISTRAL_API_KEY")

    if settings.pinecone_api_key:
        if any(p in settings.pinecone_api_key.lower() for p in placeholder_patterns):
            issues.append("PINECONE_API_KEY (placeholder detected)")

    if settings.redis_password:
        if any(p in settings.redis_password.lower() for p in placeholder_patterns):
            issues.append("REDIS_PASSWORD (placeholder detected)")

    if settings.sarvam_api_key:
        if any(p in settings.sarvam_api_key.lower() for p in placeholder_patterns):
            issues.append("SARVAM_API_KEY (placeholder detected)")

    return issues
