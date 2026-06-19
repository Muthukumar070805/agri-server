from typing import Optional
import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logger import get_logger
from app.resilience.circuit_breaker import get_circuit, CircuitOpenError

logger = get_logger(__name__)


class RedisCache:
    def __init__(self):
        self.settings = get_settings()
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    def _get_pool(self) -> redis.ConnectionPool:
        if self._pool is None:
            self._pool = redis.ConnectionPool(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                username=self.settings.redis_username or None,
                password=self.settings.redis_password or None,
                max_connections=self.settings.redis_pool_size,
                decode_responses=True,
            )
            logger.info(
                f"Redis connection pool created (max: {self.settings.redis_pool_size})"
            )
        return self._pool

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(connection_pool=self._get_pool())
        return self._client

    async def get(self, key: str) -> Optional[str]:
        cb = get_circuit("redis")
        try:
            client = await self.get_client()
            return await cb.call(client.get, key)
        except CircuitOpenError:
            logger.warning(f"Redis circuit open for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Redis GET error for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        cb = get_circuit("redis")
        try:
            client = await self.get_client()
            await cb.call(client.set, key, value, ex=ttl)
        except CircuitOpenError:
            logger.warning(f"Redis circuit open for set: {key}")
        except Exception as e:
            logger.error(f"Redis SET error for {key}: {e}")

    async def close(self):
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()


redis_cache = RedisCache()
