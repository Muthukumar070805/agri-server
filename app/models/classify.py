from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from app.models.ollama import get_chat_llm
from app.core.config import get_settings

SYSTEM_PROMPT = """You are a query classifier for a farmer helpline.

Available tools:
- get_weather(farm_id) → weather data (temp, humidity, pressure, visibility, conditions)
- get_soil_data(farm_id) → IoT soil data (moisture, temperature, ph, nitrogen)
- get_satellite_data(farm_id) → satellite imagery (NDVI, NDWI, crop status)
- get_farm_data(farm_id) → all farm data combined

Classify as "tool" for queries about:
- weather, temperature, humidity, pressure, visibility
- soil, moisture, pH, nitrogen
- satellite, NDVI, NDWI, crop status, crop health
- IoT sensors, farm conditions

Classify as "direct" for:
- greetings, thanks, acknowledgments
- simple questions not requiring data

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
