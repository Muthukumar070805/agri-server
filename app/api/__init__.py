from fastapi import APIRouter
from app.api.text_chat import router as text_chat_router

__all__ = ["text_chat_router"]
