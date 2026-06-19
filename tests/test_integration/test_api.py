from unittest.mock import patch, AsyncMock
from tests.helpers import validate_chat_response, assert_health_response


class TestRootEndpoint:
    def test_read_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"message": "agri-server running"}


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert_health_response(resp.json())

    def test_health_circuits(self, client):
        resp = client.get("/health/circuits")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_health_sessions_no_redis(self, client, monkeypatch):
        monkeypatch.setenv("SESSION_REDIS_ENABLED", "false")
        resp = client.get("/health/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backend"] == "memory"
        assert data["status"] == "active"
        assert isinstance(data["sessions"], int)


class TestChatTextEndpoint:
    def test_chat_text_basic_query(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "Hello! How can I help you?",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            resp = client.post("/chat/text", json={"query": "hello"})
            assert resp.status_code == 200
            data = resp.json()
            validate_chat_response(data)
            assert data["response"] == "Hello! How can I help you?"
            assert data["query_type"] == "direct"
            assert data["session_id"] == "default"
        get_settings.cache_clear()

    def test_chat_text_with_session_id(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "my-session-1",
                    "scheme_data": {},
                }
            )
            resp = client.post(
                "/chat/text",
                json={"query": "weather update", "session_id": "my-session-1"},
            )
            assert resp.status_code == 200
            assert resp.json()["session_id"] == "my-session-1"
        get_settings.cache_clear()

    def test_chat_text_empty_query(self, client):
        resp = client.post("/chat/text", json={"query": ""})
        assert resp.status_code == 422

    def test_chat_text_whitespace_query(self, client):
        resp = client.post("/chat/text", json={"query": "   "})
        assert resp.status_code == 400

    def test_chat_text_oversized_query(self, client):
        long_query = "x" * 4097
        resp = client.post("/chat/text", json={"query": long_query})
        assert resp.status_code == 422

    def test_chat_text_boundary_min(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            resp = client.post("/chat/text", json={"query": "a"})
            assert resp.status_code == 200
        get_settings.cache_clear()

    def test_chat_text_boundary_max(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            resp = client.post("/chat/text", json={"query": "x" * 4096})
            assert resp.status_code == 200
        get_settings.cache_clear()

    def test_chat_text_missing_query_field(self, client):
        resp = client.post("/chat/text", json={})
        assert resp.status_code == 422

    def test_chat_text_null_query(self, client):
        resp = client.post("/chat/text", json={"query": None})
        assert resp.status_code == 422

    def test_chat_text_wrong_type(self, client):
        resp = client.post("/chat/text", json={"query": 123})
        assert resp.status_code == 422

    def test_chat_text_agent_error(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("LLM failed"))
            resp = client.post("/chat/text", json={"query": "hello"})
            assert resp.status_code == 500
            data = resp.json()
            assert "Agent error" in data["detail"]
        get_settings.cache_clear()

    def test_chat_text_scheme_list_present(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "Here are schemes",
                    "query_type": "scheme",
                    "session_id": "default",
                    "scheme_data": {
                        "schemes": [
                            {
                                "content": "PM Kisan",
                                "crop": "all",
                                "type": "input_subsidy",
                            }
                        ]
                    },
                }
            )
            resp = client.post("/chat/text", json={"query": "schemes for farmers"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["scheme_list"]) == 1
            assert data["scheme_list"][0]["content"] == "PM Kisan"
        get_settings.cache_clear()

    def test_chat_text_unicode_query(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "MSP क्या है",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            resp = client.post("/chat/text", json={"query": "MSP गेहूं क्या है"})
            assert resp.status_code == 200
            data = resp.json()
            assert "MSP" in data["response"]
        get_settings.cache_clear()

    def test_chat_text_session_persistence(self, client, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        agent_results = [
            {
                "response": "First",
                "query_type": "direct",
                "session_id": "persist-test",
                "scheme_data": {},
            },
            {
                "response": "Second",
                "query_type": "direct",
                "session_id": "persist-test",
                "scheme_data": {},
            },
        ]
        with patch("app.api.text_chat.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(side_effect=agent_results)
            r1 = client.post(
                "/chat/text", json={"query": "first msg", "session_id": "persist-test"}
            )
            r2 = client.post(
                "/chat/text", json={"query": "second msg", "session_id": "persist-test"}
            )
            assert r1.status_code == 200
            assert r2.status_code == 200
        get_settings.cache_clear()
