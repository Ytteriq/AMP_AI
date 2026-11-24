"""RAG package initialization."""
from backend.rag.embeddings import get_embeddings, embeddings
from backend.rag.vector_store import (
    get_vector_store,
    add_documents_to_store,
    search_knowledge_documents,
)

__all__ = [
    "get_embeddings",
    "embeddings",
    "get_vector_store",
    "add_documents_to_store",
    "search_knowledge_documents",
]
