import asyncio
import contextlib
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.agent.graph import agent
from app.core.logger import get_logger
from app.services.session import session_manager

logger = get_logger(__name__)


async def _forward_token(token: str, queue: asyncio.Queue) -> None:
    await queue.put(token)


async def _run_agent(
    query: str,
    history: list[dict],
    session_id: str,
    queue: asyncio.Queue,
) -> dict | None:
    async def on_token(token: str) -> None:
        await _forward_token(token, queue)

    try:
        result = await agent.ainvoke(
            {
                "query": query,
                "query_type": "direct",
                "filters": {},
                "tool_data": {},
                "scheme_data": {},
                "context": history,
                "response": "",
                "session_id": session_id,
                "stream_callback": on_token,
            }
        )
        await queue.put(None)
        return result
    except Exception as e:  # noqa: BLE001 - surfaced to the client as a fallback
        logger.error(f"Agent error: {e}")
        await queue.put(None)
        return None


async def handle_websocket(websocket: WebSocket, session_id: str = "default"):
    await websocket.accept()
    logger.info(f"WebSocket connected: session_id={session_id}")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received: {data[:100]}...")

            try:
                message_data = json.loads(data)
                message = message_data.get("message", "")
                current_session_id = message_data.get("session_id", session_id)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"error": "Invalid JSON format", "session_id": session_id}
                )
                continue

            if not message.strip():
                await websocket.send_json(
                    {"error": "Empty message", "session_id": current_session_id}
                )
                continue

            session = await session_manager.get_or_create(current_session_id)
            session.add_message("user", message)

            history = session.messages[-10:]

            queue: asyncio.Queue = asyncio.Queue()

            task = asyncio.create_task(
                _run_agent(message, history, current_session_id, queue)
            )

            try:
                while True:
                    token = await queue.get()
                    if token is None:
                        break
                    await websocket.send_json({"chunk": token})

                try:
                    result = await task
                    response_text = (
                        result.get("response", "No response generated")
                        if result
                        else "Sorry, I'm having trouble processing your request."
                    )
                    query_type = (
                        result.get("query_type", "unknown") if result else "unknown"
                    )
                except Exception:  # noqa: BLE001 - fallback text, never break the stream
                    response_text = "Sorry, I'm having trouble processing your request."
                    query_type = "unknown"

                session.add_message("assistant", response_text)

                session_manager.save_in_background(session)

                schemes_data = (
                    result.get("scheme_data", {}).get("schemes", []) if result else []
                )

                await websocket.send_json(
                    {
                        "done": True,
                        "response": response_text,
                        "session_id": current_session_id,
                        "scheme_list": schemes_data,
                        "query_type": query_type,
                    }
                )

                logger.info(f"Response sent: {response_text[:50]}...")
            finally:
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    if session.messages and session.messages[-1].get("role") == "user":
                        session.messages.pop()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session_id={session_id}")
    except Exception as e:  # noqa: BLE001 - handler boundary, log and close
        logger.error(f"WebSocket error: {e}")
        with contextlib.suppress(Exception):
            await websocket.send_json({"error": str(e), "session_id": session_id})
