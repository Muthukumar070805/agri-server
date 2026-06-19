from typing import Optional
from datetime import datetime, timedelta
import json
import asyncio

import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.messages: list[dict] = []
        self.metadata: dict = {}

    def add_message(self, role: str, content: str):
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.last_activity = datetime.utcnow()

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        return datetime.utcnow() - self.last_activity > timedelta(minutes=ttl_minutes)

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict, session_id: str) -> "SessionData":
        session = cls(session_id)
        session.messages = data.get("messages", [])
        session.created_at = datetime.fromisoformat(
            data.get("created_at", datetime.utcnow().isoformat())
        )
        session.last_activity = datetime.fromisoformat(
            data.get("last_activity", datetime.utcnow().isoformat())
        )
        session.metadata = data.get("metadata", {})
        return session


class RedisSessionManager:
    """Redis-backed session manager for horizontal scaling."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._settings = get_settings()

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self._settings.redis_host,
                port=self._settings.redis_port,
                db=self._settings.redis_db,
                username=self._settings.redis_username or None,
                password=self._settings.redis_password or None,
                decode_responses=True,
            )
        return self._client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get_or_create(self, session_id: str) -> SessionData:
        client = await self._get_client()
        key = self._key(session_id)

        data = await client.get(key)
        if data:
            session_dict = json.loads(data)
            return SessionData.from_dict(session_dict, session_id)

        return SessionData(session_id)

    async def save(self, session: SessionData):
        client = await self._get_client()
        key = self._key(session.session_id)

        session_dict = session.to_dict()

        ttl = self._settings.session_ttl_minutes * 60
        await client.set(key, json.dumps(session_dict), ex=ttl)

    async def delete(self, session_id: str):
        client = await self._get_client()
        await client.delete(self._key(session_id))

    async def close(self):
        if self._client:
            await self._client.close()


class SessionManager:
    def __init__(self):
        self._memory_sessions: dict[str, SessionData] = {}
        self._redis_manager: Optional[RedisSessionManager] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def _periodic_cleanup(self):
        """Background task to clean up expired sessions every 60 seconds."""
        while self._running:
            try:
                await asyncio.sleep(60)
                self.cleanup_expired(ttl_minutes=30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")

    def start_cleanup_task(self):
        """Start background cleanup task (call from app lifespan)."""
        if self._cleanup_task is None:
            self._running = True
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._periodic_cleanup())
                    logger.info("Started session cleanup task (async)")
                else:
                    self._cleanup_task = loop.create_task(self._periodic_cleanup())
                    logger.info("Started session cleanup task (sync)")
            except Exception as e:
                logger.warning(f"Could not start cleanup task: {e}")

    async def stop_cleanup_task(self):
        """Stop background cleanup task (call from app shutdown)."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped session cleanup task")

    def _get_redis_manager(self) -> Optional[RedisSessionManager]:
        settings = get_settings()
        if not settings.session_redis_enabled:
            return None
        if self._redis_manager is None:
            self._redis_manager = RedisSessionManager()
        return self._redis_manager

    async def _save_to_redis(self, session: SessionData):
        redis_mgr = self._get_redis_manager()
        if redis_mgr:
            try:
                await redis_mgr.save(session)
                logger.debug(f"Saved session to Redis: {session.session_id}")
            except Exception as e:
                logger.warning(f"Failed to save session to Redis: {e}")

    async def get_or_create(self, session_id: str) -> SessionData:
        redis_mgr = self._get_redis_manager()

        if redis_mgr:
            try:
                return await redis_mgr.get_or_create(session_id)
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to memory: {e}")

        if session_id not in self._memory_sessions:
            self._memory_sessions[session_id] = SessionData(session_id)
            logger.info(f"Created new session (memory): {session_id}")
        else:
            session = self._memory_sessions[session_id]
            if session.is_expired():
                session.messages = []
                session.last_activity = datetime.utcnow()
                logger.info(f"Reset expired session (memory): {session_id}")
        return self._memory_sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionData]:
        return self._memory_sessions.get(session_id)

    def delete(self, session_id: str):
        if session_id in self._memory_sessions:
            del self._memory_sessions[session_id]
            logger.info(f"Deleted session (memory): {session_id}")

        redis_mgr = self._get_redis_manager()
        if redis_mgr:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(redis_mgr.delete(session_id))
                else:
                    loop.run_until_complete(redis_mgr.delete(session_id))
            except Exception as e:
                logger.warning(f"Failed to delete from Redis: {e}")

    def cleanup_expired(self, ttl_minutes: int = 30):
        expired = [
            sid for sid, s in self._memory_sessions.items() if s.is_expired(ttl_minutes)
        ]
        for sid in expired:
            self.delete(sid)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions (memory)")

    async def save_session(self, session: SessionData):
        await self._save_to_redis(session)
        self._memory_sessions[session.session_id] = session


session_manager = SessionManager()
