from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
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


def get_chat_llm_with_history(
    model: Optional[str] = None, session_id: str = "default", temperature: float = 0.7
) -> RunnableWithMessageHistory:
    base_chain = get_chat_llm(model=model, temperature=temperature)
    history = InMemoryChatMessageHistory()
    return RunnableWithMessageHistory(
        base_chain,
        lambda _: history,
        input_messages_key="input",
        history_messages_key="history",
    )
