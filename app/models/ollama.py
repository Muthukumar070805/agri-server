from langchain_ollama import ChatOllama, OllamaEmbeddings
from typing import Optional
from app.core.config import get_settings


def get_chat_llm(model: Optional[str] = None, temperature: float = 0.1) -> ChatOllama:
    settings = get_settings()
    return ChatOllama(
        model=model or settings.ollama_flash_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


def get_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
