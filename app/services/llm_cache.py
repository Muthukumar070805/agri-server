import hashlib
from typing import Optional
import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class LLMCache:
    """Redis-based cache for LLM responses."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
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

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    async def get(self, query: str) -> Optional[str]:
        if not self.settings.llm_cache_enabled:
            return None

        try:
            client = await self._get_client()
            key = f"llm_cache:{self._hash_query(query)}"
            cached = await client.get(key)
            if cached:
                logger.debug(f"LLM cache hit for query: {query[:50]}...")
                return cached
            return None
        except Exception as e:
            logger.warning(f"LLM cache get error: {e}")
            return None

    async def set(self, query: str, response: str) -> bool:
        if not self.settings.llm_cache_enabled:
            return False

        try:
            client = await self._get_client()
            key = f"llm_cache:{self._hash_query(query)}"
            ttl = self.settings.llm_cache_ttl_seconds
            await client.set(key, response, ex=ttl)
            logger.debug(f"LLM cache set for query: {query[:50]}...")
            return True
        except Exception as e:
            logger.warning(f"LLM cache set error: {e}")
            return False

    async def invalidate(self, query: str) -> bool:
        try:
            client = await self._get_client()
            key = f"llm_cache:{self._hash_query(query)}"
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"LLM cache invalidate error: {e}")
            return False

    async def clear_all(self) -> bool:
        try:
            client = await self._get_client()
            keys = []
            async for key in client.scan_iter(match="llm_cache:*"):
                keys.append(key)
            if keys:
                await client.delete(*keys)
                logger.info(f"Cleared {len(keys)} LLM cache entries")
            return True
        except Exception as e:
            logger.warning(f"LLM cache clear error: {e}")
            return False


llm_cache = LLMCache()
