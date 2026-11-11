import os
import sys
import threading
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import uvicorn
from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nest_asyncio

nest_asyncio.apply()

from app.api.text_chat import router  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.services.rag import preload_reranker  # noqa: E402
from app.websocket.handler import handle_websocket  # noqa: E402

logger = get_logger(__name__)


ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
).split(",")
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "10240"))  # 10KB default
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)


def _clean_old_entries(client_id: str):
    cutoff = datetime.now(UTC) - timedelta(seconds=RATE_LIMIT_WINDOW)
    filtered = [ts for ts in _rate_limit_store.get(client_id, []) if ts > cutoff]
    if filtered:
        _rate_limit_store[client_id] = filtered
    elif client_id in _rate_limit_store:
        del _rate_limit_store[client_id]

    if len(_rate_limit_store) > 1000:
        stale = [
            cid
            for cid, times in _rate_limit_store.items()
            if not any(ts > cutoff for ts in times)
        ]
        for cid in stale:
            del _rate_limit_store[cid]


def _check_rate_limit(client_id: str) -> bool:
    _clean_old_entries(client_id)
    return len(_rate_limit_store.get(client_id, [])) < RATE_LIMIT_REQUESTS


def _record_request(client_id: str):
    _rate_limit_store[client_id].append(datetime.now(UTC))


async def _check_rate_limit_distributed(client_id: str) -> bool:
    from app.services.redis_cache import redis_cache

    key = f"rate_limit:{client_id}"
    try:
        client = await redis_cache.get_client()
        now = datetime.now(UTC).timestamp()
        cutoff = now - RATE_LIMIT_WINDOW

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, RATE_LIMIT_WINDOW + 10)
        results = await pipe.execute()
        req_count = results[2]
        return req_count <= RATE_LIMIT_REQUESTS
    except Exception:  # noqa: BLE001 - fallback to memory limiter on Redis failure
        if not _check_rate_limit(client_id):
            return False
        _record_request(client_id)
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.config import validate_required_keys
    from app.services.rag import validate_rag_index_compatibility
    from app.services.session import session_manager

    logger.info("Server starting...")

    missing_keys = validate_required_keys()
    if missing_keys:
        logger.warning(f"Config issues detected: {missing_keys}. Check .env file.")

    try:
        validate_rag_index_compatibility()
    except Exception as e:
        logger.critical(f"RAG Startup Refusal: {e}")
        raise

    def _preload():
        try:
            preload_reranker()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to preload reranker: {e}")

    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()

    from app.models.reasoning import get_reasoning_llm

    try:
        get_reasoning_llm()
        logger.info("ReasoningLLM pre-loaded (warm)")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Could not pre-warm ReasoningLLM: {e}. Will lazy-init on first request."
        )

    session_manager.start_cleanup_task()
    logger.info("Session cleanup task started")

    yield

    await session_manager.stop_cleanup_task()
    await session_manager.close()
    from app.services.llm_cache import llm_cache
    from app.services.redis_cache import redis_cache

    await redis_cache.close()
    await llm_cache.close()
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
    if content_length:
        try:
            length_val = int(content_length)
            if length_val < 0:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if length_val > MAX_REQUEST_SIZE:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request too large. Max size: {MAX_REQUEST_SIZE} bytes"
                        )
                    },
                )
        except (ValueError, TypeError):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )
    elif "chunked" in request.headers.get("transfer-encoding", "").lower():
        body = await request.body()
        if len(body) > MAX_REQUEST_SIZE:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={
                    "detail": (f"Request too large. Max size: {MAX_REQUEST_SIZE} bytes")
                },
            )
    response = await call_next(request)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/ws") or request.url.path.startswith("/health"):
        return await call_next(request)

    client_id = request.client.host if request.client else "unknown"
    if not await _check_rate_limit_distributed(client_id):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} "
                    f"requests per {RATE_LIMIT_WINDOW}s"
                )
            },
        )
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
            "failures": cb.snapshot()["failures"],
            "last_failure": cb.snapshot()["last_failure"],
        }
        for name, cb in _circuits.items()
    }


@app.get("/health/sessions")
async def session_health():
    from app.core.config import get_settings
    from app.services.session import session_manager

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
        except Exception as e:  # noqa: BLE001
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
    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
