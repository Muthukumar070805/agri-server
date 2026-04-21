from typing import Optional
from datetime import datetime, timedelta
import json

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


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionData] = {}

    def get_or_create(self, session_id: str) -> SessionData:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData(session_id)
            logger.info(f"Created new session: {session_id}")
        else:
            session = self._sessions[session_id]
            if session.is_expired():
                session.messages = []
                session.last_activity = datetime.utcnow()
                logger.info(f"Reset expired session: {session_id}")
        return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionData]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")

    def cleanup_expired(self, ttl_minutes: int = 30):
        expired = [
            sid for sid, s in self._sessions.items() if s.is_expired(ttl_minutes)
        ]
        for sid in expired:
            self.delete(sid)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


session_manager = SessionManager()
