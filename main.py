from fastapi import FastAPI, WebSocket, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timedelta
import uvicorn
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nest_asyncio

nest_asyncio.apply()

from app.websocket.handler import handle_websocket  # noqa: E402
from app.api.text_chat import router  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.services.rag import preload_reranker  # noqa: E402

logger = get_logger(__name__)


ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
).split(",")
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "10240"))  # 10KB default
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)


def _clean_old_entries(client_id: str):
    cutoff = datetime.utcnow() - timedelta(seconds=RATE_LIMIT_WINDOW)
    _rate_limit_store[client_id] = [
        ts for ts in _rate_limit_store[client_id] if ts > cutoff
    ]


def _check_rate_limit(client_id: str) -> bool:
    _clean_old_entries(client_id)
    return len(_rate_limit_store[client_id]) < RATE_LIMIT_REQUESTS


def _record_request(client_id: str):
    _rate_limit_store[client_id].append(datetime.utcnow())


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.session import session_manager
    from app.core.config import validate_required_keys

    logger.info("Server starting...")

    missing_keys = validate_required_keys()
    if missing_keys:
        logger.warning(f"Config issues detected: {missing_keys}. Check .env file.")

    def _preload():
        try:
            preload_reranker()
        except Exception as e:
            logger.error(f"Failed to preload reranker: {e}")

    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()

    session_manager.start_cleanup_task()
    logger.info("Session cleanup task started")

    yield

    await session_manager.stop_cleanup_task()
    thread.join(timeout=5)
    logger.info("Server shutting down")


app = FastAPI(
    title="agri-server",
    description="AI voice/text assistant for farmer helpline",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=413,
            content={
                "detail": f"Request too large. Max size: {MAX_REQUEST_SIZE} bytes"
            },
        )
    response = await call_next(request)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/ws") or request.url.path.startswith("/health"):
        return await call_next(request)

    client_id = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_id):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s"
            },
        )
    _record_request(client_id)
    return await call_next(request)


@app.get("/")
async def read_root():
    return {"message": "agri-server running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/circuits")
async def circuit_health():
    from app.resilience.circuit_breaker import _circuits

    return {
        name: {
            "state": cb.state.value,
            "failures": cb._failure_count,
            "last_failure": cb._last_failure_time.isoformat()
            if cb._last_failure_time
            else None,
        }
        for name, cb in _circuits.items()
    }


@app.get("/health/sessions")
async def session_health():
    from app.services.session import session_manager
    from app.core.config import get_settings

    settings = get_settings()
    redis_mgr = session_manager._get_redis_manager()

    if not settings.session_redis_enabled:
        return {
            "backend": "memory",
            "sessions": len(session_manager._memory_sessions),
            "status": "active",
        }

    if redis_mgr:
        try:
            client = await redis_mgr._get_client()
            await client.ping()
            return {
                "backend": "redis",
                "sessions": len(session_manager._memory_sessions),
                "status": "connected",
            }
        except Exception as e:
            return {
                "backend": "redis",
                "sessions": len(session_manager._memory_sessions),
                "status": "error",
                "error": str(e),
            }

    return {"status": "unknown"}


@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket, session_id: str = Query(default="default")
):
    await handle_websocket(websocket, session_id)


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
