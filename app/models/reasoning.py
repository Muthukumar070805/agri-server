from typing import Optional
from app.models.provider import ProviderSelector


class ReasoningLLM:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        self._selector = ProviderSelector()
        self._model = model or self._selector.resolve_model("reasoning")
        self._llm = self._selector.get_chat_llm(model=self._model, temperature=temperature)

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self._llm.generate(prompt=prompt, system=system)

    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        return await self._llm.agenerate(prompt=prompt, system=system)

    def stream(self, prompt: str, system: Optional[str] = None):
        for chunk in self._llm.stream(prompt=prompt, system=system):
            yield chunk

    async def astream(self, prompt: str, system: Optional[str] = None):
        async for chunk in self._llm.astream(prompt=prompt, system=system):
            yield chunk
