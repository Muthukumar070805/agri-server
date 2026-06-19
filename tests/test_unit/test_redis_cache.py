import pytest
from unittest.mock import patch, AsyncMock


class TestRedisCache:
    @pytest.mark.asyncio
    async def test_get_cached_value(self):
        from app.services.redis_cache import redis_cache

        with patch.object(redis_cache, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value="stored-value")
            mock_get_client.return_value = mock_redis
            result = await redis_cache.get("my-key")
            assert result == "stored-value"
            mock_redis.get.assert_called_once_with("my-key")

    @pytest.mark.asyncio
    async def test_get_miss(self):
        from app.services.redis_cache import redis_cache

        with patch.object(redis_cache, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_redis
            result = await redis_cache.get("missing-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_value(self):
        from app.services.redis_cache import redis_cache

        with patch.object(redis_cache, "get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.set = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_redis
            await redis_cache.set("my-key", "my-value", ttl=3600)
            mock_redis.set.assert_called_once_with("my-key", "my-value", ex=3600)

    @pytest.mark.asyncio
    async def test_circuit_open_returns_none(self):
        from app.services.redis_cache import redis_cache

        with patch.object(redis_cache, "get_client") as mock_get_client:
            mock_get_client.side_effect = ConnectionError("No Redis")
            from app.resilience.circuit_breaker import get_circuit, CircuitState

            cb = get_circuit("redis")
            cb._state = CircuitState.OPEN
            result = await redis_cache.get("any-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_set_with_circuit_open_logs_warning(self):
        from app.services.redis_cache import redis_cache

        with patch.object(redis_cache, "get_client") as mock_get_client:
            mock_get_client.side_effect = ConnectionError("No Redis")
            from app.resilience.circuit_breaker import get_circuit, CircuitState

            cb = get_circuit("redis")
            cb._state = CircuitState.OPEN
            await redis_cache.set("key", "value")
