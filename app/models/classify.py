from typing import Literal
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.models.provider import ProviderSelector

CROPS = ["all", "coconut", "groundnut", "horticulture", "millets", "oilpalm", "oilseeds", "paddy", "pulses", "sugarcane", "vegetables"]
SCHEME_TYPES = ["award_incentive", "credit_loan", "crop_insurance", "crop_productivity", "farm_mechanization", "farmer_organization", "input_subsidy", "irrigation", "organic_farming", "pest_management", "planting_material", "seed_production", "soil_health", "training_extension"]

SYSTEM_PROMPT = f"""You are a query classifier for a farmer helpline.

Available metadata filters:
- Crops: {', '.join(CROPS)}
- Scheme Types: {', '.join(SCHEME_TYPES)}

Classify as "tool" for queries about:
- weather, temperature, humidity, pressure, visibility
- soil, moisture, pH, nitrogen
- satellite, NDVI, NDWI, crop status, crop health
- IoT sensors, farm conditions

Classify as "scheme" for queries about:
- government schemes, subsidies, loans, insurance, policies
- agricultural schemes, PM-Kisan, crop insurance
- grants, incentives, financial assistance

Classify as "direct" for:
- greetings, thanks, acknowledgments
- simple questions not requiring data

Also extract metadata filters from the query if scheme-related:
    - Look for scheme types: {', '.join(SCHEME_TYPES)}

    Respond with ONLY a JSON object in this exact format:
    {{"query_type": "tool" | "scheme" | "direct", "filters": {{"type": "..." | null}}}}"""


async def classify_query(query: str) -> tuple[Literal["tool", "scheme", "direct"], dict]:
    selector = ProviderSelector()
    llm = selector.get_chat_llm(model=selector.resolve_model("classify"), temperature=0.1)

    response = await llm.ainvoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
    )

    content = response.content.strip()

    try:
        result = json.loads(content)
        query_type = result.get("query_type", "direct")
        filters = result.get("filters", {})
    except json.JSONDecodeError:
        content_lower = content.lower()
        if any(k in content_lower for k in ["subsidy", "loan", "scheme", "insurance", "grant", "incentive", "pm-kisan"]):
            query_type = "scheme"
        elif any(k in content_lower for k in ["weather", "soil", "moisture", "satellite", "ndvi", "iot", "temperature"]):
            query_type = "tool"
        else:
            query_type = "direct"
        filters = {}

    return query_type, filters
