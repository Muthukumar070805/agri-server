import json
from app.services.redis_cache import redis_cache
from app.core.logger import get_logger

logger = get_logger(__name__)

CACHE_TTL = 3600
CACHE_TTL_SAT = 1800

MOCK_SOIL = {
    "moisture": 45.2,
    "pH": 6.8,
    "nitrogen": 28,
    "phosphorus": 15,
    "potassium": 120,
    "temperature": 30.5,
}

MOCK_SATELLITE = {
    "wind": {"speed_m_s": None, "direction_deg": None},
    "rain": {"precipitation_mm_hr": None},
    "ndvi": {"value": None, "source": "Sentinel-2"},
    "sar": {"vv_db": None, "vh_db": None},
    "temperature": {"temp_2m_c": None},
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

    from app.services.gee import fetch_satellite as gee_fetch

    try:
        data = await gee_fetch(farm_id)
    except Exception as e:
        logger.error(f"GEE fetch failed, using mock fallback: {e}")
        data = json.dumps(MOCK_SATELLITE)

    await redis_cache.set(f"satellite:{farm_id}", data, ttl=CACHE_TTL_SAT)
    return data
