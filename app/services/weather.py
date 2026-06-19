import json
import httpx
from app.core.logger import get_logger
from app.services.redis_cache import redis_cache
from app.core.config import get_settings

logger = get_logger(__name__)

CACHE_TTL = 1800


async def _build_url() -> str:
    loc = get_settings().weather_location
    return f"https://wttr.in/{loc}?format=j1"


async def fetch_weather(farm_id: str = "default") -> str:
    cached = await redis_cache.get(f"weather:{farm_id}")
    if cached:
        return cached

    url = await _build_url()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        if cached:
            return cached
        return json.dumps({"error": "Weather data temporarily unavailable"})

    cc = raw["current_condition"][0]
    data = json.dumps(
        {
            "temp_C": cc["temp_C"],
            "humidity": cc["humidity"],
            "pressure": cc["pressure"],
            "visibility": cc["visibility"],
            "weatherCode": cc["weatherCode"],
            "feelsLikeC": cc["FeelsLikeC"],
            "windSpeedKmph": cc["windspeedKmph"],
            "windDir16Point": cc["winddir16Point"],
            "cloudcover": cc["cloudcover"],
            "uvIndex": cc["uvIndex"],
            "condition": cc["weatherDesc"][0]["value"],
            "precipMM": cc["precipMM"],
        }
    )

    await redis_cache.set(f"weather:{farm_id}", data, ttl=CACHE_TTL)
    return data
