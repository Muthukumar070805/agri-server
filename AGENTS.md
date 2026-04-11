# FASTAPI AI SERVER — AGENT GUIDE

## Current State

- `main.py` delegates to `app/main.py` (FastAPI app). The placeholder CRUD stub is replaced.
- `app/` contains the real implementation. Structure below.
- **Phase 1 (Foundation) COMPLETE** — voice pipeline built end-to-end.
- **Phase 2 (Planning) COMPLETE** — multi-agent architecture designed, Redis Queue A2A chosen.
- **NOT YET STARTED** — LangChain/LangGraph, Redis Queue, RAG, Tool Agent, SMS, Text Chat channels.
- Python 3.11+, managed with `.venv` + `uv.lock`.

## Run Commands

```bash
# Dev server
python main.py
# or
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Run tests
pytest

# Install deps
pip install -e .
```

## Implemented

| Layer | File | Status |
|-------|------|--------|
| HTTP webhook | `app/api/voice.py` | `POST /voice/incoming` — receives Exotel POST, returns TwiML Stream response |
| WebSocket | `app/api/voice_ws.py` | `WS /voice/stream` — bidirectional audio loop |
| STT | `app/services/stt.py` | Sarvam WebSocket STT (`saaras:v3`), PCM 16kHz |
| TTS | `app/services/tts.py` | Sarvam REST TTS (`bulbul:v3`), μ-law 8kHz output |
| LLM | `app/services/llm.py` | HuggingFace Inference API |
| Session | `app/services/session.py` | In-memory, last 5 turns per call |
| Audio utils | `app/utils/audio.py` | μ-law↔PCM conversion, RMS VAD, resampling |
| Config | `app/core/config.py` | `pydantic-settings`, reads `.env` |
| Exotel adapter | `app/adapters/exotel.py` | TwiML builder, WS URL builder |

## Audio Pipeline (per call)

```
Exotel (μ-law 8kHz)
    → WS /voice/stream
    → accumulate buffer → RMS VAD (silence detection)
    → μ-law→PCM 16kHz → Sarvam STT WebSocket
    → transcript → HuggingFace LLM
    → reply text → Sarvam TTS REST (mulaw 8kHz)
    → raw μ-law bytes → WS back to Exotel
```

## Multi-Agent Architecture (PLANNED)

### Agents
- **Main Agent** — entry point for all channels (voice, SMS, text chat); routes to RAG/Tool/Handoff
- **RAG Agent** — BLPOP consumer; queries Pinecone for government schemes/subsidies/loans
- **Tool Agent** — BLPOP consumer; queries weather, IoT, GEE data

### A2A Communication
- **Redis Queue (BLPOP)** for guaranteed response delivery. Main Agent `RPUSH`es, awaits on per-request response queues.
- Redis pub/sub only for non-critical async writes (e.g., logging weather to Redis).
- NOT pub/sub, NOT HTTPS REST for A2A.

### LLM Roles
- **Flash LLM** — fast classifier + metadata filter extractor (type, crop filters for RAG)
- **Reasoning LLM** — generates final answer from context
- Same-or-different models: **pending user confirmation**

### RAG Scope
- RAG only fires for **government scheme/subsidy/loan** queries, filtered by `{type, crop}` metadata from Pinecone.
- RAG fail → graceful degradation (continue without context).

### Redis Data (also planned)
| Key | Type | Purpose |
|-----|------|---------|
| `agent:rag:queue` | List | RAG request queue |
| `agent:rag:response:{request_id}` | List | Per-request response queue (TTL: 60s) |
| `agent:tool:queue` | List | Tool request queue |
| `agent:tool:response:{request_id}` | List | Per-request response queue (TTL: 60s) |
| `weather:{lat}:{lon}` | String | Open-Meteo data (TTL: 30 min) |
| `iot:{field_id}` | String | Soil moisture/humidity/temp (TTL: 5 min) |
| `gee:{field_id}` | String | NDVI/land use (TTL: 24 hr) |

### Channels (planned)
1. **Voice** — WS `/voice/stream` (already wired, needs LangGraph integration)
2. **SMS** — POST `/sms/inbound` (Exotel SMS webhook)
3. **Text Chat** — WS `/chat/stream` (Gemini-style text chat)

## LangGraph Graph (PLANNED)

```
Input → classify (Flash LLM) → route → [
    DirectAnswer     — trivial queries
    RAG              — government schemes/subsidies/loans (BLPOP → RAG Agent)
    Tool             — weather/IoT/GEE (BLPOP → Tool Agent)
    Handoff          — emit ASSIST_REQUESTED to log
] → Answer (Reasoning LLM)
```

## System Role (Hard Rules)

