from typing import Optional
from langchain_pinecone import PineconeVectorStore
from app.models.provider import ProviderSelector
from app.core.config import get_settings
from app.core.logger import get_logger
from sentence_transformers import CrossEncoder
import json

logger = get_logger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = None

def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def preload_reranker():
    global _reranker
    if _reranker is None:
        logger.info("Preloading CrossEncoder reranker model...")
        _reranker = CrossEncoder(RERANK_MODEL)
        logger.info("CrossEncoder reranker loaded successfully")


def query_schemes(
    query: str,
    scheme_type: Optional[str] = None,
    top_k: int = 5,
    initial_k: int = 50
) -> dict:
    settings = get_settings()
    if not settings.pinecone_api_key:
        return {"schemes": [], "filters_used": {"type": scheme_type}, "count": 0, "error": "Pinecone API key not configured"}
    try:
        embeddings = ProviderSelector().get_embeddings()
        vectorstore = PineconeVectorStore(
            index_name=settings.pinecone_index,
            embedding=embeddings,
            text_key="scheme",
            pinecone_api_key=settings.pinecone_api_key,
        )

        filter_expr = None
        if scheme_type:
            filter_expr = {"type": {"$eq": scheme_type}}

        docs = vectorstore.similarity_search(
            query,
            k=initial_k,
            filter=filter_expr
        )

        if not docs:
            return {"schemes": [], "filters_used": {"type": scheme_type}, "count": 0}

        reranker = _get_reranker()
        pairs = [[query, doc.page_content] for doc in docs]
        scores = reranker.predict(pairs)

        scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top_docs = [doc for score, doc in scored_docs][:top_k]

        schemes = []
        for doc in top_docs:
            schemes.append({
                "content": doc.page_content,
                "crop": doc.metadata.get("crop"),
                "type": doc.metadata.get("type")
            })

        return {
            "schemes": schemes,
            "filters_used": {"type": scheme_type},
            "count": len(schemes)
        }

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"schemes": [], "filters_used": {}, "count": 0, "error": str(e)}

import asyncio


async def aquery_schemes(
    query: str,
    scheme_type: Optional[str] = None,
    top_k: int = 5,
    initial_k: int = 50
) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, query_schemes, query, scheme_type, top_k, initial_k
    )
