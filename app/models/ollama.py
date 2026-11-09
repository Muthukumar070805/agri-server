from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.core.config import get_settings


def get_chat_llm(model: str | None = None, temperature: float = 0.1) -> ChatOllama:
    settings = get_settings()
    return ChatOllama(
        model=model or settings.ollama_flash_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


def get_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    kwargs = {
        "model": settings.ollama_embed_model,
        "base_url": settings.ollama_base_url,
    }
    if getattr(settings, "ollama_embed_dimensions", 0) > 0:
        kwargs["dimensions"] = settings.ollama_embed_dimensions
    return OllamaEmbeddings(**kwargs)
