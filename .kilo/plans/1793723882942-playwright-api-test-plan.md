# Plan: Test all agri-server HTTP APIs with playwright-cli

## Goal
Test every HTTP API endpoint on the agri-server FastAPI app using playwright-cli eval + fetch, with custom inputs and captured response outputs. Ollama is now running so `/chat/text` should return live LLM responses instead of 500 errors.

## Prerequisites (verify before executing)

| # | Check | Command / expected |
|---|---|---|
| 1 | playwright-cli installed | `playwright-cli --version` → v0.1.23 |
| 2 | agri-server running | `uv run python -m uvicorn main:app --reload --port 8001` (port 8000 occupied by unrelated shipment/seller API) |
| 3 | Ollama running | `ollama serve` + models pulled: `qwen2.5:0.5b` (classify), `gemma4:e2b` (reasoning) |
| 4 | `.env` model names match Ollama | `OLLAMA_FLASH_MODEL=qwen2.5:0.5b`, `OLLAMA_REASONING_MODEL=gemma4:e2b` — if retired model returns 410 Gone, swap in `.env` |

**Base URL**: `http://localhost:8001` (run eval from same-origin docs page to avoid CORS)

## Workarounds documented (from prior run)

| Issue | Fix |
|---|---|
| `open about:blank` fails (ChildProcess.kill) | Use `goto http://localhost:8001/docs` |
| CORS blocks cross-origin fetch | Run eval from same-origin docs page |
| `eval` rejects `var`/`const`/multi-statement | Use single-expression IIFE `(()=>{...})()` |
| Console output captured in `.playwright-cli\console-*.log` | Read after each eval; unique filename per test |
| `r.ok?r.json():Promise.reject()` loses body on error | Use `r.text().then(t=>({status:r.status,body:t}))` to capture body on all statuses |

## HTTP API endpoints under test

| # | Endpoint | Method | Custom input | Expected output |
|---|---|---|---|---|
| 1 | `GET /` | none | — | `{"message":"agri-server running"}` (200) |
| 2 | `GET /health` | none | — | `{"status":"healthy"}` (200) |
| 3 | `GET /health/circuits` | none | — | dict keyed by circuit name (`classify-llm`, `pinecone`, `redis`), each with `state`, `failures`, `last_failure` (200) |
| 4 | `GET /health/sessions` | none | — | `{"backend":"memory","sessions":N,"status":"active"}` (200) — Redis disabled per `.env` |
| 5 | `POST /chat/text` | JSON | `{"query":"weather in punjab","session_id":"sess_weather"}` | 200 `ChatResponse`, `query_type=="tool"`, non-empty `response` |
| 6 | `POST /chat/text` | JSON | `{"query":"PM Kisan scheme details","session_id":"sess_scheme"}` | 200 `ChatResponse`, `query_type=="scheme"`, `scheme_list` array |
| 7 | `POST /chat/text` | JSON | `{"query":"hello","session_id":"sess_greeting"}` | 200 `ChatResponse`, `query_type=="direct"` |
| 8 | `POST /chat/text` | JSON | `{"query":"soil health card scheme","session_id":"sess_soil"}` | 200 `ChatResponse`, `query_type=="scheme"` (scheme-before-tool rule) |
| 9 | `POST /chat/text` | JSON | `{"query":"","session_id":"sess_empty"}` | 400 `{"detail":"Query cannot be empty"}` |
| 10 | `POST /chat/text` | JSON | `{"query":"<11KB string>","session_id":"sess_long"}` | 413 `{"detail":"Request too large..."}` (MAX_REQUEST_SIZE=10240) |

> WebSocket `/ws/chat` is NOT HTTP — out of scope for this plan.

## playwright-cli commands per test

Navigate once (same-origin):
```
playwright-cli goto http://localhost:8001/docs
```

Each fetch (run from docs page; body captured on all statuses):
```
playwright-cli eval "(()=>{fetch('/health').then(r=>r.text().then(t=>({status:r.status,body:t}))).then(j=>console.log('HEALTH:',JSON.stringify(j))).catch(e=>console.log('HEALTH ERR:',e.message))})()"
```

POST /chat/text with custom body (escape inner quotes):
```
playwright-cli eval "(()=>{fetch('/chat/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:'weather in punjab',session_id:'sess_weather'})}).then(r=>r.text().then(t=>({status:r.status,body:t}))).then(j=>console.log('CHAT_TOOL:',JSON.stringify(j))).catch(e=>console.log('CHAT_TOOL ERR:',e.message))})()"
```

Repeat for tests 5–8, changing `query` and `session_id`. Use unique `session_id` per test to avoid session-state cross-contamination.

Error-path test (400 empty query):
```
playwright-cli eval "(()=>{fetch('/chat/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:'',session_id:'sess_empty'})}).then(r=>r.text().then(t=>({status:r.status,body:t}))).then(j=>console.log('EMPTY:',JSON.stringify(j))).catch(e=>console.log('EMPTY ERR:',e.message))})()"
```

Error-path test (413 oversized query — ~11KB string):
```
playwright-cli eval "(()=>{fetch('/chat/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:'x'.repeat(11000),session_id:'sess_long'})}).then(r=>r.text().then(t=>({status:r.status,body:t}))).then(j=>console.log('LONG:',JSON.stringify(j))).catch(e=>console.log('LONG ERR:',e.message))})()"
```

After each test block:
```
playwright-cli snapshot --filename=api-test-<n>.yml
```

## Success criteria

- playwright-cli `--version` returns v0.1.23
- Server starts on 8001, docs page title "agri-server - Swagger UI"
- `GET /health` → `{"status":"healthy"}` (200)
- `GET /health/circuits` returns dict with `classify-llm`, `pinecone`, `redis` entries (200)
- `GET /health/sessions` returns `backend=="memory"` (200)
- `POST /chat/text` `"weather in punjab"` → 200, `query_type=="tool"`, non-empty `response`
- `POST /chat/text` `"PM Kisan scheme details"` → 200, `query_type=="scheme"`, `scheme_list` present
- `POST /chat/text` `"hello"` → 200, `query_type=="direct"`
- `POST /chat/text` `"soil health card scheme"` → 200, `query_type=="scheme"`
- `POST /chat/text` empty query → 400 `{"detail":"Query cannot be empty"}`
- `POST /chat/text` 11KB query → 413 `{"detail":"Request too large..."}`
- All console outputs and snapshots saved for review

## Open questions / risks

- Ollama `gemma4:e2b` is slow on CPU (~20-60s per generation per session-ses_e7cb.md) — allow generous time between evals
- Session state persists across POSTs with same `session_id` (in-memory per `.env`) — unique `session_id` per test
- Rate limit: 60 req/60s per IP — space out rapid-fire evals (10 tests is fine within one window)
- If Ollama model name retired → 410 Gone → 500 `Agent error`; swap model in `.env` (working: `gemma4:e2b` per session notes)
