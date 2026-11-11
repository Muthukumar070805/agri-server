"""Local desktop audio test script for Sarvam AI TTS playback.

Requires optional dependency: pyaudio (pip install .[audio])
"""

import asyncio
import base64
import queue
import shutil
import subprocess
import threading

from app.core.config import get_settings


def play_stream():
    try:
        import pyaudio
    except ImportError:
        print("pyaudio is not installed. Install with: pip install .[audio]")
        return

    settings = get_settings()
    api_key = settings.sarvam_api_key
    if not api_key:
        print("SARVAM_API_KEY not configured in .env")
        return

    from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
    audio_queue = queue.Queue()

    def audio_player():
        while True:
            chunk = audio_queue.get()
            if chunk is None:
                break
            stream.write(chunk)

    threading.Thread(target=audio_player, daemon=True).start()

    ffmpeg_process = subprocess.Popen(  # noqa: S603
        [
            ffmpeg_bin,
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "22050",
            "pipe:1",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    async def _stream():
        client = AsyncSarvamAI(api_subscription_key=api_key)
        async with client.text_to_speech_streaming.connect(
            model="bulbul:v3", send_completion_event=True
        ) as ws:
            await ws.configure(target_language_code="hi-IN", speaker="shubh")
            await ws.convert("नमस्ते, मैं आपकी क्या सहायता कर सकता हूँ?")
            await ws.flush()

            async for message in ws:
                if isinstance(message, AudioOutput):
                    mp3_chunk = base64.b64decode(message.data.audio)
                    if ffmpeg_process.stdin:
                        ffmpeg_process.stdin.write(mp3_chunk)
                    if ffmpeg_process.stdout:
                        pcm_data = ffmpeg_process.stdout.read(4096)
                        if pcm_data:
                            audio_queue.put(pcm_data)
                elif (
                    isinstance(message, EventResponse)
                    and message.data.event_type == "final"
                ):
                    break
        audio_queue.put(None)

    asyncio.run(_stream())


if __name__ == "__main__":
    play_stream()
