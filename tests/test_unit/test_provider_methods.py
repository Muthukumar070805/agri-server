import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.core.config import get_settings
from app.models.provider import LLMTimeoutError, MistralLLM, OllamaLLM, ProviderSelector


class TestOllamaLLM:
    @pytest.fixture
    def mock_llm(self):
        with patch("app.models.provider.get_ollama_llm") as m:
            llm = MagicMock()
            llm.invoke.return_value = AIMessage(content="ollama resp")
            llm.ainvoke = AsyncMock(return_value=AIMessage(content="ollama resp"))

            chunk1 = MagicMock()
            chunk1.content = "hello "
            chunk2 = MagicMock()
            chunk2.content = "world"
            llm.stream.return_value = iter([chunk1, chunk2])

            async def _astream(*args, **kwargs):
                yield chunk1
                yield chunk2

            llm.astream = _astream

            m.return_value = llm
            yield llm

    def test_invoke(self, mock_llm):
        llm = OllamaLLM()
        result = llm.invoke([{"role": "user", "content": "hi"}])
        assert result.content == "ollama resp"
        mock_llm.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_ainvoke(self, mock_llm):
        llm = OllamaLLM()
        result = await llm.ainvoke([{"role": "user", "content": "hi"}])
        assert result.content == "ollama resp"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_ainvoke_timeout(self, mock_llm, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
        get_settings.cache_clear()

        async def slow(*args, **kwargs):
            await asyncio.sleep(3)
            return AIMessage(content="late")

        mock_llm.ainvoke = slow

        llm = OllamaLLM()
        with pytest.raises(LLMTimeoutError, match="timed out after 1s"):
            await llm.ainvoke([{"role": "user"}])

    def test_generate_with_system(self, mock_llm):
        llm = OllamaLLM()
        result = llm.generate("hello", system="be helpful")
        assert result == "ollama resp"
        mock_llm.invoke.assert_called_once()

    def test_generate_without_system(self, mock_llm):
        llm = OllamaLLM()
        result = llm.generate("hello")
        assert result == "ollama resp"
        mock_llm.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agenerate(self, mock_llm):
        llm = OllamaLLM()
        result = await llm.agenerate("hello", system="be helpful")
        assert result == "ollama resp"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agenerate_timeout(self, mock_llm, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
        get_settings.cache_clear()

        async def slow(*args, **kwargs):
            await asyncio.sleep(3)
            return AIMessage(content="late")

        mock_llm.ainvoke = slow

        llm = OllamaLLM()
        with pytest.raises(LLMTimeoutError, match="timed out after 1s"):
            await llm.agenerate("hello")

    def test_stream(self, mock_llm):
        llm = OllamaLLM()
        result = list(llm.stream("hello"))
        assert result == ["hello ", "world"]

    def test_stream_skips_empty_content(self, mock_llm):
        empty = MagicMock()
        empty.content = ""
        good = MagicMock()
        good.content = "data"
        mock_llm.stream.return_value = iter([empty, good, empty])
        llm = OllamaLLM()
        result = list(llm.stream("hello"))
        assert result == ["data"]

    @pytest.mark.asyncio
    async def test_astream(self, mock_llm):
        llm = OllamaLLM()
        result = []
        async for chunk in llm.astream("hello"):
            result.append(chunk)
        assert result == ["hello ", "world"]

    @pytest.mark.asyncio
    async def test_astream_skips_empty_content(self, mock_llm):
        empty = MagicMock()
        empty.content = ""
        good = MagicMock()
        good.content = "data"

        async def filtered(*args, **kwargs):
            yield empty
            yield good
            yield empty

        mock_llm.astream = filtered

        llm = OllamaLLM()
        result = []
        async for chunk in llm.astream("hello"):
            result.append(chunk)
        assert result == ["data"]


class TestMistralLLM:
    @pytest.fixture
    def mock_llm(self):
        with patch("app.models.provider.ChatMistralAI") as m:
            llm = MagicMock()
            llm.invoke.return_value = AIMessage(content="mistral resp")
            llm.ainvoke = AsyncMock(return_value=AIMessage(content="mistral resp"))

            chunk1 = MagicMock()
            chunk1.content = "hello "
            chunk2 = MagicMock()
            chunk2.content = "world"
            llm.stream.return_value = iter([chunk1, chunk2])

            async def _astream(*args, **kwargs):
                yield chunk1
                yield chunk2

            llm.astream = _astream

            m.return_value = llm
            yield llm

    def test_invoke(self, mock_llm):
        llm = MistralLLM()
        result = llm.invoke([{"role": "user", "content": "hi"}])
        assert result.content == "mistral resp"
        mock_llm.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_ainvoke(self, mock_llm):
        llm = MistralLLM()
        result = await llm.ainvoke([{"role": "user", "content": "hi"}])
        assert result.content == "mistral resp"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_ainvoke_timeout(self, mock_llm, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
        get_settings.cache_clear()

        async def slow(*args, **kwargs):
            await asyncio.sleep(3)
            return AIMessage(content="late")

        mock_llm.ainvoke = slow

        llm = MistralLLM()
        with pytest.raises(LLMTimeoutError, match="timed out after 1s"):
            await llm.ainvoke([{"role": "user"}])

    def test_generate_with_system(self, mock_llm):
        llm = MistralLLM()
        result = llm.generate("hello", system="be helpful")
        assert result == "mistral resp"
        mock_llm.invoke.assert_called_once()

    def test_generate_without_system(self, mock_llm):
        llm = MistralLLM()
        result = llm.generate("hello")
        assert result == "mistral resp"
        mock_llm.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agenerate(self, mock_llm):
        llm = MistralLLM()
        result = await llm.agenerate("hello", system="be helpful")
        assert result == "mistral resp"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agenerate_timeout(self, mock_llm, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "1")
        get_settings.cache_clear()

        async def slow(*args, **kwargs):
            await asyncio.sleep(3)
            return AIMessage(content="late")

        mock_llm.ainvoke = slow

        llm = MistralLLM()
        with pytest.raises(LLMTimeoutError, match="timed out after 1s"):
            await llm.agenerate("hello")

    def test_stream(self, mock_llm):
        llm = MistralLLM()
        result = list(llm.stream("hello"))
        assert result == ["hello ", "world"]

    def test_stream_skips_empty_content(self, mock_llm):
        empty = MagicMock()
        empty.content = ""
        good = MagicMock()
        good.content = "data"
        mock_llm.stream.return_value = iter([empty, good, empty])
        llm = MistralLLM()
        result = list(llm.stream("hello"))
        assert result == ["data"]

    @pytest.mark.asyncio
    async def test_astream(self, mock_llm):
        llm = MistralLLM()
        result = []
        async for chunk in llm.astream("hello"):
            result.append(chunk)
        assert result == ["hello ", "world"]

    @pytest.mark.asyncio
    async def test_astream_skips_empty_content(self, mock_llm):
        empty = MagicMock()
        empty.content = ""
        good = MagicMock()
        good.content = "data"

        async def filtered(*args, **kwargs):
            yield empty
            yield good
            yield empty

        mock_llm.astream = filtered

        llm = MistralLLM()
        result = []
        async for chunk in llm.astream("hello"):
            result.append(chunk)
        assert result == ["data"]


class TestGetEmbeddings:
    def test_ollama_success(self):
        with patch("app.models.provider.get_ollama_embeddings") as m:
            mock_emb = MagicMock()
            m.return_value = mock_emb
            sel = ProviderSelector()
            result = sel.get_embeddings()
            assert result is mock_emb

    def test_fallback_to_mistral(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        get_settings.cache_clear()
        with (
            patch("app.models.provider.get_ollama_embeddings") as mock_ollama,
            patch("app.models.provider.MistralAIEmbeddings") as mock_mistral,
        ):
            mock_ollama.side_effect = RuntimeError("Ollama down")
            mock_instance = MagicMock()
            mock_mistral.return_value = mock_instance
            sel = ProviderSelector()
            result = sel.get_embeddings()
            assert result is mock_instance
            mock_mistral.assert_called_once_with(
                model="codestral-embed",
                api_key="real-mistral-key-xyz789",
            )

    def test_both_fail_raises(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        get_settings.cache_clear()
        with (
            patch("app.models.provider.get_ollama_embeddings") as mock_ollama,
            patch("app.models.provider.MistralAIEmbeddings") as mock_mistral,
        ):
            mock_ollama.side_effect = RuntimeError("Ollama down")
            mock_mistral.side_effect = RuntimeError("Mistral also down")
            sel = ProviderSelector()
            with pytest.raises(RuntimeError, match="Ollama down"):
                sel.get_embeddings()

    def test_ollama_fail_no_fallback_for_ollama_provider(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        get_settings.cache_clear()
        with patch("app.models.provider.get_ollama_embeddings") as m:
            m.side_effect = RuntimeError("Ollama down")
            sel = ProviderSelector()
            with pytest.raises(RuntimeError):
                sel.get_embeddings()
