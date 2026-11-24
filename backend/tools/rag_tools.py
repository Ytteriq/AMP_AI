"""
tools/rag_tools.py
Implements search_knowledge tool for retrieving contextual knowledge,
strategy guidelines, and campaign playbooks from MongoDB.
"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from backend.database.knowledge import search_knowledge_documents


@tool
def search_knowledge(
    query: str,
    top_k: int = 3,
    agency_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve unstructured contextual knowledge, campaign strategy documents,
    agency playbooks, guidelines, and historical reports from MongoDB.

    Parameters:
    - query: Natural language search query (e.g., 'What strategy did Apex Growth Lab use?').
    - top_k: Maximum number of relevant document passages to retrieve (default 3).
    - agency_filter: Optional agency name to filter documents by metadata.
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        return {
            "error": "Query cannot be empty.",
            "results": [],
            "documents_found": 0,
        }

    filter_dict = {"agency": agency_filter} if agency_filter else None
    results = search_knowledge_documents(query=clean_query, k=top_k, filter_metadata=filter_dict)

    if not results:
        return {
            "query": clean_query,
            "status": "no_documents_found",
            "message": "No relevant campaign strategy documents or guidelines were retrieved for this query.",
            "documents_found": 0,
            "results": [],
        }

    return {
        "query": clean_query,
        "status": "success",
        "documents_found": len(results),
        "results": [
            {
                "title": r.get("title"),
                "source": r.get("source"),
                "content": r.get("content"),
                "relevance_score": r.get("relevance_score"),
            }
            for r in results
        ],
    }
