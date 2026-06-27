import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_tool_node_uses_farm_id_from_state():
    from app.agent.nodes import tool_node

    state = {
        "query": "weather",
        "query_type": "tool",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "farm-42",
        "stream_callback": None,
    }

    async def fake_get_farm_data(farm_id):
        assert farm_id == "farm-42"
        return '{"weather": {"temp_C": 30}}'

    with patch("app.agent.tools.get_farm_data", side_effect=fake_get_farm_data):
        result = await tool_node(state)

    assert result["tool_data"]["weather"]["temp_C"] == 30


@pytest.mark.asyncio
async def test_tool_node_json_parse_failure():
    from app.agent.nodes import tool_node

    state = {
        "query": "weather",
        "query_type": "tool",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    async def fake_get_farm_data(farm_id):
        return "not valid json"

    with patch("app.agent.tools.get_farm_data", side_effect=fake_get_farm_data):
        result = await tool_node(state)

    assert result["tool_data"] == {}


@pytest.mark.asyncio
async def test_tool_node_non_tool_query():
    from app.agent.nodes import tool_node

    state = {
        "query": "hello",
        "query_type": "direct",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    result = await tool_node(state)
    assert result["tool_data"] == {}
