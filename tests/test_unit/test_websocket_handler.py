from unittest.mock import patch, AsyncMock


class TestWebSocketHandler:
    def test_websocket_accepts_connection(self, client):
        with patch("app.websocket.handler.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "Hello!",
                    "query_type": "direct",
                    "session_id": "test-ws",
                    "scheme_data": {},
                }
            )
            with client.websocket_connect("/ws/chat?session_id=test-ws") as ws:
                ws.send_json({"message": "hello"})
                responses = []
                while True:
                    data = ws.receive_json()
                    if "done" in data and data["done"]:
                        responses.append(data)
                        break
                    responses.append(data)
                assert any("Hello" in str(r) for r in responses)
                done = [r for r in responses if "done" in r][0]
                assert done["query_type"] == "direct"

    def test_websocket_invalid_json(self, client):
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text("this is not json")
            data = ws.receive_json()
            assert data["error"] == "Invalid JSON format"

    def test_websocket_empty_message(self, client):
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"message": ""})
            data = ws.receive_json()
            assert data["error"] == "Empty message"

    def test_websocket_missing_message_key(self, client):
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"other_key": "value"})
            data = ws.receive_json()
            assert data["error"] == "Empty message"

    def test_websocket_default_session_id(self, client):
        with patch("app.websocket.handler.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "default",
                    "scheme_data": {},
                }
            )
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"message": "test"})
                while True:
                    data = ws.receive_json()
                    if "done" in data:
                        assert data["query_type"] == "direct"
                        assert "default" in str(data)
                        break

    def test_websocket_agent_error_fallback(self, client):
        with patch("app.websocket.handler.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(side_effect=RuntimeError("fail"))
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"message": "hello"})
                while True:
                    data = ws.receive_json()
                    if "done" in data and data["done"]:
                        assert "trouble" in data["response"].lower()
                        assert data["query_type"] == "unknown"
                        break

    def test_websocket_returns_done_with_response(self, client):
        with patch("app.websocket.handler.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "streamed response",
                    "query_type": "direct",
                    "session_id": "stream-test",
                    "scheme_data": {},
                }
            )
            with client.websocket_connect("/ws/chat?session_id=stream-test") as ws:
                ws.send_json({"message": "tell me something"})
                while True:
                    data = ws.receive_json()
                    if "done" in data:
                        assert data["response"] == "streamed response"
                        assert data["session_id"] == "stream-test"
                        assert data["query_type"] == "direct"
                        break

    def test_websocket_disconnect_clean(self, client):
        with patch("app.websocket.handler.agent") as mock_agent:
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "response": "ok",
                    "query_type": "direct",
                    "session_id": "disc-test",
                    "scheme_data": {},
                }
            )
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"message": "hello"})
                ws.close()
