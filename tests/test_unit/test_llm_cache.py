import pytest
from unittest.mock import patch, AsyncMock
from app.services.llm_cache import llm_cache


@pytest.fixture(autouse=True)
def enable_cache():
    old = llm_cache.settings.llm_cache_enabled
    llm_cache.settings.llm_cache_enabled = True
    yield
    llm_cache.settings.llm_cache_enabled = old


class TestLLMCache:
    @pytest.mark.asyncio
    async def test_cache_disabled_returns_none(self):
        llm_cache.settings.llm_cache_enabled = False
        result = await llm_cache.get("some query")
        assert result is None
        llm_cache.settings.llm_cache_enabled = True

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self):
        with patch.object(llm_cache, "_get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_redis
            result = await llm_cache.get("unknown query")
            assert result is None

    @pytest.mark.asyncio
    async def test_set_then_get(self):
        with patch.object(llm_cache, "_get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.get = AsyncMock(return_value="cached response")
            mock_get_client.return_value = mock_redis
            set_ok = await llm_cache.set("test query", "cached response")
            assert set_ok is True
            result = await llm_cache.get("test query")
            assert result == "cached response"

    @pytest.mark.asyncio
    async def test_set_disabled_returns_false(self):
        llm_cache.settings.llm_cache_enabled = False
        result = await llm_cache.set("query", "response")
        assert result is False
        llm_cache.settings.llm_cache_enabled = True

    @pytest.mark.asyncio
    async def test_invalidate_removes_key(self):
        with patch.object(llm_cache, "_get_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_redis
            result = await llm_cache.invalidate("some query")
            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_wipes_keys(self):
        with patch.object(llm_cache, "_get_client") as mock_get_client:
            mock_redis = AsyncMock()

            async def mock_scan_iter(match=None):
                for key in ["llm_cache:key1", "llm_cache:key2"]:
                    yield key

            mock_redis.scan_iter = mock_scan_iter
            mock_redis.delete = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_redis
            result = await llm_cache.clear_all()
            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_error_graceful(self):
        with patch.object(llm_cache, "_get_client") as mock_get_client:
            mock_get_client.side_effect = ConnectionError("Redis down")
            result = await llm_cache.get("any query")
            assert result is None
