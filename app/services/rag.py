from typing import Optional
from langchain_pinecone import PineconeVectorStore
from app.models.ollama import get_embeddings
from app.core.config import get_settings
from app.core.logger import get_logger
from sentence_transformers import CrossEncoder
import json

logger = get_logger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_THRESHOLD = 0.5

_reranker = None

def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


async def query_schemes(
    query: str,
    crop: Optional[str] = None,
    scheme_type: Optional[str] = None,
    top_k: int = 5,
    initial_k: int = 50
) -> dict:
    settings = get_settings()
    try:
        embeddings = get_embeddings()
        vectorstore = PineconeVectorStore(
            index_name=settings.pinecone_index,
            embedding=embeddings,
            text_key="scheme",
        )

        filter_expr = {}
        if crop:
            filter_expr["crop"] = {"$eq": crop}
        if scheme_type:
            filter_expr["type"] = {"$eq": scheme_type}

        docs = vectorstore.similarity_search(
            query,
            k=initial_k,
            filter=filter_expr if filter_expr else None
        )

        if not docs:
            return {"schemes": [], "filters_used": {"crop": crop, "type": scheme_type}, "count": 0}

        reranker = _get_reranker()
        pairs = [[query, doc.page_content] for doc in docs]
        scores = reranker.predict(pairs)

        scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top_docs = [doc for score, doc in scored_docs if score > RERANK_THRESHOLD][:top_k]

        if not top_docs:
            return {"schemes": [], "filters_used": {"crop": crop, "type": scheme_type}, "count": 0, "message": "No relevant schemes found above threshold"}

        schemes = []
        for doc in top_docs:
            schemes.append({
                "content": doc.page_content,
                "crop": doc.metadata.get("crop"),
                "type": doc.metadata.get("type")
            })

        return {
            "schemes": schemes,
            "filters_used": {"crop": crop, "type": scheme_type},
            "count": len(schemes)
        }

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"schemes": [], "filters_used": {}, "count": 0, "error": str(e)}