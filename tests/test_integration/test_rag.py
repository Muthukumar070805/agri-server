import pytest
from unittest.mock import patch, MagicMock, AsyncMock


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
