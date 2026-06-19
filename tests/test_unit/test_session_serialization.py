import pytest
from datetime import datetime, timedelta
from app.services.session import SessionData, SessionManager


class TestSessionDataSerialization:
    def test_to_dict_roundtrip(self):
        original = SessionData("test-123")
        original.add_message("user", "Hello")
        original.add_message("assistant", "Hi")
        original.metadata["crop"] = "paddy"

        data = original.to_dict()
        restored = SessionData.from_dict(data, "test-123")

        assert restored.session_id == original.session_id
        assert len(restored.messages) == 2
        assert restored.messages[0]["role"] == "user"
        assert restored.messages[1]["content"] == "Hi"
        assert restored.metadata["crop"] == "paddy"

    def test_from_dict_with_partial_data(self):
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": "test",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }
        session = SessionData.from_dict(data, "partial-session")
        assert session.session_id == "partial-session"
        assert len(session.messages) == 1
        assert session.metadata == {}

    def test_from_dict_empty_data(self):
        data = {}
        session = SessionData.from_dict(data, "empty-session")
        assert session.session_id == "empty-session"
        assert session.messages == []
        assert session.metadata == {}

    def test_to_dict_includes_isoformat_timestamps(self):
        session = SessionData("ts-test")
        session.add_message("user", "hello")
        data = session.to_dict()
        assert "created_at" in data
        assert "last_activity" in data
        assert (
            data["messages"][0]["timestamp"].endswith("+00:00")
            or "T" in data["messages"][0]["timestamp"]
        )


class TestSessionManagerEdgeCases:
    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self):
        mgr = SessionManager()
        result = mgr.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_removes_from_memory(self):
        mgr = SessionManager()
        session = await mgr.get_or_create("to-delete")
        assert mgr.get("to-delete") is session
        mgr.delete("to-delete")
        assert mgr.get("to-delete") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_sessions(self):
        mgr = SessionManager()
        session = await mgr.get_or_create("expired-session")
        session.last_activity = datetime.utcnow() - timedelta(minutes=31)
        fresh = await mgr.get_or_create("fresh-session")
        mgr.cleanup_expired(ttl_minutes=30)
        assert mgr.get("expired-session") is None
        assert mgr.get("fresh-session") is fresh

    @pytest.mark.asyncio
    async def test_cleanup_expired_keeps_active_sessions(self):
        mgr = SessionManager()
        session = await mgr.get_or_create("active-session")
        mgr.cleanup_expired(ttl_minutes=30)
        assert mgr.get("active-session") is session

    @pytest.mark.asyncio
    async def test_save_session_stores_in_memory(self):
        mgr = SessionManager()
        session = SessionData("save-test")
        session.add_message("user", "hello")
        await mgr.save_session(session)
        stored = mgr.get("save-test")
        assert stored is session
        assert len(stored.messages) == 1

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self):
        mgr = SessionManager()
        s1 = await mgr.get_or_create("session-a")
        s2 = await mgr.get_or_create("session-b")
        s1.add_message("user", "msg for A")
        s2.add_message("user", "msg for B")
        assert len(mgr.get("session-a").messages) == 1
        assert len(mgr.get("session-b").messages) == 1
        assert mgr.get("session-a").messages[0]["content"] == "msg for A"
