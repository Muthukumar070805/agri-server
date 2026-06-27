import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_direct_node_updates_context():
    from app.agent.nodes import direct_node

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

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Hi there!"

    with patch("app.models.reasoning.get_reasoning_llm", return_value=mock_llm):
        result = await direct_node(state)

    assert len(result["context"]) == 2
    assert result["context"][0]["role"] == "user"
    assert result["context"][0]["content"] == "hello"
    assert result["context"][1]["role"] == "assistant"
    assert result["context"][1]["content"] == "Hi there!"
    assert result["response"] == "Hi there!"


@pytest.mark.asyncio
async def test_direct_node_trims_context():
    from app.agent.nodes import direct_node

    old_context = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    state = {
        "query": "hello",
        "query_type": "direct",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": old_context,
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Hi!"

    with patch("app.models.reasoning.get_reasoning_llm", return_value=mock_llm):
        result = await direct_node(state)

    assert len(result["context"]) <= 10
    assert result["context"][-2] == {"role": "user", "content": "hello"}
    assert result["context"][-1] == {"role": "assistant", "content": "Hi!"}


@pytest.mark.asyncio
async def test_direct_node_non_streaming_executor():
    from app.agent.nodes import direct_node

    state = {
        "query": "test",
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

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "result"

    with patch("app.models.reasoning.get_reasoning_llm", return_value=mock_llm):
        result = await direct_node(state)

    assert result["response"] == "result"
