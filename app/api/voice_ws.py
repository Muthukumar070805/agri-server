import asyncio
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logger import setup_logger
from app.services.llm import LLMService
from app.services.session import session_store
from app.services.stt import STTService
from app.services.tts import TTSService
from app.utils.audio import compute_rms

router = APIRouter(prefix="/voice", tags=["voice"])
logger = setup_logger("voice_ws")

AUDIO_SAMPLE_RATE = 8000
CHUNK_DURATION_MS = 40
CHUNK_SIZE = int(AUDIO_SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
SILENCE_THRESHOLD = 150
SILENCE_CHUNKS = 12
MAX_BUFFER_SECONDS = 30
MAX_BUFFER_CHUNKS = int(MAX_BUFFER_SECONDS * 1000 / CHUNK_DURATION_MS)
STT_TIMEOUT = 10.0


async def build_prompt(session, transcript: str) -> str:
    history = session.context_prompt()
    lang_name = {"ta": "Tamil", "en": "English", "hi": "Hindi"}.get(
        session.language, "English"
    )
    return (
        f"<s>[INST] You are a helpful AI assistant for a farmer helpline in {lang_name}. "
        f"Provide clear, concise, and helpful answers about government schemes, farming, "
        f"crops, weather, and agricultural best practices.\n"
        f"Conversation history:\n{history or '(no previous messages)'}\n"
        f"Farmer: {transcript} [/INST]"
    )


class VoicePipeline:
    def __init__(self, ws: WebSocket, call_sid: str, phone: str, language: str = "ta"):
        self.ws = ws
        self.call_sid = call_sid
        self.phone = phone
        self.language = language
        self.audio_buffer: bytearray = bytearray()
        self.silence_streak = 0
        self.running = True
        self.stt: Optional[STTService] = None
        self.tts: Optional[TTSService] = None
        self.llm: Optional[LLMService] = None

    async def start(self) -> None:
        self.stt = STTService(language_code=f"{self.language}-IN")
        self.tts = TTSService(language_code=self.language)
        self.llm = LLMService()
        await self.stt.connect()
        asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        try:
            while self.running:
                try:
                    msg = await asyncio.wait_for(self.ws.receive(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self.audio_buffer:
                        await self._process_buffer()
                    continue

                if msg.type == "binary":
                    self._handle_audio_chunk(bytes(msg.data))
                elif msg.type == "text":
                    logger.debug("ws_text", extra={"msg": msg.text})
                elif msg.type == "disconnect":
                    break
        except WebSocketDisconnect:
            logger.info("ws_disconnected", extra={"call_sid": self.call_sid})
        except Exception as e:
            logger.error("ws_receive_error", extra={"error": str(e)})
        finally:
            await self.cleanup()

    def _handle_audio_chunk(self, chunk: bytes) -> None:
        self.audio_buffer.extend(chunk)
        if len(self.audio_buffer) > MAX_BUFFER_CHUNKS * CHUNK_SIZE:
            self.audio_buffer = self.audio_buffer[-MAX_BUFFER_CHUNKS * CHUNK_SIZE :]

        rms = compute_rms(bytes(self.audio_buffer[-CHUNK_SIZE:]))
        if rms < SILENCE_THRESHOLD:
            self.silence_streak += 1
        else:
            if (
                self.silence_streak >= SILENCE_CHUNKS
                and len(self.audio_buffer) > CHUNK_SIZE * 5
            ):
                asyncio.create_task(self._process_buffer())
            self.silence_streak = 0

    async def _process_buffer(self) -> None:
        if not self.audio_buffer or len(self.audio_buffer) < CHUNK_SIZE * 3:
            return
        audio_copy = bytes(self.audio_buffer)
        self.audio_buffer.clear()
        self.silence_streak = 0

        if self.stt:
            await self.stt.send_audio(audio_copy)
            await self.stt.flush()

        transcript = None
        if self.stt:
            transcript = await self.stt.get_transcript(timeout=STT_TIMEOUT)

        if not transcript or not transcript.strip():
            return

        logger.info(
            "transcript_received", extra={"call_sid": self.call_sid, "text": transcript}
        )

        session = session_store.get(self.call_sid)
        if not session:
            session = session_store.create(self.call_sid, self.phone, self.language)
        session.add_turn("user", transcript)

        prompt = await build_prompt(session, transcript)
        reply = await self.llm.generate(prompt)
        session.add_turn("assistant", reply)

        logger.info("llm_reply", extra={"call_sid": self.call_sid, "reply": reply[:80]})

        if self.tts:
            audio_out = await self.tts.synthesize(reply)
            if audio_out and self.running:
                try:
                    await self.ws.send(bytes(audio_out))
                    logger.debug(
                        "audio_sent",
                        extra={"call_sid": self.call_sid, "bytes": len(audio_out)},
                    )
                except Exception as e:
                    logger.error("audio_send_error", extra={"error": str(e)})

    async def cleanup(self) -> None:
        self.running = False
        if self.stt:
            await self.stt.close()
        if self.tts:
            await self.tts.close()
        if self.llm:
            await self.llm.close()
        session_store.remove(self.call_sid)


@router.websocket("/stream")
async def voice_stream(ws: WebSocket):
    call_sid = ws.query_params.get("call_sid", "unknown")
    phone = ws.query_params.get("phone", "unknown")
    language = ws.query_params.get("language", "ta")

    await ws.accept(binary_format=True)
    logger.info(
        "ws_connected", extra={"call_sid": call_sid, "phone": phone, "lang": language}
    )
    session_store.create(call_sid, phone, language)

    pipeline = VoicePipeline(ws, call_sid, phone, language)
    await pipeline.start()
