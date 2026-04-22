from typing import Optional
import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                username=self.settings.redis_username or None,
                password=self.settings.redis_password or None,
                decode_responses=True,
            )
        return self._client

    async def get_weather(self, farm_id: str = "default") -> Optional[dict]:
        try:
            client = await self.get_client()
            key = f"weather:{farm_id}"
            data = await client.json().get(key)
            return data
        except Exception as e:
            logger.error(f"Redis JSON GET error for weather:{farm_id}: {e}")
            return None

    async def get(self, key: str) -> Optional[str]:
        try:
            client = await self.get_client()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        try:
            client = await self.get_client()
            await client.set(key, value, ex=ttl)
        except Exception as e:
            logger.error(f"Redis SET error for {key}: {e}")

    async def close(self):
        if self._client:
            await self._client.close()


redis_cache = RedisCache()
