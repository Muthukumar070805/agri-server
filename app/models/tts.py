import asyncio
import base64
import subprocess
import pyaudio
import threading
import queue

from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse


# ---------------- AUDIO SETUP ----------------
p = pyaudio.PyAudio()

stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=22050,
    output=True
)

audio_queue = queue.Queue()


# ---------------- AUDIO THREAD ----------------
def audio_player():
    while True:
        chunk = audio_queue.get()
        if chunk is None:
            break
        stream.write(chunk)


threading.Thread(target=audio_player, daemon=True).start()


# ---------------- FFMPEG PROCESS ----------------
ffmpeg_process = subprocess.Popen(
    [
        "ffmpeg",
        "-i", "pipe:0",              # input from stdin (MP3)
        "-f", "s16le",               # raw PCM output
        "-acodec", "pcm_s16le",
        "-ac", "1",                  # mono
        "-ar", "22050",              # sample rate
        "pipe:1"
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL
)


# ---------------- MAIN ----------------
async def tts_stream():
    client = AsyncSarvamAI(api_subscription_key="YOUR_API_KEY")

    async with client.text_to_speech_streaming.connect(
        model="bulbul:v3",
        send_completion_event=True
    ) as ws:

        await ws.configure(
            target_language_code="hi-IN",
            speaker="shubh"
        )

        text = "भारत की संस्कृति विश्व की सबसे प्राचीन और समृद्ध संस्कृतियों में से एक है।"

        await ws.convert(text)
        await ws.flush()

        async for message in ws:

            if isinstance(message, AudioOutput):
                mp3_chunk = base64.b64decode(message.data.audio)

                # Send MP3 to ffmpeg
                ffmpeg_process.stdin.write(mp3_chunk)

                # Read decoded PCM
                pcm_data = ffmpeg_process.stdout.read(4096)

                if pcm_data:
                    audio_queue.put(pcm_data)

            elif isinstance(message, EventResponse):
                if message.data.event_type == "final":
                    break

    audio_queue.put(None)


# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(tts_stream())