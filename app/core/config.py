from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    EXOTEL_ACCOUNT_SID: str = ""
    EXOTEL_SUBDOMAIN: str = "api.exotel.com"
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""

    SARVAM_API_KEY: str = ""

    PINECONE_API_KEY: str = ""
    PINECONE_HOST: str = ""
    PINECONE_INDEX: str = ""

    HUGGINGFACE_ACCESS_TOKEN: str = ""

    NEXT_PUBLIC_SUPABASE_URL: str = ""
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: str = ""

    BASE_URL: str = "http://127.0.0.1:8000"
    WS_STREAM_PATH: str = "/voice/stream"


@lru_cache
def get_settings() -> Settings:
    return Settings()
