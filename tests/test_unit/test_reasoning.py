import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_astream_cached_returns_full_string():
    from app.models.reasoning import ReasoningLLM

    mock_llm = MagicMock()
    mock_sel_instance = MagicMock()
    mock_sel_instance.get_chat_llm.return_value = mock_llm

    with patch("app.models.reasoning.llm_cache") as mock_cache, \
         patch("app.models.reasoning.ProviderSelector", return_value=mock_sel_instance):
        mock_cache.get = AsyncMock(return_value="cached full response")

        llm = ReasoningLLM(model="test")

        tokens = []
        async for token in llm.astream("test prompt", system="system"):
            tokens.append(token)

        assert len(tokens) == 1
        assert tokens[0] == "cached full response"


@pytest.mark.asyncio
async def test_astream_no_cache_streams():
    from app.models.reasoning import ReasoningLLM

    async def fake_stream(prompt, system):
        yield "chunk1"
        yield "chunk2"

    mock_llm = MagicMock()
    mock_llm.astream = fake_stream

    mock_sel_instance = MagicMock()
    mock_sel_instance.get_chat_llm.return_value = mock_llm

    with patch("app.models.reasoning.llm_cache") as mock_cache, \
         patch("app.models.reasoning.ProviderSelector", return_value=mock_sel_instance):
        mock_cache.get = AsyncMock(return_value=None)

        llm = ReasoningLLM(model="test")

        tokens = []
        async for token in llm.astream("test prompt", system="system"):
            tokens.append(token)

        assert tokens == ["chunk1", "chunk2"]
