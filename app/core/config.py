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
    pinecone_environment: str = ""
    pinecone_index: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_flash_model: str = "minimax-m2.7:cloud"
    ollama_reasoning_model: str = "minimax-m2.7:cloud"
    ollama_embed_model: str = "nomic-embed-text:latest"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_username: str = ""
    redis_password: str = ""

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