This service is **ONLY** intelligence + orchestration. It must NOT:
- store users or chats
- maintain long sessions beyond the call
- own business logic
- call Supabase for user/chat data

## Key Constraints

- Async everywhere; no blocking calls
- No DB imports or persistence layer
- Strict typing; logging per request
- Handoff: emit `{"event": "ASSIST_REQUESTED", ...}` to log only — no DB write
- RAG fail → continue without context (graceful degradation)
- **Pipecat rejected** — use LangChain + LangGraph only

## Project Structure

```
app/
  main.py           # FastAPI app entrypoint
  api/
    voice.py        # POST /voice/incoming (TwiML webhook)
    voice_ws.py     # WS /voice/stream (streaming loop)
    sms.py          # POST /sms/inbound (PLANNED)
    text_chat.py    # WS /chat/stream (PLANNED)
  core/
    config.py       # Settings from .env (needs HF_FLASH/REASONING_MODEL, REDIS_*)
    logger.py       # Structured logging
  services/
    stt.py          # Sarvam WebSocket STT
    tts.py          # Sarvam REST TTS
    llm.py          # HuggingFace Inference LLM (refactor to LangChain PLANNED)
    session.py      # In-memory session store
    redis_queue.py  # Redis BLPOP helpers (PLANNED)
    flash_llm.py    # Classification + filter extraction (PLANNED)
    reasoning_llm.py # Final answer generation (PLANNED)
    rag.py          # LangChain Pinecone RAG (PLANNED)
    rag_agent.py    # RAG BLPOP consumer (PLANNED)
    tool_agent.py   # Tool BLPOP consumer (PLANNED)
    weather.py      # Open-Meteo → Redis (PLANNED)
    iot.py          # Redis reader for IoT data (PLANNED)
    gee.py          # Redis reader for GEE data (PLANNED)
    handoff.py      # ASSIST_REQUESTED emitter (PLANNED)
    ai_flow.py      # LangGraph graph (PLANNED)
  adapters/
    exotel.py       # TwiML response builder
  utils/
    audio.py        # μ-law/PCM conversion, VAD
```

## Env Variables (in `.env`)

`EXOTEL_*`, `SARVAM_API_KEY`, `HUGGINGFACE_ACCESS_TOKEN`, `HF_FLASH_MODEL`, `HF_REASONING_MODEL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `PINECONE_*`, `NEXT_PUBLIC_SUPABASE_*`

> **Known issue**: `.env` has `HUGGI_FACE_ACCESS_TOKEN` (typo) — `config.py` correctly references `HUGGINGFACE_ACCESS_TOKEN`. Fix pending.

## Pending Dependencies (need `pip install`)

- `redis[hiredis]`
- `langchain>=0.3.0`
- `langgraph>=0.2.0`
- `langchain-huggingface`
- `langchain-pinecone`

## Execution Order (next steps)

1. Fix `.env` typo (`HUGGI_FACE` → `HUGGINGFACE`), add Redis + model vars
2. Add `HF_FLASH_MODEL`, `HF_REASONING_MODEL`, `REDIS_*` to `app/core/config.py`
3. Add langchain, langgraph, redis deps to `pyproject.toml`
4. `pip install` dependencies
5. `app/services/redis_queue.py` — Redis client + BLPOP helpers
6. `app/services/weather.py` — Open-Meteo → Redis
7. `app/services/iot.py` — Redis reader
8. `app/services/gee.py` — Dummy Redis reader
9. `app/services/flash_llm.py` — Classification + filter extraction
10. `app/services/reasoning_llm.py` — LangChain reasoning chain
11. `app/services/rag.py` — LangChain Pinecone RAG chain
12. `app/services/llm.py` — Refactor to LangChain
13. `app/services/rag_agent.py` — BLPOP consumer
14. `app/services/tool_agent.py` — BLPOP consumer
15. `app/services/handoff.py` — ASSIST_REQUESTED emitter
16. `app/services/ai_flow.py` — LangGraph graph
17. `app/services/session.py` — Add `handoff_triggered`, `channel`, `metadata` fields
18. `app/api/voice_ws.py` — Update to use ai_flow
19. `app/api/sms.py` — SMS webhook
20. `app/api/text_chat.py` — Text chat WebSocket
21. `app/main.py` — Wire all routers
22. Add tests alongside code

## Reference Docs

- `Exotel_AI_Voice_Agent_API_Reference.md` — Exotel API details
- `.env` — actual API credentials (read-only)

## What NOT to Do

- Do NOT overbuild LangGraph initially
- Do NOT add persistence or user storage
- Do NOT integrate Pipecat
- Do NOT build the full brain — build the brainstem first
- Do NOT import RAG (`app/services/rag.py`) in the voice pipeline yet
