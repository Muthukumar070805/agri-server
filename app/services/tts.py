import base64
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.utils.audio import pcm_to_ulaw

logger = setup_logger("tts")

TTS_URL = "https://api.sarvam.ai/text-to-speech"

LANG_CODE_MAP = {
    "ta": "ta-IN",
    "en": "en-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "bn": "bn-IN",
    "mr": "mr-IN",
    "te": "te-IN",
    "gu": "gu-IN",
}


class TTSService:
    def __init__(
        self,
        language_code: str = "ta-IN",
        model: str = "bulbul:v3",
        speaker: str = "meera",
    ):
        self.language_code = language_code
        self.model = model
        self.speaker = speaker
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def synthesize(self, text: str) -> Optional[bytes]:
        settings = get_settings()
        lang = LANG_CODE_MAP.get(self.language_code, self.language_code)
        payload = {
            "model": self.model,
            "input_text": text,
            "language_code": lang,
            "speaker": self.speaker,
            "audio_output_format": "mulaw",
            "sample_rate": 8000,
        }
        try:
            client = await self._get_client()
            resp = await client.post(
                TTS_URL,
                json=payload,
                headers={
                    "Api-Subscription-Key": settings.SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            audio_b64 = data.get("audio")
            if not audio_b64:
                logger.warning("tts_no_audio", extra={"response": data})
                return None
            ulaw_bytes = base64.b64decode(audio_b64)
            logger.debug(
                "tts_synthesized", extra={"chars": len(text), "bytes": len(ulaw_bytes)}
            )
            return ulaw_bytes
        except Exception as e:
            logger.error("tts_error", extra={"error": str(e)})
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
