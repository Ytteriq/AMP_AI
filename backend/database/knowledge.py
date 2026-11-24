"""
backend/database/knowledge.py
MongoDB-backed campaign strategy and marketing guidelines repository.
Queries the 'strategies' collection strictly from MongoDB.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from backend.database.connection import get_database

logger = logging.getLogger("ai_reel.database.knowledge")

COLLECTION_NAME = "strategies"


def search_knowledge_documents(
    query: str,
    k: int = 3,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Searches campaign strategy documents and playbooks strictly from MongoDB.
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        return []

    terms = [re.escape(w) for w in re.split(r"\W+", clean_query) if len(w) > 2]
    regex_pattern = "|".join(terms) if terms else re.escape(clean_query)

    agency_filter = None
    if filter_metadata and "agency" in filter_metadata:
        agency_filter = filter_metadata["agency"]

    # Enforce ambient tenant context isolation if active
    from backend.security.tenant_context import current_tenant_cv
    tenant = current_tenant_cv.get()
    if tenant and tenant.agency_id:
        if agency_filter and not tenant.can_access_agency(agency_filter):
            agency_filter = tenant.agency_id
        elif not agency_filter:
            agency_filter = tenant.agency_id

    db = get_database()
    coll = db[COLLECTION_NAME]

    mongo_filter: Dict[str, Any] = {}
    if agency_filter:
        mongo_filter["agency"] = {"$regex": re.escape(agency_filter), "$options": "i"}

    if regex_pattern:
        mongo_filter["$or"] = [
            {"content": {"$regex": regex_pattern, "$options": "i"}},
            {"title": {"$regex": regex_pattern, "$options": "i"}},
            {"topic": {"$regex": regex_pattern, "$options": "i"}},
            {"agency": {"$regex": regex_pattern, "$options": "i"}},
        ]

    results: List[Dict[str, Any]] = []
    cursor = coll.find(mongo_filter).limit(k)
    for doc in cursor:
        results.append(
            {
                "title": doc.get("title", "Strategy Document"),
                "source": doc.get("source", "MongoDB Atlas"),
                "content": doc.get("content", ""),
                "metadata": {
                    "agency": doc.get("agency", ""),
                    "topic": doc.get("topic", ""),
                    "source": doc.get("source", ""),
                },
                "relevance_score": 0.95,
            }
        )
    return results
