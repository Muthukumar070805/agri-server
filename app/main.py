from fastapi import FastAPI
from app.api.voice import router as voice_router
from app.api.voice_ws import router as voice_ws_router
from app.core.logger import setup_logger

logger = setup_logger("app")

app = FastAPI(title="FastAPI AI Voice Agent")
app.include_router(voice_router)
app.include_router(voice_ws_router)
