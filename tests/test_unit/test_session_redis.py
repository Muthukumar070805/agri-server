import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.session import RedisSessionManager, SessionManager, SessionData
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def enable_redis(monkeypatch):
    monkeypatch.setenv("SESSION_REDIS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.close = AsyncMock(return_value=None)
    return client


class TestRedisSessionManager:

    @pytest.fixture
    def manager(self, mock_client):
        with patch("app.services.session.redis.Redis") as m:
            m.return_value = mock_client
            yield RedisSessionManager()

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, manager, mock_client):
        mock_client.get.return_value = None
        session = await manager.get_or_create("s1")
        assert session.session_id == "s1"
        assert len(session.messages) == 0
        mock_client.get.assert_called_once_with("session:s1")

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, manager, mock_client):
        mock_client.get.return_value = json.dumps({
            "messages": [{"role": "user", "content": "hi", "timestamp": "2024-01-01T00:00:00"}],
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-01T00:00:00",
            "metadata": {"crop": "paddy"},
        })
        session = await manager.get_or_create("s2")
        assert session.session_id == "s2"
        assert len(session.messages) == 1
        assert session.metadata.get("crop") == "paddy"

    @pytest.mark.asyncio
    async def test_save(self, manager, mock_client):
        session = SessionData("s3")
        session.add_message("user", "hello")
        await manager.save(session)
        mock_client.set.assert_called_once()
        key, value = mock_client.set.call_args[0][0], mock_client.set.call_args[0][1]
        assert key == "session:s3"
        parsed = json.loads(value)
        assert len(parsed["messages"]) == 1

    @pytest.mark.asyncio
    async def test_delete(self, manager, mock_client):
        await manager.delete("s4")
        mock_client.delete.assert_called_once_with("session:s4")

    @pytest.mark.asyncio
    async def test_close_triggers_when_client_exists(self, manager, mock_client):
        await manager.get_or_create("s5")
        await manager.close()
        mock_client.close.assert_called_once()

    def test_key_format(self, manager):
        assert manager._key("abc") == "session:abc"


class TestSessionManagerWithRedis:

    @pytest.fixture
    def manager(self, mock_client):
        with patch("app.services.session.redis.Redis") as m:
            m.return_value = mock_client
            mgr = SessionManager()
            yield mgr

    @pytest.mark.asyncio
    async def test_get_or_create_via_redis(self, manager, mock_client):
        mock_client.get.return_value = None
        session = await manager.get_or_create("sm1")
        assert session.session_id == "sm1"
        mock_client.get.assert_called_once_with("session:sm1")

    @pytest.mark.asyncio
    async def test_get_or_create_redis_fallback(self, manager, mock_client):
        mock_client.get.side_effect = ConnectionError("down")
        session = await manager.get_or_create("sm2")
        assert session.session_id == "sm2"
        assert manager.get("sm2") is session

    @pytest.mark.asyncio
    async def test_save_session_stores_in_redis_and_memory(self, manager, mock_client):
        session = SessionData("sm3")
        session.add_message("user", "hello")
        await manager.save_session(session)
        mock_client.set.assert_called_once()
        assert mock_client.set.call_args[0][0] == "session:sm3"
        assert manager.get("sm3") is session

    @pytest.mark.asyncio
    async def test_save_session_redis_failure(self, manager, mock_client):
        mock_client.set.side_effect = RuntimeError("set failed")
        session = SessionData("sm4")
        session.add_message("user", "hello")
        await manager.save_session(session)
        assert manager.get("sm4") is session

    @pytest.mark.asyncio
    async def test_delete_calls_redis(self, manager, mock_client):
        await manager.get_or_create("sm5")
        manager.delete("sm5")
        await asyncio.sleep(0)
        assert manager.get("sm5") is None
        mock_client.delete.assert_called_with("session:sm5")

    @pytest.mark.asyncio
    async def test_delete_redis_failure_handled(self, manager, mock_client):
        await manager.get_or_create("sm6")
        mock_client.delete.side_effect = RuntimeError("del failed")
        manager.delete("sm6")
        await asyncio.sleep(0)
        assert manager.get("sm6") is None

    @pytest.mark.asyncio
    async def test_get_redis_manager_lazy_init(self, mock_client):
        with patch("app.services.session.redis.Redis") as m:
            m.return_value = mock_client
            mgr = SessionManager()
            rm1 = mgr._get_redis_manager()
            rm2 = mgr._get_redis_manager()
            assert rm1 is rm2
            assert rm1 is not None


class TestSessionCleanupTask:

    @pytest.fixture
    def manager(self, mock_client):
        with patch("app.services.session.redis.Redis") as m:
            m.return_value = mock_client
            mgr = SessionManager()
            mgr._running = False
            mgr._cleanup_task = None
            yield mgr

    def test_start_cleanup_task(self, manager):
        manager.start_cleanup_task()
        assert manager._running is True

    def test_start_cleanup_task_idempotent(self, manager):
        manager.start_cleanup_task()
        manager.start_cleanup_task()
        assert manager._running is True

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self, manager):
        manager.start_cleanup_task()
        await manager.stop_cleanup_task()
        assert manager._running is False
        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_noop_when_no_task(self, manager):
        await manager.stop_cleanup_task()
        assert manager._running is False
        assert manager._cleanup_task is None
