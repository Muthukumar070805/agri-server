"""TTS streaming service module.

Uses Sarvam AI streaming text-to-speech without local audio device dependencies.
"""

import base64
from collections.abc import AsyncIterator

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def generate_speech_stream(
    text: str,
    target_language_code: str = "hi-IN",
    speaker: str = "shubh",
    model: str = "bulbul:v3",
) -> AsyncIterator[bytes]:
    """Stream synthesized audio chunks from Sarvam AI."""
    settings = get_settings()
    api_key = settings.sarvam_api_key
    if not api_key:
        logger.warning("SARVAM_API_KEY not configured; speech synthesis disabled")
        return

    from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse

    client = AsyncSarvamAI(api_subscription_key=api_key)

    async with client.text_to_speech_streaming.connect(
        model=model, send_completion_event=True
    ) as ws:
        await ws.configure(target_language_code=target_language_code, speaker=speaker)
        await ws.convert(text)
        await ws.flush()

        async for message in ws:
            if isinstance(message, AudioOutput):
                chunk = base64.b64decode(message.data.audio)
                yield chunk
            elif (
                isinstance(message, EventResponse)
                and message.data.event_type == "final"
            ):
                break
