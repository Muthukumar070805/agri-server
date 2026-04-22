from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nest_asyncio
nest_asyncio.apply()

from app.websocket.handler import handle_websocket
from app.api.text_chat import router
from app.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Server starting...")
    yield
    logger.info("Server shutting down")


app = FastAPI(
    title="agri-server",
    description="AI voice/text assistant for farmer helpline",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "agri-server running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket, session_id: str = Query(default="default")
):
    await handle_websocket(websocket, session_id)


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
