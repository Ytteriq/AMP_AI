"""
backend/rag/__init__.py
Centralized strategy and knowledge retrieval package (powered by MongoDB).
"""

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
