from typing import Optional
from app.models.provider import ProviderSelector
from app.services.llm_cache import llm_cache
from app.core.logger import get_logger

logger = get_logger(__name__)


class ReasoningLLM:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        self._selector = ProviderSelector()
        self._model = model or self._selector.resolve_model("reasoning")
        self._llm = self._selector.get_chat_llm(
            model=self._model, temperature=temperature
        )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self._llm.generate(prompt=prompt, system=system)

    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        cache_key = f"{system or ''}:{prompt}"
        cached = await llm_cache.get(cache_key)
        if cached:
            return cached

        result = await self._llm.agenerate(prompt=prompt, system=system)
        await llm_cache.set(cache_key, result)
        return result

    def stream(self, prompt: str, system: Optional[str] = None):
        for chunk in self._llm.stream(prompt=prompt, system=system):
            yield chunk

    async def astream(self, prompt: str, system: Optional[str] = None):
        cache_key = f"{system or ''}:{prompt}"
        cached = await llm_cache.get(cache_key)
        if cached:
            for char in cached:
                yield char
            return

        async for chunk in self._llm.astream(prompt=prompt, system=system):
            yield chunk
