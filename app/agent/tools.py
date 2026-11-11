import asyncio
import json
import logging

from app.services.farm_data import fetch_satellite, fetch_soil
from app.services.weather import fetch_weather

logger = logging.getLogger(__name__)


def _safe_parse(raw, label):
    if not raw:
        logger.warning(f"{label}: empty response")
        return {"error": f"{label} returned empty"}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"{label}: JSON parse error: {e}")
        return {"error": f"{label} data parse failed"}


async def get_farm_data(farm_id: str = "default") -> str:
    """Get all farm data: weather, soil/IoT, satellite."""
    results = await asyncio.gather(
        fetch_weather(farm_id),
        fetch_soil(farm_id),
        fetch_satellite(farm_id),
        return_exceptions=True,
    )
    weather = results[0] if not isinstance(results[0], Exception) else ""
    soil = results[1] if not isinstance(results[1], Exception) else ""
    satellite = results[2] if not isinstance(results[2], Exception) else ""

    return json.dumps(
        {
            "weather": _safe_parse(weather, "weather"),
            "iot": _safe_parse(soil, "soil"),
            "gee": _safe_parse(satellite, "satellite"),
        }
    )
