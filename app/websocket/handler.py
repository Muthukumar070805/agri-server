from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio

from app.agent.graph import agent
from app.services.session import session_manager
from app.core.logger import get_logger

logger = get_logger(__name__)


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
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"error": "Invalid JSON format", "session_id": session_id}
                )
                continue

            if not message.strip():
                await websocket.send_json(
                    {"error": "Empty message", "session_id": session_id}
                )
                continue

            session = session_manager.get_or_create(session_id)
            session.add_message("user", message)

            history = session.messages[-10:]

            queue: asyncio.Queue = asyncio.Queue()

            async def on_token(token: str):
                await queue.put(token)

            async def run_agent():
                try:
                    result = await agent.ainvoke(
                        {
                            "query": message,
                            "query_type": "direct",
                            "tool_data": {},
                            "context": history,
                            "response": "",
                            "session_id": session_id,
                            "stream_callback": on_token,
                        }
                    )
                    await queue.put(None)
                    return result
                except Exception as e:
                    logger.error(f"Agent error: {e}")
                    await queue.put(None)
                    return None

            task = asyncio.create_task(run_agent())

            while True:
                token = await queue.get()
                if token is None:
                    break
                await websocket.send_json({"chunk": token})

            try:
                result = await task
                response_text = result.get("response", "No response generated") if result else "Sorry, I'm having trouble processing your request."
            except Exception:
                response_text = "Sorry, I'm having trouble processing your request."

            session.add_message("assistant", response_text)

            await websocket.send_json({
                "done": True,
                "response": response_text,
                "session_id": session_id,
            })

            logger.info(f"Response sent: {response_text[:50]}...")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e), "session_id": session_id})
        except:
            pass