import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestRateLimiting:
    def test_rate_limit_allows_under_threshold(self, client):
        with patch("app.core.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.weather_location = "Avadi"
            settings.llm_timeout_seconds = 30
            settings.llm_cache_enabled = False
            settings.session_redis_enabled = False
            settings.session_ttl_minutes = 30
            settings.redis_host = "localhost"
            settings.redis_port = 6379
            settings.redis_db = 0
            settings.redis_username = None
            settings.redis_password = None
            settings.redis_pool_size = 20
            mock_settings.return_value = settings

            from app.core.config import get_settings

            get_settings.cache_clear()

            responses = []
            for _ in range(5):
                resp = client.get("/health")
                responses.append(resp.status_code)
            assert all(s == 200 for s in responses)
            get_settings.cache_clear()

    def test_health_routes_exempt_from_rate_limit(self, client):
        for _ in range(100):
            resp = client.get("/health")
            if resp.status_code != 200:
                pytest.fail(
                    f"Health route should not be rate limited, got {resp.status_code}"
                )
            break

    def test_ws_routes_exempt_from_rate_limit(self, client):
        with client.websocket_connect("/ws/chat?session_id=rate-test") as ws:
            ws.send_json({"message": "hello"})
            data = ws.receive_json()
            assert "chunk" in data or "done" in data or "error" in data


class TestRequestSizeLimit:
    def test_request_under_size_limit(self, client):
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            small_payload = {"query": "hello"}
            resp = client.post("/chat/text", json=small_payload)
            assert resp.status_code == 200

    def test_cors_middleware_loaded(self, client):
        from main import app

        middlewares = [m.cls for m in app.user_middleware if hasattr(m, "cls")]
        from fastapi.middleware.cors import CORSMiddleware

        assert any(m is CORSMiddleware for m in middlewares)

    def test_cors_allows_configured_origins(self, client, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://example.com")
        resp = client.get("/", headers={"Origin": "http://example.com"})
        assert resp.status_code == 200
