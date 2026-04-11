from dataclasses import dataclass
from app.core.config import get_settings


@dataclass
class CallContext:
    call_sid: str
    from_number: str
    to_number: str
    call_status: str


def build_twiml_stream_response(
    ws_url: str,
    call_sid: str,
    from_number: str,
    to_number: str,
    language: str = "ta",
) -> str:
    stream_url = f"{ws_url}?call_sid={call_sid}&phone={from_number}&language={language}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Stream transport="websocket" '
        f'url="{stream_url}" '
        'contentType="audio/x-mulaw" '
        'direction="both"/>'
        "</Response>"
    )


def build_twiml_hangup_response() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'


def get_websocket_url(path: str = "/voice/stream") -> str:
    settings = get_settings()
    scheme = "wss" if settings.BASE_URL.startswith("https") else "ws"
    base = settings.BASE_URL.replace("http://", "").replace("https://", "")
    return f"{scheme}://{base}{path}"
