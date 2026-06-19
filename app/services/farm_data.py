import json
from app.services.redis_cache import redis_cache
from app.core.logger import get_logger

logger = get_logger(__name__)

CACHE_TTL = 3600

MOCK_SOIL = {
    "moisture": 45.2,
    "pH": 6.8,
    "nitrogen": 28,
    "phosphorus": 15,
    "potassium": 120,
    "temperature": 30.5,
}

MOCK_SATELLITE = {
    "ndvi": 0.72,
    "ndwi": 0.15,
    "crop_health": "good",
    "last_scan": "2026-06-04",
    "area_acres": 2.5,
}


async def fetch_soil(farm_id: str = "default") -> str:
    cached = await redis_cache.get(f"soil:{farm_id}")
    if cached:
        return cached

    data = json.dumps(MOCK_SOIL)
    await redis_cache.set(f"soil:{farm_id}", data, ttl=CACHE_TTL)
    logger.info(f"Seeded mock soil data for farm: {farm_id}")
    return data


async def fetch_satellite(farm_id: str = "default") -> str:
    cached = await redis_cache.get(f"satellite:{farm_id}")
    if cached:
        return cached

    data = json.dumps(MOCK_SATELLITE)
    await redis_cache.set(f"satellite:{farm_id}", data, ttl=CACHE_TTL)
    logger.info(f"Seeded mock satellite data for farm: {farm_id}")
    return data
