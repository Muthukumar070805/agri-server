from typing import Literal, Optional
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.models.provider import ProviderSelector
from app.resilience.circuit_breaker import get_circuit

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


def _fast_classify(query: str) -> Optional[tuple[Literal["tool", "scheme", "direct"], dict]]:
    content_lower = query.lower().strip()

    if any(
        content_lower.startswith(p) or content_lower == p
        for p in ["hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye", "good", "yes", "no"]
    ) or any(
        p in content_lower for p in ["thank", "welcome", "ok,", "ok ", "alright"]
    ):
        return "direct", {}

    if any(
        p in content_lower
        for p in [
            "weather", "temperature", "humidity", "pressure", "wind",
            "rain", "soil", "moisture", "ph", "nitrogen", "phosphorus",
            "potassium", "satellite", "ndvi", "ndwi", "crop health",
            "crop status", "iot", "sensor",
        ]
    ):
        crop_match = None
        for crop in CROPS:
            if crop in content_lower and crop != "all":
                crop_match = crop
                break
        return "tool", {"type": crop_match}

    if any(
        p in content_lower
        for p in [
            "subsidy", "loan", "scheme", "insurance", "grant",
            "incentive", "pm-kisan", "pm kisan", "government",
            "financial", "pension", "benefit", "assistance",
            "award", "crop insurance", "credit",
        ]
    ):
        scheme_match = None
        for st in SCHEME_TYPES:
            label = st.replace("_", " ")
            if label in content_lower or st in content_lower:
                scheme_match = st
                break
        if not scheme_match:
            words = set(content_lower.split())
            for st in SCHEME_TYPES:
                parts = set(st.split("_"))
                if parts & words:
                    scheme_match = st
                    break
        return "scheme", {"type": scheme_match}

    return None


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
    fast_result = _fast_classify(query)
    if fast_result is not None:
        return fast_result

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
    except Exception:
        return _fallback_classify(query)

    content = response.content.strip()

    try:
        result = json.loads(content)
        query_type = result.get("query_type", "direct")
        filters = result.get("filters", {})
    except json.JSONDecodeError:
        return _fallback_classify(query)

    return query_type, filters
