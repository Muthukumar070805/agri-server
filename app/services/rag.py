import asyncio
import hashlib
import json
import threading

from langchain_pinecone import PineconeVectorStore
from sentence_transformers import CrossEncoder

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.provider import ProviderSelector
from app.resilience.circuit_breaker import CircuitOpenError, get_circuit
from app.services.redis_cache import redis_cache

logger = get_logger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = None
_reranker_lock = threading.Lock()

_vectorstore: PineconeVectorStore | None = None
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
    query: str,
    scheme_type: str | list[str] | None = None,
    top_k: int = 8,
    initial_k: int = 20,
) -> dict:
    settings = get_settings()

    types_list: list[str] = []
    if isinstance(scheme_type, list):
        types_list = [t for t in scheme_type if isinstance(t, str) and t.strip()]
    elif isinstance(scheme_type, str) and scheme_type.strip():
        types_list = [scheme_type.strip()]

    filters_used: dict = {
        "type": types_list[0] if len(types_list) == 1 else None,
        "types": types_list,
    }

    if not settings.pinecone_api_key:
        logger.warning("Pinecone API key not configured")
        return {
            "schemes": [],
            "filters_used": filters_used,
            "count": 0,
            "error": "Pinecone API key not configured",
        }

    type_cache_key = ",".join(sorted(types_list)) if types_list else "all"

    if settings.llm_cache_enabled:
        digest = hashlib.sha256(query.encode()).hexdigest()[:16]
        cache_key = f"rag:{digest}:{type_cache_key}"
        cached = await redis_cache.get(cache_key)
        if cached:
            logger.info(f"RAG cache hit: {query[:50]}")
            return json.loads(cached)

    try:
        vectorstore = get_vectorstore()

        cb = get_circuit("pinecone")
        filter_expr = None
        if len(types_list) == 1:
            filter_expr = {"type": {"$eq": types_list[0]}}
        elif len(types_list) > 1:
            filter_expr = {"type": {"$in": types_list}}

        logger.info(f"RAG: query='{query}', filter={filter_expr}, k={initial_k}")

        try:

            async def _search_pinecone(f_expr):
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: vectorstore.similarity_search(
                            query, k=initial_k, filter=f_expr
                        ),
                    ),
                    timeout=15.0,
                )

            docs = await cb.call(_search_pinecone, filter_expr)
        except CircuitOpenError:
            cb = get_circuit("pinecone")
            logger.warning(f"Pinecone circuit OPEN (failures={cb._failure_count})")
            return {
                "schemes": [],
                "filters_used": filters_used,
                "count": 0,
                "error": "RAG service temporarily unavailable",
            }

        logger.info(f"RAG: Pinecone returned {len(docs)} docs")

        reranker = _get_reranker()
        loop = asyncio.get_event_loop()

        if docs:
            pairs = [[query, doc.page_content] for doc in docs]
            scores = await loop.run_in_executor(None, reranker.predict, pairs)
            scored_docs = sorted(
                zip(scores, docs, strict=False), key=lambda x: x[0], reverse=True
            )
            top_score = float(scored_docs[0][0]) if scored_docs else 0.0
        else:
            scored_docs = []
            top_score = 0.0

        # Resilient fallback: if category filtering was too restrictive
        # or returned docs below floor, perform an unfiltered dense search
        # to catch cross-component named schemes (e.g. PMKSY, SMAM)
        floor = settings.min_relevance_score
        if filter_expr is not None and (
            not docs or (floor != 0.0 and top_score < floor)
        ):
            logger.info(
                "RAG: Filter %s top score %.4f (floor %.4f). Retrying unfiltered...",
                filter_expr,
                top_score,
                floor,
            )
            try:
                unfiltered_docs = await cb.call(_search_pinecone, None)
                if unfiltered_docs:
                    unfiltered_pairs = [
                        [query, doc.page_content] for doc in unfiltered_docs
                    ]
                    unfiltered_scores = await loop.run_in_executor(
                        None, reranker.predict, unfiltered_pairs
                    )
                    unfiltered_scored = sorted(
                        zip(unfiltered_scores, unfiltered_docs, strict=False),
                        key=lambda x: x[0],
                        reverse=True,
                    )
                    unfiltered_top_score = (
                        float(unfiltered_scored[0][0]) if unfiltered_scored else 0.0
                    )
                    if unfiltered_top_score > top_score:
                        docs = unfiltered_docs
                        scored_docs = unfiltered_scored
                        top_score = unfiltered_top_score
                        logger.info(
                            "RAG: Unfiltered fallback elevated top score to %.4f",
                            top_score,
                        )
            except Exception as ex:  # noqa: BLE001
                logger.warning("RAG: Unfiltered fallback query failed: %s", ex)

        if not docs:
            logger.warning(f"RAG: No documents found for query: {query}")
            return {"schemes": [], "filters_used": filters_used, "count": 0}

        if (
            settings.min_relevance_score != 0.0
            and top_score < settings.min_relevance_score
        ):
            logger.info(
                "RAG: top score %.4f below floor %.4f for '%s'",
                top_score,
                settings.min_relevance_score,
                query[:60],
            )
            return {
                "schemes": [],
                "filters_used": {"type": scheme_type},
                "count": 0,
                "top_score": round(top_score, 4),
                "reason": "below_relevance_threshold",
            }

        top_docs = [doc for _, doc in scored_docs][:top_k]

        logger.info(f"RAG: Reranked to {len(top_docs)} schemes")

        schemes = []
        for doc in top_docs:
            schemes.append(
                {
                    "content": doc.page_content,
                    "type": doc.metadata.get("type"),
                }
            )

        logger.info(f"RAG: Returning {len(schemes)} schemes")

        result = {
            "schemes": schemes,
            "filters_used": filters_used,
            "count": len(schemes),
            "top_score": round(top_score, 4),
        }

        if settings.llm_cache_enabled and schemes:
            await redis_cache.set(cache_key, json.dumps(result), ttl=3600)

        return result

    except Exception as e:  # noqa: BLE001 - degraded RAG must not fail the request
        logger.error(f"RAG error for '{query[:60]}': {type(e).__name__}: {e}")
        return {
            "schemes": [],
            "filters_used": filters_used,
            "count": 0,
            "error": f"{type(e).__name__}: {e!s}",
        }


async def aquery_schemes(
    query: str,
    scheme_type: str | list[str] | None = None,
    top_k: int = 8,
    initial_k: int = 20,
) -> dict:
    return await query_schemes(query, scheme_type, top_k, initial_k)
