from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.ollama import get_embeddings as get_ollama_embeddings
from app.models.ollama import get_chat_llm as get_ollama_llm

logger = get_logger(__name__)


class LLMTimeoutError(Exception):
    """Raised when LLM call exceeds timeout."""

    pass


def _get_timeout() -> int:
    return get_settings().llm_timeout_seconds


@dataclass
class LLMResponse:
    content: str
    raw: Optional[object] = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def invoke(self, messages: list):
        """Invoke LLM with LangChain message list. Returns LangChain response object."""
        pass

    @abstractmethod
    async def ainvoke(self, messages: list):
        """Async invoke LLM with LangChain message list."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str, system: Optional[str] = None):
        pass

    @abstractmethod
    async def astream(self, prompt: str, system: Optional[str] = None):
        pass


class OllamaLLM(BaseLLM):
    """Ollama LLM wrapper."""

    def __init__(self, model: Optional[str] = None, temperature: float = 0.1):
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
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Ollama LLM call timed out after {timeout}s")

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self._llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=prompt)]
        ).content

    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        timeout = _get_timeout()
        try:
            async with asyncio.timeout(timeout):
                return (
                    await self._llm.ainvoke(
                        [SystemMessage(content=system), HumanMessage(content=prompt)]
                    )
                ).content
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Ollama LLM call timed out after {timeout}s")

    def stream(self, prompt: str, system: Optional[str] = None):
        for chunk in self._llm.stream(
            [SystemMessage(content=system), HumanMessage(content=prompt)]
        ):
            if chunk.content:
                yield chunk.content

    async def astream(self, prompt: str, system: Optional[str] = None):
        async for chunk in self._llm.astream(
            [SystemMessage(content=system), HumanMessage(content=prompt)]
        ):
            if chunk.content:
                yield chunk.content


class MistralLLM(BaseLLM):
    """Mistral LLM wrapper."""

    def __init__(self, model: Optional[str] = None, temperature: float = 0.1):
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
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Mistral LLM call timed out after {timeout}s")

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return self._llm.invoke(messages).content

    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        timeout = _get_timeout()
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        try:
            async with asyncio.timeout(timeout):
                return (await self._llm.ainvoke(messages)).content
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Mistral LLM call timed out after {timeout}s")

    def stream(self, prompt: str, system: Optional[str] = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def astream(self, prompt: str, system: Optional[str] = None):
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield chunk.content


class ProviderSelector:
    """Factory for LLM provider selection."""

    def __init__(self):
        self.provider = get_settings().provider

    def get_chat_llm(
        self, model: Optional[str] = None, temperature: float = 0.1
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
                    logger.info("Falling back to MistralAIEmbeddings")
                    return MistralAIEmbeddings(
                        model="mistral-embed",
                        api_key=settings.mistral_api_key,
                    )
                except Exception as e2:
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
