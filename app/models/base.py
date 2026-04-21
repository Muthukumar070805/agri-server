from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Any
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    raw: Optional[Any] = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers via LangChain."""

    @abstractmethod
    def get_chain(self):
        """Return a LangChain chain."""
        pass

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
    chain = self.get_chain()
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if m["role"] == "system":
                lc_messages.append(SystemMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))
        result = await chain.ainvoke(lc_messages)
        return LLMResponse(content=result.content)

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        chain = self.get_chain()
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if m["role"] == "system":
                lc_messages.append(SystemMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))
        async for chunk in chain.astream(lc_messages):
            yield chunk.content


class BaseEmbeddings(ABC):
    """Abstract base class for embedding models via LangChain."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Get embedding for a single text."""
        pass

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(text) for text in texts]
