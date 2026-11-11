import json
import re
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.provider import ProviderSelector
from app.resilience.circuit_breaker import get_circuit

_METADATA_PATH = Path(__file__).resolve().parents[2] / "metadata.json"

with open(_METADATA_PATH, encoding="utf-8") as _f:
    _METADATA = json.load(_f)

CROPS = _METADATA["crops"]
SCHEME_TYPES = _METADATA["types"]

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
    {{"query_type": "tool" | "scheme" | "direct",
      "filters": {{"type": "..." | null}}}}"""


_WORD_RE = re.compile(r"[a-z0-9]+")

_GREETING_PHRASES = (
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "thank you",
)

_GREETING_TOKENS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "ok",
        "okay",
        "bye",
        "goodbye",
        "alright",
        "welcome",
        "yes",
        "no",
    }
)

_DIRECT_EXACT = frozenset(
    {
        "how are you",
        "how are you doing",
        "how is it going",
        "who are you",
        "what can you do",
        "what do you do",
    }
)

_SCHEME_KEYWORDS = (
    "subsidy",
    "subsidies",
    "loan",
    "loans",
    "scheme",
    "schemes",
    "insurance",
    "grant",
    "grants",
    "incentive",
    "incentives",
    "pm-kisan",
    "pm kisan",
    "kisan samman",
    "government",
    "financial",
    "pension",
    "benefit",
    "benefits",
    "assistance",
    "award",
    "credit",
)

_TOOL_KEYWORDS = (
    "weather",
    "temperature",
    "humidity",
    "pressure",
    "wind",
    "rain",
    "rainfall",
    "soil",
    "moisture",
    "ph",
    "nitrogen",
    "phosphorus",
    "potassium",
    "satellite",
    "ndvi",
    "ndwi",
    "crop health",
    "crop status",
    "iot",
    "sensor",
    "forecast",
    "drought",
)

_SCHEME_PATTERNS = tuple(
    re.compile(rf"\b{re.escape(term)}\b") for term in _SCHEME_KEYWORDS
)
_TOOL_PATTERNS = tuple(re.compile(rf"\b{re.escape(term)}\b") for term in _TOOL_KEYWORDS)

_INTENT_ACTION_TOKENS = frozenset(
    {
        "what",
        "how",
        "when",
        "where",
        "why",
        "who",
        "which",
        "can",
        "could",
        "is",
        "are",
        "do",
        "does",
        "will",
        "apply",
        "subsidy",
        "subsidies",
        "scheme",
        "schemes",
        "loan",
        "loans",
        "insurance",
        "grant",
        "grants",
        "incentive",
        "incentives",
        "benefit",
        "benefits",
        "cost",
        "costs",
        "price",
        "prices",
        "rate",
        "rates",
        "claim",
        "claims",
        "damage",
        "damages",
        "help",
        "get",
        "avail",
        "process",
        "register",
        "eligibility",
        "weather",
        "rain",
        "temperature",
        "humidity",
        "moisture",
        "ph",
        "ndvi",
        "status",
        "forecast",
    }
)

_SCHEME_SYNONYMS = {
    "tractor": ("farm_mechanization", "crop_productivity"),
    "tractors": ("farm_mechanization", "crop_productivity"),
    "tillers": ("farm_mechanization", "crop_productivity"),
    "tiller": ("farm_mechanization", "crop_productivity"),
    "harvester": ("farm_mechanization", "crop_productivity"),
    "rotavator": ("farm_mechanization", "crop_productivity"),
    "machinery": ("farm_mechanization", "crop_productivity"),
    "implements": ("farm_mechanization", "crop_productivity"),
    "equipment": ("farm_mechanization", "crop_productivity"),
    "seeds": "seed_production",
    "seed": "seed_production",
    "drip": "irrigation",
    "sprinkler": "irrigation",
    "borewell": "irrigation",
    "fertilizer": "input_subsidy",
    "fertilizers": "input_subsidy",
    "urea": "input_subsidy",
    "vermicompost": "organic_farming",
    "manure": "organic_farming",
}


def _is_underspecified_query(content: str) -> bool:
    """Detect 1-2 token queries without interrogative or actionable intent."""
    tokens = _WORD_RE.findall(content.lower())
    if not tokens or len(tokens) > 2:
        return False
    return not any(token in _INTENT_ACTION_TOKENS for token in tokens)


def _strip_greeting(text: str) -> str:
    lowered = text.strip().lower()
    for phrase in _GREETING_PHRASES:
        if lowered == phrase:
            return ""
        if lowered.startswith(phrase) and not lowered[len(phrase)].isalnum():
            return lowered[len(phrase) :].lstrip(" ,.!?-")
    match = _WORD_RE.match(lowered)
    if match and match.group(0) in _GREETING_TOKENS:
        return lowered[match.end() :].lstrip(" ,.!?-")
    return lowered


def _match_crop(content: str) -> str | None:
    for crop in CROPS:
        if crop != "all" and re.search(rf"\b{re.escape(crop)}\b", content):
            return crop
    return None


def _match_scheme_types(content: str) -> list[str]:
    matched: list[str] = []
    # 1. Exact or multi-word match in official SCHEME_TYPES
    for scheme_type in SCHEME_TYPES:
        label = scheme_type.replace("_", " ")
        has_match = re.search(rf"\b{re.escape(label)}\b", content) or re.search(
            rf"\b{re.escape(scheme_type)}\b", content
        )
        if has_match and scheme_type not in matched:
            matched.append(scheme_type)

    # 2. Token overlap with scheme type name components
    words = set(_WORD_RE.findall(content))
    for scheme_type in SCHEME_TYPES:
        if (set(scheme_type.split("_")) & words) and scheme_type not in matched:
            matched.append(scheme_type)

    # 3. Domain synonyms
    for term, mapped in _SCHEME_SYNONYMS.items():
        if re.search(rf"\b{re.escape(term)}\b", content):
            mapped_types = [mapped] if isinstance(mapped, str) else list(mapped)
            for m_type in mapped_types:
                if m_type in SCHEME_TYPES and m_type not in matched:
                    matched.append(m_type)

    return matched


def _match_scheme_type(content: str) -> str | None:
    types = _match_scheme_types(content)
    return types[0] if types else None


def _fast_classify(
    query: str,
) -> tuple[Literal["tool", "scheme", "direct"], dict] | None:
    content = _strip_greeting(query)

    if not content or content.strip(" ?!.,") in _DIRECT_EXACT:
        return "direct", {}

    # Scalable ambiguity check for isolated 1-2 word nouns/entities
    if _is_underspecified_query(content):
        return "direct", {"ambiguous": True, "entity": content}

    # Scheme keywords win: "soil health card scheme" is a scheme, not farm data.
    if any(pattern.search(content) for pattern in _SCHEME_PATTERNS):
        matched_types = _match_scheme_types(content)
        return "scheme", {
            "type": matched_types[0] if matched_types else None,
            "types": matched_types,
        }

    if any(pattern.search(content) for pattern in _TOOL_PATTERNS):
        return "tool", {"crop": _match_crop(content)}

    return None


def _fallback_classify(query: str) -> tuple[Literal["tool", "scheme", "direct"], dict]:
    return _fast_classify(query) or ("direct", {})


def _normalize_filters(raw: object) -> dict:
    if not isinstance(raw, dict) or not raw:
        return {}
    result: dict = {}
    if "crop" in raw and isinstance(raw["crop"], str) and raw["crop"] in CROPS:
        result["crop"] = raw["crop"]

    types: list[str] = []
    raw_types = raw.get("types")
    if isinstance(raw_types, list):
        for t in raw_types:
            if isinstance(t, str) and t in SCHEME_TYPES and t not in types:
                types.append(t)

    raw_type = raw.get("type")
    if isinstance(raw_type, str) and raw_type in SCHEME_TYPES and raw_type not in types:
        types.append(raw_type)

    if "type" in raw or "types" in raw:
        primary_type = (
            types[0]
            if types
            else (
                raw_type
                if isinstance(raw_type, str) and raw_type in SCHEME_TYPES
                else None
            )
        )
        result["type"] = primary_type
        result["types"] = types

    if raw.get("ambiguous"):
        result["ambiguous"] = True
    if raw.get("entity"):
        result["entity"] = raw["entity"]

    return result


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
    except Exception:  # noqa: BLE001 - rule-based fallback is the safety net
        return _fallback_classify(query)

    content = response.content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return _fallback_classify(query)

    if not isinstance(result, dict):
        return _fallback_classify(query)

    query_type = result.get("query_type")
    if query_type not in ("tool", "scheme", "direct"):
        query_type = "direct"

    return query_type, _normalize_filters(result.get("filters"))
