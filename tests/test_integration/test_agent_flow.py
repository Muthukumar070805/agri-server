import pytest
from unittest.mock import patch
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.agent.graph import agent


@pytest.fixture(autouse=True)
def _mock_llm_generate():
    """Prevent integration tests from hitting real LLM APIs."""
    with patch("app.models.reasoning.ReasoningLLM.generate") as mock_gen:
        mock_gen.return_value = (
            "This is a mock response from the LLM for testing purposes."
        )
        yield


@pytest.mark.asyncio
async def test_classify_routes_to_direct(_mock_llm_generate):
    state = {
        "query": "Hello, how are you?",
        "session_id": "test-direct",
        "context": [],
        "tool_data": {},
        "scheme_data": {},
        "response": "",
    }
    result = await agent.ainvoke(state)
    assert result["query_type"] == "direct"
    assert result["response"] != ""


@pytest.mark.asyncio
async def test_tool_node_fetches_farm_data(_mock_llm_generate):
    state = {
        "query": "What's the weather?",
        "session_id": "test-tool",
        "context": [],
        "tool_data": {},
        "scheme_data": {},
        "response": "",
    }
    result = await agent.ainvoke(state)
    assert result["query_type"] == "tool"
    assert "response" in result


@pytest.mark.asyncio
async def test_scheme_routes_to_rag(_mock_llm_generate):
    state = {
        "query": "Tell me about PM Kisan scheme",
        "session_id": "test-scheme",
        "context": [],
        "tool_data": {},
        "scheme_data": {},
        "response": "",
    }
    result = await agent.ainvoke(state)
    assert result["query_type"] in ["scheme", "direct"]


@pytest.mark.asyncio
async def test_agent_returns_response(_mock_llm_generate):
    state = {
        "query": "What is 2+2?",
        "session_id": "test-math",
        "context": [],
        "tool_data": {},
        "scheme_data": {},
        "response": "",
    }
    result = await agent.ainvoke(state)
    assert "response" in result
    assert isinstance(result["response"], str)
