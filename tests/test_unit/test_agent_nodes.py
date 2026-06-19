import pytest
import json
from unittest.mock import patch, MagicMock
from tests.factories import make_state, mock_provider_selector


class TestClassifyNode:
    @pytest.mark.asyncio
    async def test_classify_sets_query_type(self):
        from app.agent.nodes import classify

        state = make_state(query="hello")
        with mock_provider_selector(query_type="direct"):
            result = await classify(state)
        assert result["query_type"] == "direct"
        assert isinstance(result["filters"], dict)

    @pytest.mark.asyncio
    async def test_classify_sets_tool_type(self):
        from app.agent.nodes import classify

        state = make_state(query="weather in chennai")
        with mock_provider_selector(query_type="tool"):
            result = await classify(state)
        assert result["query_type"] == "tool"


class TestToolNode:
    @pytest.mark.asyncio
    async def test_tool_node_skips_non_tool(self):
        from app.agent.nodes import tool_node

        state = make_state(query="hello", query_type="direct")
        result = await tool_node(state)
        assert result["tool_data"] == {}

    @pytest.mark.asyncio
    async def test_tool_node_calls_get_farm_data(self):
        from app.agent.nodes import tool_node

        state = make_state(query="weather", query_type="tool")
        with patch("app.agent.tools.get_farm_data") as mock_get:
            mock_get.return_value = json.dumps(
                {
                    "weather": {"temp_C": "30"},
                    "iot": {"moisture": 45},
                    "gee": {"ndvi": 0.7},
                }
            )
            result = await tool_node(state)
        assert result["tool_data"]["weather"]["temp_C"] == "30"
        assert result["tool_data"]["iot"]["moisture"] == 45

    @pytest.mark.asyncio
    async def test_tool_node_invalid_json_fallback(self):
        from app.agent.nodes import tool_node

        state = make_state(query="weather", query_type="tool")
        with patch("app.agent.tools.get_farm_data") as mock_get:
            mock_get.return_value = "not valid json"
            result = await tool_node(state)
        assert result["tool_data"] == {}


class TestRagNode:
    @pytest.mark.asyncio
    async def test_rag_node_calls_aquery_schemes(self):
        from app.agent.nodes import rag_node

        state = make_state(query="pm kisan", filters={"type": "input_subsidy"})
        with patch("app.services.rag.aquery_schemes") as mock_query:
            mock_query.return_value = {
                "schemes": [{"content": "PM Kisan", "type": "input_subsidy"}]
            }
            result = await rag_node(state)
        assert result["scheme_data"]["schemes"][0]["content"] == "PM Kisan"
        mock_query.assert_called_once_with(
            query="pm kisan", scheme_type="input_subsidy"
        )


class TestHandoffNode:
    def test_handoff_node_returns_human_message(self):
        from app.agent.nodes import handoff_node

        state = make_state()
        result = handoff_node(state)
        assert "human agent" in result["response"].lower()


class TestDirectNode:
    @pytest.mark.asyncio
    async def test_direct_node_builds_prompt_with_all_data(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.agent.nodes import direct_node

        state = make_state(
            query="tell me about farming",
            tool_data={"weather": {"temp_C": "30"}},
            scheme_data={"schemes": [{"content": "PM Kisan"}]},
            context=[{"role": "user", "content": "hi"}],
        )
        with patch("app.models.reasoning.ProviderSelector") as MockSel:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "farming advice response"
            mock_sel = MagicMock()
            mock_sel.get_chat_llm.return_value = mock_llm
            mock_sel.resolve_model.return_value = "test-model"
            MockSel.return_value = mock_sel
            result = await direct_node(state)
            assert result["response"] == "farming advice response"
            call_args = mock_llm.generate.call_args[1]
            assert "tell me about farming" in call_args["prompt"]
            assert "temp_C" in call_args["prompt"]
            assert "PM Kisan" in call_args["prompt"]
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_direct_node_streams_tokens_via_callback(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_FLASH_MODEL", "minimax-m2.7:cloud")
        monkeypatch.setenv("OLLAMA_REASONING_MODEL", "minimax-m2.7:cloud")
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.agent.nodes import direct_node

        tokens = []

        async def cb(token: str):
            tokens.append(token)

        state = make_state(
            query="hello",
            stream_callback=cb,
        )
        with patch("app.models.reasoning.ProviderSelector") as MockSel:

            async def mock_astream(prompt, system=None):
                for t in ["Hello", " ", "World"]:
                    yield t

            mock_llm = MagicMock()
            mock_llm.astream = mock_astream
            mock_sel = MagicMock()
            mock_sel.get_chat_llm.return_value = mock_llm
            mock_sel.resolve_model.return_value = "test-model"
            MockSel.return_value = mock_sel
            result = await direct_node(state)
            assert result["response"] == "Hello World"
            assert tokens == ["Hello", " ", "World"]
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_direct_node_no_context(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.agent.nodes import direct_node

        state = make_state(query="hello")
        with patch("app.models.reasoning.ProviderSelector") as MockSel:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = "response"
            mock_sel = MagicMock()
            mock_sel.get_chat_llm.return_value = mock_llm
            mock_sel.resolve_model.return_value = "test-model"
            MockSel.return_value = mock_sel
            result = await direct_node(state)
            assert result["response"] == "response"
        get_settings.cache_clear()
