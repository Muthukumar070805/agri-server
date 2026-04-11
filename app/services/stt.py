import asyncio
import base64
import json
from typing import Optional

import websockets
from websockets.client import ClientConnection

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.utils.audio import pcm_to_ulaw, resample

logger = setup_logger("stt")

STT_WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"


class STTService:
    def __init__(
        self,
        language_code: str = "en-IN",
        model: str = "saaras:v3",
        sample_rate: int = 16000,
    ):
        self.language_code = language_code
        self.model = model
        self.sample_rate = sample_rate
        self._conn: Optional[ClientConnection] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._transcript_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        settings = get_settings()
        params = {
            "model": self.model,
            "language_code": self.language_code,
            "sample_rate": str(self.sample_rate),
            "input_audio_codec": "pcm_s16le",
            "vad_signals": "true",
        }
        uri = STT_WS_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        self._conn = await websockets.connect(
            uri,
            extra_headers={
                "Api-Subscription-Key": settings.SARVAM_API_KEY,
            },
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info(
            "stt_connected", extra={"model": self.model, "lang": self.language_code}
        )

    async def _recv_loop(self) -> None:
        try:
            async for msg in self._conn:
                if isinstance(msg, str):
                    data = json.loads(msg)
                    evt = data.get("event", "")
                    if evt in ("start", "end"):
                        logger.debug("vad_event", extra={"event": evt})
                    elif data.get("transcript"):
                        self._transcript_queue.put_nowait(data["transcript"])
                        logger.debug(
                            "stt_transcript", extra={"text": data["transcript"]}
                        )
                    elif data.get("error"):
                        logger.error("stt_error", extra={"error": data["error"]})
        except Exception as e:
            logger.error("stt_recv_error", extra={"error": str(e)})

    async def send_audio(self, ulaw_bytes: bytes) -> None:
        if not self._conn:
            return
        pcm = ulaw_to_pcm(ulaw_bytes)
        pcm_16k = resample(pcm, 8000, self.sample_rate)
        payload = {
            "encoding": "pcm_s16le",
            "sample_rate": self.sample_rate,
            "audio": base64.b64encode(pcm_16k).decode(),
        }
        await self._conn.send(json.dumps(payload))

    async def flush(self) -> None:
        if self._conn:
            await self._conn.send(json.dumps({"event": "flush"}))

    async def get_transcript(self, timeout: float = 10.0) -> Optional[str]:
        try:
            return await asyncio.wait_for(self._transcript_queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._conn:
            await self._conn.close()
            self._conn = None
        logger.info("stt_closed")
