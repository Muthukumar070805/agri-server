from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage


def make_llm_response(
    content: str = '{"query_type": "direct", "filters": {}}',
) -> AIMessage:
    return AIMessage(content=content)


def make_state(query="test", session_id="default", **overrides):
    return {
        "query": query,
        "query_type": "direct",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": session_id,
        **overrides,
    }


def make_session(session_id="test-session"):
    from app.services.session import SessionData

    return SessionData(session_id)


def mock_chat_llm(response_text="Mock response", query_type="direct"):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=make_llm_response(
            f'{{"query_type": "{query_type}", "filters": {{}}}}'
        )
    )
    mock_llm.generate.return_value = response_text
    mock_llm.agenerate = AsyncMock(return_value=response_text)
    mock_llm.stream.return_value = iter([response_text])

    async def _astream(*args, **kwargs):
        yield response_text

    mock_llm.astream = _astream()
    return mock_llm


def mock_provider_selector(query_type="direct", response_text="Mock response"):
    from unittest.mock import MagicMock, patch

    mock_llm = mock_chat_llm(response_text=response_text, query_type=query_type)
    mock_sel = MagicMock()
    mock_sel.get_chat_llm.return_value = mock_llm
    mock_sel.resolve_model.return_value = "test-model"
    mock_sel.get_embeddings.return_value = MagicMock()
    return patch("app.models.classify.ProviderSelector", return_value=mock_sel)
