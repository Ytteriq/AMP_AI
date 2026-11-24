"""
backend/rag/vector_store.py
Compatibility layer redirecting legacy RAG queries to MongoDB knowledge store.
ChromaDB has been replaced with centralized MongoDB strategy documents.
"""

from typing import Any, Dict, List, Optional
from backend.database.knowledge import (
    DEFAULT_STRATEGIES,
    ensure_seed_strategies,
    search_knowledge_documents,
)

__all__ = [
    "search_knowledge_documents",
    "ensure_seed_strategies",
    "DEFAULT_STRATEGIES",
]
