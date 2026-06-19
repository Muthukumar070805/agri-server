import asyncio
import hashlib
import json
import threading
from typing import Optional
from langchain_pinecone import PineconeVectorStore
from app.models.provider import ProviderSelector
from app.core.config import get_settings
from app.core.logger import get_logger
from app.resilience.circuit_breaker import get_circuit, CircuitOpenError
from app.services.redis_cache import redis_cache
from sentence_transformers import CrossEncoder

logger = get_logger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = None
_reranker_lock = threading.Lock()

_vectorstore: Optional[PineconeVectorStore] = None
_embeddings = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def get_vectorstore() -> PineconeVectorStore:
    global _vectorstore, _embeddings
    if _vectorstore is None:
        settings = get_settings()
        _embeddings = ProviderSelector().get_embeddings()
        _vectorstore = PineconeVectorStore(
            index_name=settings.pinecone_index,
            embedding=_embeddings,
            text_key="scheme",
            pinecone_api_key=settings.pinecone_api_key,
        )
        logger.info("PineconeVectorStore initialized (singleton)")
    return _vectorstore


def reset_vectorstore():
    global _vectorstore, _embeddings
    _vectorstore = None
    _embeddings = None
    logger.info("PineconeVectorStore reset (cache cleared)")


def preload_reranker():
    global _reranker
    if _reranker is None:
        logger.info("Preloading CrossEncoder reranker model...")
        _reranker = CrossEncoder(RERANK_MODEL)
        logger.info("CrossEncoder reranker loaded successfully")


async def query_schemes(
    query: str, scheme_type: Optional[str] = None, top_k: int = 5, initial_k: int = 20
) -> dict:
    settings = get_settings()
    if not settings.pinecone_api_key:
        logger.warning("Pinecone API key not configured")
        return {
            "schemes": [],
            "filters_used": {"type": scheme_type},
            "count": 0,
            "error": "Pinecone API key not configured",
        }

    if settings.llm_cache_enabled:
        cache_key = f"rag:{hashlib.sha256(query.encode()).hexdigest()[:16]}:{scheme_type or 'all'}"
        cached = await redis_cache.get(cache_key)
        if cached:
            logger.info(f"RAG cache hit: {query[:50]}")
            return json.loads(cached)

    try:
        vectorstore = get_vectorstore()

        cb = get_circuit("pinecone")
        filter_expr = None
        if scheme_type:
            filter_expr = {"type": {"$eq": scheme_type}}

        logger.info(f"RAG: query='{query}', filter={filter_expr}, k={initial_k}")

        try:

            async def _search():
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: vectorstore.similarity_search(
                            query, k=initial_k, filter=filter_expr
                        ),
                    ),
                    timeout=15.0,
                )

            docs = await cb.call(_search)
        except CircuitOpenError:
            cb = get_circuit("pinecone")
            logger.warning(f"Pinecone circuit OPEN (failures={cb._failure_count})")
            return {
                "schemes": [],
                "filters_used": {"type": scheme_type},
                "count": 0,
                "error": "RAG service temporarily unavailable",
            }

        logger.info(f"RAG: Pinecone returned {len(docs)} docs")

        if not docs:
            logger.warning(f"RAG: No documents found for query: {query}")
            return {"schemes": [], "filters_used": {"type": scheme_type}, "count": 0}

        reranker = _get_reranker()
        pairs = [[query, doc.page_content] for doc in docs]

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, reranker.predict, pairs)

        scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top_docs = [doc for score, doc in scored_docs][:top_k]

        logger.info(f"RAG: Reranked to {len(top_docs)} schemes")

        schemes = []
        for doc in top_docs:
            schemes.append(
                {
                    "content": doc.page_content,
                    "crop": doc.metadata.get("crop"),
                    "type": doc.metadata.get("type"),
                }
            )

        logger.info(f"RAG: Returning {len(schemes)} schemes")

        result = {
            "schemes": schemes,
            "filters_used": {"type": scheme_type},
            "count": len(schemes),
        }

        if settings.llm_cache_enabled:
            await redis_cache.set(cache_key, json.dumps(result), ttl=3600)

        return result

    except Exception as e:
        logger.error(f"RAG error for '{query[:60]}': {type(e).__name__}: {e}")
        return {
            "schemes": [],
            "filters_used": {"type": scheme_type},
            "count": 0,
            "error": f"{type(e).__name__}: {str(e)}",
        }


async def aquery_schemes(
    query: str, scheme_type: Optional[str] = None, top_k: int = 5, initial_k: int = 20
) -> dict:
    return await query_schemes(query, scheme_type, top_k, initial_k)
