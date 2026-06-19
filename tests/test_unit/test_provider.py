import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.models.provider import ProviderSelector, LLMTimeoutError, _get_timeout
from app.models.reasoning import ReasoningLLM


class TestProviderSelector:
    def test_init_detects_mistral(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        monkeypatch.delenv("SESSION_REDIS_ENABERT", raising=False)
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        assert sel.is_mistral() is True
        assert sel.is_ollama() is False
        get_settings.cache_clear()

    def test_init_detects_ollama(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        assert sel.is_mistral() is False
        assert sel.is_ollama() is True
        get_settings.cache_clear()

    def test_resolve_model_classify_mistral(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        model = sel.resolve_model("classify")
        assert model == "mistral-small-latest"
        get_settings.cache_clear()

    def test_resolve_model_reasoning_mistral(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        model = sel.resolve_model("reasoning")
        assert model == "mistral-large-latest"
        get_settings.cache_clear()

    def test_resolve_model_classify_ollama(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_FLASH_MODEL", "minimax-m2.7:cloud")
        monkeypatch.setenv("OLLAMA_REASONING_MODEL", "minimax-m2.7:cloud")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        model = sel.resolve_model("classify")
        assert model == "minimax-m2.7:cloud"
        get_settings.cache_clear()

    def test_resolve_model_reasoning_ollama(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_FLASH_MODEL", "minimax-m2.7:cloud")
        monkeypatch.setenv("OLLAMA_REASONING_MODEL", "minimax-m2.7:cloud")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        model = sel.resolve_model("reasoning")
        assert model == "minimax-m2.7:cloud"
        get_settings.cache_clear()

    def test_get_chat_llm_mistral(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        llm = sel.get_chat_llm()
        from app.models.provider import MistralLLM

        assert isinstance(llm, MistralLLM)
        get_settings.cache_clear()

    def test_get_chat_llm_ollama(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        sel = ProviderSelector()
        llm = sel.get_chat_llm()
        from app.models.provider import OllamaLLM

        assert isinstance(llm, OllamaLLM)
        get_settings.cache_clear()


class TestGetTimeout:
    def test_get_timeout_returns_config_value(self, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "15")
        from app.core.config import get_settings

        get_settings.cache_clear()
        assert _get_timeout() == 15
        get_settings.cache_clear()


class TestLLMTimeoutError:
    def test_is_exception(self):
        err = LLMTimeoutError("timed out after 30s")
        assert isinstance(err, Exception)
        assert "timed out" in str(err)


class TestReasoningLLM:
    @pytest.mark.asyncio
    async def test_generate_calls_underlying_llm(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.models.reasoning.ProviderSelector") as MockSel:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "test response"
            mock_sel = MagicMock()
            mock_sel.get_chat_llm.return_value = mock_llm
            mock_sel.resolve_model.return_value = "test-model"
            MockSel.return_value = mock_sel

            rllm = ReasoningLLM()
            result = rllm.generate("hello", system="be helpful")
            assert result == "test response"
            mock_llm.generate.assert_called_once_with(
                prompt="hello", system="be helpful"
            )
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_agenerate_calls_underlying_llm(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.models.reasoning.llm_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            with patch("app.models.reasoning.ProviderSelector") as MockSel:
                mock_llm = MagicMock()
                mock_llm.agenerate = AsyncMock(return_value="async response")
                mock_sel = MagicMock()
                mock_sel.get_chat_llm.return_value = mock_llm
                mock_sel.resolve_model.return_value = "test-model"
                MockSel.return_value = mock_sel

                rllm = ReasoningLLM()
                result = await rllm.agenerate("hello", system="be helpful")
                assert result == "async response"
                mock_llm.agenerate.assert_called_once_with(
                    prompt="hello", system="be helpful"
                )
                mock_cache.set.assert_called_once()
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_agenerate_cache_hit(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.models.reasoning.llm_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value="cached response")
            with patch("app.models.reasoning.ProviderSelector") as MockSel:  # noqa: F841
                mock_llm = MagicMock()
                mock_sel = MagicMock()
                mock_sel.get_chat_llm.return_value = mock_llm
                mock_sel.resolve_model.return_value = "test-model"
                MockSel.return_value = mock_sel

                rllm = ReasoningLLM()
                result = await rllm.agenerate("hello")
                assert result == "cached response"
                mock_llm.agenerate.assert_not_called()
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_astream_cache_hit(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.models.reasoning.llm_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value="cached stream")
            with patch("app.models.reasoning.ProviderSelector"):
                rllm = ReasoningLLM()
                tokens = []
                async for token in rllm.astream("hello"):
                    tokens.append(token)
                assert "".join(tokens) == "cached stream"
        get_settings.cache_clear()

    def test_stream_yields_chunks(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        with patch("app.models.reasoning.ProviderSelector") as MockSel:
            mock_llm = MagicMock()
            mock_llm.stream.return_value = iter(["a", "b", "c"])
            mock_sel = MagicMock()
            mock_sel.get_chat_llm.return_value = mock_llm
            mock_sel.resolve_model.return_value = "test-model"
            MockSel.return_value = mock_sel

            rllm = ReasoningLLM()
            result = list(rllm.stream("hello"))
            assert result == ["a", "b", "c"]
        get_settings.cache_clear()
