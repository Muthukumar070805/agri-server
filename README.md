# agri-server

AI voice/text assistant for farmer helpline. FastAPI + LangGraph + Ollama/Mistral.

## Quick Start

```bash
# Setup
.venv\Scripts\activate
uv pip install -e .

# Run (Ollama must be running separately)
.venv\Scripts\python.exe main.py
```

## Docker

```bash
docker compose up --build
```

Services: `api` (port 8000), `redis` (6379), `ollama` (11434).

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Notes |
|----------|----------|-------|
| `PROVIDER` | No | `ollama` (default) or `mistral` |
| `MISTRAL_API_KEY` | If `PROVIDER=mistral` | — |
| `PINECONE_API_KEY` | For RAG | Returns empty results if missing |
| `OLLAMA_BASE_URL` | If `PROVIDER=ollama` | Default `http://localhost:11434` |

See `.env.example` for all options.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root probe |
| `/health` | GET | Health check |
| `/health/circuits` | GET | Circuit breaker states |
| `/health/sessions` | GET | Session backend status |
| `/chat/text` | POST | Text chat (query + session_id) |
| `/ws/chat` | WS | WebSocket chat with token streaming |

## Tests

```bash
uv run pytest tests/test_unit/ -v -x --timeout=60
uv run pytest tests/test_integration/ -v -x --timeout=120
uv run pytest tests/ -v --timeout=120
```

## Smoke Test

```bash
python scripts/smoke_test.py
```
