from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_query_schemes_returns_dict():
    from app.services.rag import query_schemes

    mock_doc = MagicMock()
    mock_doc.page_content = "PM Kisan: ₹6000 annual support"
    mock_doc.metadata = {"crop": "all", "type": "input_subsidy"}

    with patch("app.services.rag.get_vectorstore") as mock_get_vs:
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [mock_doc]
        mock_get_vs.return_value = mock_vs

        with patch("app.services.rag._get_reranker") as mock_get_rr:
            mock_rr = MagicMock()
            mock_rr.predict.return_value = [0.95]
            mock_get_rr.return_value = mock_rr

            with patch(
                "app.services.rag.redis_cache.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await query_schemes("PM Kisan scheme")
                assert "schemes" in result
                assert len(result["schemes"]) == 1
                assert (
                    result["schemes"][0]["content"] == "PM Kisan: ₹6000 annual support"
                )


@pytest.mark.asyncio
async def test_aquery_schemes_returns_dict():
    from app.services.rag import aquery_schemes

    result = await aquery_schemes("agricultural scheme")
    assert isinstance(result, dict)
    assert "schemes" in result


@pytest.mark.asyncio
async def test_query_schemes_handles_empty_result():
    from app.services.rag import query_schemes

    with patch("app.services.rag.get_vectorstore") as mock_get_vs:
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = []
        mock_get_vs.return_value = mock_vs

        with patch("app.services.rag._get_reranker") as mock_get_rr:
            mock_rr = MagicMock()
            mock_rr.predict.return_value = []
            mock_get_rr.return_value = mock_rr

            with patch(
                "app.services.rag.redis_cache.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await query_schemes("nonexistent query xyz123")
                assert result["count"] == 0
                assert result["schemes"] == []


@pytest.mark.asyncio
async def test_get_vectorstore_singleton():
    from app.services.rag import get_vectorstore, reset_vectorstore

    with patch("app.services.rag.PineconeVectorStore") as mock_store:
        mock_instance = MagicMock()
        mock_store.return_value = mock_instance

        vs1 = get_vectorstore()
        vs2 = get_vectorstore()
        assert vs1 is vs2

        reset_vectorstore()


@pytest.mark.asyncio
async def test_query_schemes_abstains_below_floor(monkeypatch):
    from app.core.config import get_settings
    from app.services.rag import query_schemes

    monkeypatch.setattr(get_settings(), "min_relevance_score", 0.6)

    mock_doc = MagicMock()
    mock_doc.page_content = "irrelevant chunk"
    mock_doc.metadata = {"type": "irrigation"}

    with patch("app.services.rag.get_vectorstore") as mock_get_vs:
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [mock_doc]
        mock_get_vs.return_value = mock_vs

        with patch("app.services.rag._get_reranker") as mock_get_rr:
            mock_rr = MagicMock()
            mock_rr.predict.return_value = [0.4]
            mock_get_rr.return_value = mock_rr

            with patch(
                "app.services.rag.redis_cache.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await query_schemes("unrelated question")

    assert result["schemes"] == []
    assert result["count"] == 0
    assert result["reason"] == "below_relevance_threshold"
    assert result["top_score"] == 0.4


@pytest.mark.asyncio
async def test_query_schemes_floor_disabled_by_default(monkeypatch):
    from app.core.config import get_settings
    from app.services.rag import query_schemes

    monkeypatch.setattr(get_settings(), "min_relevance_score", 0.0)

    mock_doc = MagicMock()
    mock_doc.page_content = "weak match"
    mock_doc.metadata = {"type": "irrigation"}

    with patch("app.services.rag.get_vectorstore") as mock_get_vs:
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [mock_doc]
        mock_get_vs.return_value = mock_vs

        with patch("app.services.rag._get_reranker") as mock_get_rr:
            mock_rr = MagicMock()
            mock_rr.predict.return_value = [0.05]
            mock_get_rr.return_value = mock_rr

            with patch(
                "app.services.rag.redis_cache.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await query_schemes("weak query")

    assert len(result["schemes"]) == 1
    assert result["top_score"] == 0.05
