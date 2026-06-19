from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestOpenAPISchema:
    def test_openapi_endpoint_exists(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200

    def test_openapi_version(self):
        schema = client.get("/openapi.json").json()
        assert schema["openapi"].startswith("3.")

    def test_all_endpoints_documented(self):
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/" in paths
        assert "/health" in paths
        assert "/health/circuits" in paths
        assert "/health/sessions" in paths
        assert "/chat/text" in paths

    def test_chat_text_request_schema(self):
        schema = client.get("/openapi.json").json()
        chat_path = schema["paths"]["/chat/text"]["post"]
        assert "requestBody" in chat_path

    def test_chat_text_response_schema(self):
        schema = client.get("/openapi.json").json()
        responses = schema["paths"]["/chat/text"]["post"]["responses"]
        assert "200" in responses
        assert "422" in responses

    def test_health_endpoints_documented(self):
        schema = client.get("/openapi.json").json()
        assert "/health" in schema["paths"]

    def test_websocket_endpoint_not_in_openapi(self):
        schema = client.get("/openapi.json").json()
        assert "/ws/chat" not in schema["paths"]
