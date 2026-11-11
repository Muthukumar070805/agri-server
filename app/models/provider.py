import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.ollama import get_chat_llm as get_ollama_llm
from app.models.ollama import get_embeddings as get_ollama_embeddings

logger = get_logger(__name__)


class LLMTimeoutError(Exception):
    """Raised when LLM call exceeds timeout or stream stalls."""


class LLMStreamStalledError(LLMTimeoutError):
    """Raised when a streaming LLM response stalls between chunks."""


def _get_timeout() -> int:
    return get_settings().llm_timeout_seconds


@dataclass
class LLMResponse:
    content: str
    raw: object | None = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def invoke(self, messages: list):
        """Invoke LLM with LangChain message list. Returns LangChain response object."""

    @abstractmethod
    async def ainvoke(self, messages: list):
        """Async invoke LLM with LangChain message list."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        pass

    @abstractmethod
    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str, system: str | None = None):
        pass

    @abstractmethod
    async def astream(self, prompt: str, system: str | None = None):
        pass


class OllamaLLM(BaseLLM):
    """Ollama LLM wrapper."""

    def __init__(self, model: str | None = None, temperature: float = 0.1):
        settings = get_settings()
        self._model = model or settings.ollama_flash_model
        self._llm = get_ollama_llm(model=self._model, temperature=temperature)

    def invoke(self, messages: list):
        return self._llm.invoke(messages)

    async def ainvoke(self, messages: list):
        timeout = _get_timeout()
        try:
            async with asyncio.timeout(timeout):
                return await self._llm.ainvoke(messages)
        except TimeoutError as e:
            raise LLMTimeoutError(f"Ollama LLM call timed out after {timeout}s") from e

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return self._llm.invoke(messages).content

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        timeout = _get_timeout()
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        try:
            async with asyncio.timeout(timeout):
                return (await self._llm.ainvoke(messages)).content
        except TimeoutError as e:
            raise LLMTimeoutError(f"Ollama LLM call timed out after {timeout}s") from e

    def stream(self, prompt: str, system: str | None = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def astream(self, prompt: str, system: str | None = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        timeout = _get_timeout()
        it = self._llm.astream(messages).__aiter__()
        while True:
            try:
                async with asyncio.timeout(timeout):
                    chunk = await it.__anext__()
            except StopAsyncIteration:
                break
            except TimeoutError as e:
                raise LLMStreamStalledError(
                    f"Ollama LLM stream stalled for over {timeout}s"
                ) from e
            if chunk.content:
                yield chunk.content


class MistralLLM(BaseLLM):
    """Mistral LLM wrapper."""

    def __init__(self, model: str | None = None, temperature: float = 0.1):
        settings = get_settings()
        self._model = model or settings.mistral_model
        self._llm = ChatMistralAI(
            model=self._model,
            temperature=temperature,
            api_key=settings.mistral_api_key,
        )

    def invoke(self, messages: list):
        return self._llm.invoke(messages)

    async def ainvoke(self, messages: list):
        timeout = _get_timeout()
        try:
            async with asyncio.timeout(timeout):
                return await self._llm.ainvoke(messages)
        except TimeoutError as e:
            raise LLMTimeoutError(f"Mistral LLM call timed out after {timeout}s") from e

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return self._llm.invoke(messages).content

    async def agenerate(self, prompt: str, system: str | None = None) -> str:
        timeout = _get_timeout()
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        try:
            async with asyncio.timeout(timeout):
                return (await self._llm.ainvoke(messages)).content
        except TimeoutError as e:
            raise LLMTimeoutError(f"Mistral LLM call timed out after {timeout}s") from e

    def stream(self, prompt: str, system: str | None = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def astream(self, prompt: str, system: str | None = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        timeout = _get_timeout()
        it = self._llm.astream(messages).__aiter__()
        while True:
            try:
                async with asyncio.timeout(timeout):
                    chunk = await it.__anext__()
            except StopAsyncIteration:
                break
            except TimeoutError as e:
                raise LLMStreamStalledError(
                    f"Mistral LLM stream stalled for over {timeout}s"
                ) from e
            if chunk.content:
                yield chunk.content


class ProviderSelector:
    """Factory for LLM provider selection."""

    def __init__(self):
        self.provider = get_settings().provider

    def get_chat_llm(
        self, model: str | None = None, temperature: float = 0.1
    ) -> BaseLLM:
        """Get LLM instance based on provider setting."""
        if self.provider == "mistral":
            return MistralLLM(model=model, temperature=temperature)
        return OllamaLLM(model=model, temperature=temperature)

    def get_embeddings(self):
        """Get embeddings instance. Always tries Ollama first."""
        settings = get_settings()
        try:
            return get_ollama_embeddings()
        except Exception as e:
            logger.warning(f"Ollama embeddings unavailable: {e}")
            if self.provider == "mistral":
                try:
                    logger.info(
                        "Falling back to MistralAIEmbeddings (%s, 1536-dim)",
                        settings.mistral_embed_model,
                    )
                    return MistralAIEmbeddings(
                        model=settings.mistral_embed_model,
                        api_key=settings.mistral_api_key,
                    )
                except Exception as e2:  # noqa: BLE001 - re-raised below
                    logger.error(f"Mistral embeddings also failed: {e2}")
            raise

    def resolve_model(self, task: str = "classify") -> str:
        """Resolve correct model name for current provider + task."""
        settings = get_settings()
        if self.provider == "mistral":
            return (
                settings.mistral_reasoning_model
                if task == "reasoning"
                else settings.mistral_model
            )
        return (
            settings.ollama_reasoning_model
            if task == "reasoning"
            else settings.ollama_flash_model
        )

    def is_mistral(self) -> bool:
        return self.provider == "mistral"

    def is_ollama(self) -> bool:
        return self.provider != "mistral"
