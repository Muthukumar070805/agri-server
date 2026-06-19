import pytest
from datetime import datetime, timedelta
from app.services.session import SessionData, SessionManager


def test_session_data_creation():
    session = SessionData("test-123")
    assert session.session_id == "test-123"
    assert len(session.messages) == 0
    assert session.created_at is not None


def test_session_add_message():
    session = SessionData("test-123")
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")

    assert len(session.messages) == 2
    assert session.messages[0]["role"] == "user"
    assert session.messages[1]["role"] == "assistant"


def test_session_expiry():
    session = SessionData("test-123")
    session.last_activity = datetime.utcnow() - timedelta(minutes=31)
    assert session.is_expired(ttl_minutes=30) is True


def test_session_not_expired():
    session = SessionData("test-123")
    session.last_activity = datetime.utcnow()
    assert session.is_expired(ttl_minutes=30) is False


@pytest.mark.asyncio
async def test_session_manager_get_or_create():
    manager = SessionManager()
    session = await manager.get_or_create("new-session")
    assert session.session_id == "new-session"


@pytest.mark.asyncio
async def test_session_manager_returns_existing():
    manager = SessionManager()
    session1 = await manager.get_or_create("existing")
    session1.add_message("user", "test")
    session2 = await manager.get_or_create("existing")
    assert session1 is session2
    assert len(session2.messages) == 1


@pytest.mark.asyncio
async def test_session_manager_clears_expired():
    manager = SessionManager()
    session = await manager.get_or_create("expired")
    session.add_message("user", "test")
    session.last_activity = datetime.utcnow() - timedelta(minutes=31)
    fresh = await manager.get_or_create("expired")
    assert len(fresh.messages) == 0
