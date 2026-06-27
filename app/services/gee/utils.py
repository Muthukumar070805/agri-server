import asyncio
from typing import Callable
from app.services.redis_cache import redis_cache
from app.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TTL = 1800


async def get_or_cache(key: str, fetcher: Callable[[], str], ttl: int = DEFAULT_TTL) -> str:
    cached = await redis_cache.get(key)
    if cached:
        logger.debug(f"GEE cache hit: {key}")
        return cached

    logger.info(f"GEE cache miss: {key} — fetching...")
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, fetcher)
    await redis_cache.set(key, data, ttl=ttl)
    return data
