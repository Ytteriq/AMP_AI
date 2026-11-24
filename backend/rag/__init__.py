"""
backend/rag/__init__.py
Centralized strategy and knowledge retrieval package (powered strictly by MongoDB).
"""

from backend.database.knowledge import search_knowledge_documents

__all__ = ["search_knowledge_documents"]
