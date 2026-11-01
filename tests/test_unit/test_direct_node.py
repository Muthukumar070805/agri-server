from unittest.mock import MagicMock, patch

import pytest


def test_format_scheme_context_excludes_internal_keys():
    from app.agent.nodes import _format_scheme_context

    text = _format_scheme_context(
        {
            "schemes": [{"content": "PM Kisan pays 6000", "type": "credit_loan"}],
            "count": 1,
            "top_score": 0.9,
            "reason": "below_relevance_threshold",
        }
    )
    assert "PM Kisan pays 6000" in text
    assert "top_score" not in text
    assert "reason" not in text


def test_format_scheme_context_empty():
    from app.agent.nodes import _format_scheme_context

    assert _format_scheme_context({"schemes": [], "count": 0}) == ""
    assert _format_scheme_context({}) == ""


def test_build_system_prompt_abstains_without_scheme_data():
    from app.agent.nodes import _build_system_prompt

    prompt = _build_system_prompt(has_scheme_data=False).lower()
    assert "do not have that detail" in prompt
    assert "never invent" in prompt


def test_build_system_prompt_grounds_with_scheme_data():
    from app.agent.nodes import _build_system_prompt

    prompt = _build_system_prompt(has_scheme_data=True).lower()
    assert "ground every claim" in prompt
    assert "do not guess" in prompt


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
