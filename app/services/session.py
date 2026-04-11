from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from app.core.logger import setup_logger

logger = setup_logger("session")


@dataclass
class Message:
    role: str
    content: str


@dataclass
class VoiceSession:
    call_sid: str
    phone: str
    language: str = "ta"
    interface: str = "HELPLINE"
    input_type: str = "VOICE"
    messages: list[Message] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        while len(self.messages) > 5:
            self.messages.pop(0)

    def context_prompt(self) -> str:
        history = ""
        for m in self.messages[-5:]:
            history += f"{m.role}: {m.content}\n"
        return history


class SessionStore:
    MAX_TURNS = 5
    _store: dict[str, VoiceSession] = {}

    def get(self, call_sid: str) -> Optional[VoiceSession]:
        return self._store.get(call_sid)

    def create(self, call_sid: str, phone: str, language: str = "ta") -> VoiceSession:
        session = VoiceSession(call_sid=call_sid, phone=phone, language=language)
        self._store[call_sid] = session
        logger.info(
            "session_created",
            extra={"call_sid": call_sid, "phone": phone, "lang": language},
        )
        return session

    def remove(self, call_sid: str) -> None:
        self._store.pop(call_sid, None)
        logger.info("session_removed", extra={"call_sid": call_sid})


session_store = SessionStore()
