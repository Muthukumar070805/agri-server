from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from app.models.ollama import get_chat_llm
from app.core.config import get_settings

SYSTEM_PROMPT = """You are a query classifier for a farmer helpline.

- "tool": User asking for data (weather, soil, satellite, IoT, farm conditions, crop status)
- "direct": Greetings, acknowledgments, conversational, simple questions

Respond with ONLY 'tool' or 'direct'."""


def classify_query(query: str) -> Literal["tool", "direct"]:
    settings = get_settings()
    llm = get_chat_llm(model=settings.ollama_flash_model, temperature=0.1)

    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
    )

    content = response.content.strip().lower()
    if "tool" in content:
        return "tool"
    return "direct"
