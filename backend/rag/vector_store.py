"""
backend/rag/vector_store.py
Compatibility layer redirecting legacy RAG queries strictly to MongoDB knowledge store.
"""

from backend.database.knowledge import search_knowledge_documents

__all__ = ["search_knowledge_documents"]
