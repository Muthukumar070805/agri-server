from fastapi import APIRouter, Request, Response

from app.adapters.exotel import (
    CallContext,
    build_twiml_stream_response,
    build_twiml_hangup_response,
    get_websocket_url,
)
from app.core.logger import setup_logger

router = APIRouter(prefix="/voice", tags=["voice"])
logger = setup_logger("voice")


@router.post(
    "/incoming",
    summary="Exotel inbound call webhook — returns TwiML to start audio stream",
)
async def handle_incoming_call(request: Request) -> Response:
    """
    Called by Exotel when a customer dials the ExoPhone.

    Exotel POSTs form fields:
      CallSid, From, To, CallStatus, digits (optional), ...
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    from_number = form.get("From", "unknown")
    to_number = form.get("To", "unknown")
    call_status = form.get("CallStatus", "unknown")

    ctx = CallContext(
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        call_status=call_status,
    )

    logger.info(
        "incoming_call",
        extra={
            "call_sid": ctx.call_sid,
            "from": ctx.from_number,
            "to": ctx.to_number,
            "status": ctx.call_status,
        },
    )

    if ctx.call_status in ("completed", "busy", "failed", "no-answer"):
        return Response(
            content=build_twiml_hangup_response(),
            media_type="application/xml",
        )

    ws_url = get_websocket_url()
    language = form.get("language", "ta")
    logger.info("starting_stream", extra={"call_sid": call_sid, "ws_url": ws_url})
    return Response(
        content=build_twiml_stream_response(
            ws_url, call_sid, from_number, to_number, language
        ),
        media_type="application/xml",
    )
