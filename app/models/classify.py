from typing import Literal
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.models.provider import ProviderSelector
from app.resilience.circuit_breaker import get_circuit, CircuitOpenError

CROPS = [
    "all",
    "coconut",
    "groundnut",
    "horticulture",
    "millets",
    "oilpalm",
    "oilseeds",
    "paddy",
    "pulses",
    "sugarcane",
    "vegetables",
]
SCHEME_TYPES = [
    "award_incentive",
    "credit_loan",
    "crop_insurance",
    "crop_productivity",
    "farm_mechanization",
    "farmer_organization",
    "input_subsidy",
    "irrigation",
    "organic_farming",
    "pest_management",
    "planting_material",
    "seed_production",
    "soil_health",
    "training_extension",
]

SYSTEM_PROMPT = f"""You are a query classifier for a farmer helpline.

Available metadata filters:
- Crops: {", ".join(CROPS)}
- Scheme Types: {", ".join(SCHEME_TYPES)}

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
    - Look for scheme types: {", ".join(SCHEME_TYPES)}

    Respond with ONLY a JSON object in this exact format:
    {{"query_type": "tool" | "scheme" | "direct", "filters": {{"type": "..." | null}}}}"""


def _fallback_classify(query: str) -> tuple[Literal["tool", "scheme", "direct"], dict]:
    content_lower = query.lower()
    if any(
        k in content_lower
        for k in [
            "subsidy",
            "loan",
            "scheme",
            "insurance",
            "grant",
            "incentive",
            "pm-kisan",
            "government",
            "financial",
        ]
    ):
        return "scheme", {"type": None}
    elif any(
        k in content_lower
        for k in [
            "weather",
            "soil",
            "moisture",
            "satellite",
            "ndvi",
            "iot",
            "temperature",
            "humidity",
            "pressure",
        ]
    ):
        return "tool", {"type": None}
    return "direct", {}


async def classify_query(
    query: str,
) -> tuple[Literal["tool", "scheme", "direct"], dict]:
    selector = ProviderSelector()
    llm = selector.get_chat_llm(
        model=selector.resolve_model("classify"), temperature=0.1
    )

    cb = get_circuit("classify-llm")
    try:
        response = await cb.call(
            llm.ainvoke,
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)],
        )
    except CircuitOpenError:
        return _fallback_classify(query)

    content = response.content.strip()

    try:
        result = json.loads(content)
        query_type = result.get("query_type", "direct")
        filters = result.get("filters", {})
    except json.JSONDecodeError:
        return _fallback_classify(query)

    return query_type, filters
