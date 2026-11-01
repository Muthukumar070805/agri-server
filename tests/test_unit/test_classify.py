from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_classify_weather_query():
    from langchain_core.messages import AIMessage

    from app.models.classify import classify_query
    from app.resilience.circuit_breaker import CircuitState, get_circuit

    cb = get_circuit("classify-llm")
    cb._failure_count = 0
    cb._state = CircuitState.CLOSED

    mock_response = AIMessage(
        content='{"query_type": "tool", "filters": {"type": null}}'
    )

    with patch("app.models.classify.ProviderSelector") as mock_sel:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_sel_instance = MagicMock()
        mock_sel_instance.get_chat_llm.return_value = mock_llm
        mock_sel_instance.resolve_model.return_value = "mistral-small"
        mock_sel.return_value = mock_sel_instance

        q_type, _ = await classify_query("What is the weather today?")
        assert q_type == "tool"


@pytest.mark.asyncio
async def test_classify_scheme_query():
    from langchain_core.messages import AIMessage

    from app.models.classify import classify_query
    from app.resilience.circuit_breaker import CircuitState, get_circuit

    cb = get_circuit("classify-llm")
    cb._failure_count = 0
    cb._state = CircuitState.CLOSED

    mock_response = AIMessage(
        content='{"query_type": "scheme", "filters": {"type": "credit_loan"}}'
    )

    with patch("app.models.classify.ProviderSelector") as mock_sel:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_sel_instance = MagicMock()
        mock_sel_instance.get_chat_llm.return_value = mock_llm
        mock_sel_instance.resolve_model.return_value = "mistral-small"
        mock_sel.return_value = mock_sel_instance

        q_type, _ = await classify_query("Tell me about PM Kisan scheme")
        assert q_type == "scheme"


@pytest.mark.asyncio
async def test_classify_greeting():
    from langchain_core.messages import AIMessage

    from app.models.classify import classify_query
    from app.resilience.circuit_breaker import CircuitState, get_circuit

    cb = get_circuit("classify-llm")
    cb._failure_count = 0
    cb._state = CircuitState.CLOSED

    mock_response = AIMessage(content='{"query_type": "direct", "filters": {}}')

    with patch("app.models.classify.ProviderSelector") as mock_sel:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_sel_instance = MagicMock()
        mock_sel_instance.get_chat_llm.return_value = mock_llm
        mock_sel_instance.resolve_model.return_value = "mistral-small"
        mock_sel.return_value = mock_sel_instance

        q_type, _ = await classify_query("Hello, how are you?")
        assert q_type == "direct"


@pytest.mark.asyncio
async def test_fallback_classify():
    from app.models.classify import _fallback_classify

    q_type, _ = _fallback_classify("subsidy for farmers")
    assert q_type == "scheme"
    q_type, _ = _fallback_classify("temperature outside")
    assert q_type == "tool"
    q_type, _ = _fallback_classify("thank you")
    assert q_type == "direct"


@pytest.mark.asyncio
async def test_circuit_open_falls_back():
    from app.models.classify import classify_query
    from app.resilience.circuit_breaker import (
        CircuitState,
        get_circuit,
    )

    cb = get_circuit("classify-llm")
    cb._state = CircuitState.OPEN
    cb._last_failure_time = None

    q_type, _ = await classify_query("What is the weather?")
    assert q_type == "tool"

    cb._state = CircuitState.CLOSED


def test_fast_classify_extracts_crop():
    from app.models.classify import _fast_classify

    q_type, filters = _fast_classify("what is the ndvi for paddy")
    assert q_type == "tool"
    assert filters.get("crop") == "paddy"


def test_fast_classify_extracts_scheme_type():
    from app.models.classify import _fast_classify

    q_type, filters = _fast_classify("subsidy for coconut farmers")
    assert q_type == "scheme"
    assert filters.get("type") == "input_subsidy"


def test_fast_classify_no_extraneous_match():
    from app.models.classify import _fast_classify

    q_type, filters = _fast_classify("what is the weather")
    assert q_type == "tool"
    assert filters.get("type") is None


def test_fast_classify_ignores_greeting_prefix():
    from app.models.classify import _fast_classify

    q_type, _ = _fast_classify("hi, what is the weather in chennai")
    assert q_type == "tool"


def test_fast_classify_high_humidity_is_tool():
    from app.models.classify import _fast_classify

    q_type, _ = _fast_classify("high humidity in my field")
    assert q_type == "tool"


def test_fast_classify_notice_is_not_greeting():
    from app.models.classify import _fast_classify

    q_type, _ = _fast_classify("notice about subsidy")
    assert q_type == "scheme"


def test_fast_classify_scheme_wins_over_tool_keyword():
    from app.models.classify import _fast_classify

    q_type, _ = _fast_classify("soil health card scheme")
    assert q_type == "scheme"


def test_fast_classify_okra_is_not_direct():
    from app.models.classify import _fast_classify

    assert _fast_classify("okra prices") is None


def test_fast_classify_word_boundaries():
    from app.models.classify import _fast_classify

    assert _fast_classify("phone number for the office") is None
    assert _fast_classify("training for farmers") is None
    q_type, _ = _fast_classify("soil ph level")
    assert q_type == "tool"
