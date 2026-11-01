import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_classify_pushes_early_ack():
    from app.agent.nodes import classify

    tokens = []

    async def cb(token):
        tokens.append(token)

    state = {
        "query": "weather in chennai",
        "query_type": "direct",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": cb,
    }

    with patch("app.agent.nodes.classify_query") as mock_cq:
        mock_cq.return_value = ("tool", {"type": None})
        with patch("app.agent.tools.get_farm_data") as mock_gfd:
            mock_gfd.return_value = '{"weather": {"temp_C": 30}}'
            result = await classify(state)

    assert tokens[0] == "_ack_"
    assert result["query_type"] == "tool"


@pytest.mark.asyncio
async def test_classify_prefetches_tool_data():
    from app.agent.nodes import classify

    state = {
        "query": "weather in chennai",
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

    with (
        patch("app.agent.nodes.classify_query") as mock_cq,
        patch("app.agent.tools.get_farm_data") as mock_gfd,
    ):
        mock_cq.return_value = ("tool", {"type": None})
        mock_gfd.return_value = '{"weather": {"temp_C": 30}}'
        result = await classify(state)

    assert "tool_data" in result
    assert result["tool_data"]["weather"]["temp_C"] == 30


@pytest.mark.asyncio
async def test_classify_prefetches_scheme_data():
    from app.agent.nodes import classify

    state = {
        "query": "pm kisan loan",
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

    with (
        patch("app.agent.nodes.classify_query") as mock_cq,
        patch("app.services.rag.aquery_schemes") as mock_raq,
    ):
        mock_cq.return_value = ("scheme", {"type": "credit_loan"})
        mock_raq.return_value = {"schemes": [{"content": "PM Kisan"}]}
        result = await classify(state)

    assert result["scheme_data"]["schemes"][0]["content"] == "PM Kisan"


@pytest.mark.asyncio
async def test_classify_no_ack_without_callback():
    from app.agent.nodes import classify

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

    with patch("app.agent.nodes.classify_query") as mock_cq:
        mock_cq.return_value = ("direct", {})
        result = await classify(state)

    assert result["query_type"] == "direct"


@pytest.mark.asyncio
async def test_classify_cancels_prefetch_on_disagreement():
    from app.agent.nodes import classify

    state = {
        "query": "weather in chennai",
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

    with (
        patch("app.models.classify._fast_classify") as mock_fast,
        patch("app.agent.nodes.classify_query") as mock_cq,
        patch("app.agent.tools.get_farm_data") as mock_gfd,
    ):
        mock_fast.return_value = ("tool", {"type": None})
        mock_cq.return_value = ("direct", {})
        mock_gfd.return_value = '{"weather": {"temp_C": 30}}'
        result = await classify(state)

    assert result["query_type"] == "direct"
    assert result["tool_data"] == {}


@pytest.mark.asyncio
async def test_tool_node_skips_if_data_already_in_state():
    from app.agent.nodes import tool_node

    state = {
        "query": "weather",
        "query_type": "tool",
        "filters": {},
        "tool_data": {"weather": {"temp_C": 30}},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    with patch("app.agent.tools.get_farm_data") as mock_gfd:
        result = await tool_node(state)

    assert result["tool_data"]["weather"]["temp_C"] == 30
    mock_gfd.assert_not_called()


@pytest.mark.asyncio
async def test_rag_node_skips_if_data_already_in_state():
    from app.agent.nodes import rag_node

    state = {
        "query": "pm kisan",
        "query_type": "scheme",
        "filters": {"type": "credit_loan"},
        "tool_data": {},
        "scheme_data": {"schemes": [{"content": "PM Kisan"}]},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    with patch("app.services.rag.aquery_schemes") as mock_raq:
        result = await rag_node(state)

    assert result["scheme_data"]["schemes"][0]["content"] == "PM Kisan"
    mock_raq.assert_not_called()


@pytest.mark.asyncio
async def test_rag_node_uses_cache_when_enabled():
    from app.agent.nodes import rag_node
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.llm_cache_enabled
    settings.llm_cache_enabled = True

    state = {
        "query": "pm kisan",
        "query_type": "scheme",
        "filters": {"type": "credit_loan"},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "farm_id": "default",
        "stream_callback": None,
    }

    with (
        patch("app.services.redis_cache.redis_cache.get") as mock_get,
        patch("app.services.rag.aquery_schemes") as mock_raq,
    ):
        mock_get.return_value = json.dumps({"schemes": [{"content": "CACHED"}]})
        result = await rag_node(state)

    assert result["scheme_data"]["schemes"][0]["content"] == "CACHED"
    mock_raq.assert_not_called()

    settings.llm_cache_enabled = original
