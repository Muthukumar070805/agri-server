from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional
from app.models.ollama import get_chat_llm
from app.core.config import get_settings


class ReasoningLLM:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        settings = get_settings()
        self._model = model or settings.ollama_reasoning_model
        self._llm = get_chat_llm(model=self._model, temperature=temperature)

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = self._llm.invoke(messages)
        return response.content

    async def agenerate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = await self._llm.ainvoke(messages)
        return response.content
