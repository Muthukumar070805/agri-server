from typing import Optional
from langchain_pinecone import PineconeVectorStore
from app.models.ollama import get_embeddings
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def query_schemes(query: str, top_k: int = 5) -> str:
    settings = get_settings()
    try:
        embeddings = get_embeddings()
        vectorstore = PineconeVectorStore(
            index_name=settings.pinecone_index,
            embedding=embeddings,
            text_key="scheme",
        )
        docs = vectorstore.similarity_search(query, k=top_k)
        if not docs:
            return "No matching schemes found."

        results = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content
            source = doc.metadata.get("source", "Unknown")
            results.append(f"{i}. {content}\n   Source: {source}")

        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return "Unable to fetch scheme information. Please try again."
