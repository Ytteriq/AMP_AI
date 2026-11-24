"""
backend/database/knowledge.py
MongoDB-backed campaign strategy and marketing guidelines repository.
Replaces ChromaDB vector store with lightweight, robust MongoDB storage and text search.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from backend.database.connection import get_database

logger = logging.getLogger("ai_reel.database.knowledge")

COLLECTION_NAME = "strategies"

DEFAULT_STRATEGIES = [
    {
        "title": "Apex Growth Lab Strategy & Conversion Playbook",
        "source": "Strategy_Doc_2026_Apex_Growth.md",
        "agency": "Apex Growth Lab",
        "topic": "Strategy & ROAS Optimization",
        "content": (
            "Campaign Strategy: Apex Growth Lab emphasizes high-intent audience targeting, "
            "problem-solving hooks, and direct product demonstrations. Their strategy prioritizes "
            "conversion rate and return on ad spend (ROAS) rather than raw viral reach. "
            "They focus on niche professional segments (WFH desk workers, specialty coffee enthusiasts, "
            "and digital creators), resulting in lower top-of-funnel views but substantially higher net profit "
            "and strong double/triple-digit ROI."
        ),
    },
    {
        "title": "PulseMedia Digital Brand Awareness Playbook",
        "source": "Strategy_Doc_2026_PulseMedia.md",
        "agency": "PulseMedia Digital",
        "topic": "Brand Awareness & Viral Reach",
        "content": (
            "Campaign Strategy: PulseMedia Digital specializes in mass awareness, top-of-funnel reach, "
            "and high-production aesthetic reels. Their creative approach relies on fast-paced transitions, "
            "trendy audio, and broad consumer appeal. While generating massive view counts (often 400k - 600k+), "
            "their customer acquisition costs and production overhead are high, frequently leading to thin profit "
            "margins or negative short-term ROI when evaluated solely on direct attributed sales."
        ),
    },
    {
        "title": "Internal Reel Campaign Guidelines Q3-Q4 2026",
        "source": "Internal_Marketing_Guidelines_2026.md",
        "agency": "Global Marketing Team",
        "topic": "Guidelines & Spend Caps",
        "content": (
            "Q3-Q4 2026 Marketing Guidelines: All agencies managing Instagram Reels must balance viral hooks "
            "with direct call-to-actions (CTAs). For awareness campaigns, ad spend should be capped at ₹75,000 "
            "unless pre-approved for festive surges. Agencies experiencing low or negative profit must audit "
            "their landing page conversion funnels, targeting parameters, and production expense ratios."
        ),
    },
]


def ensure_seed_strategies() -> None:
    """Ensures default marketing strategy documents exist in MongoDB."""
    try:
        db = get_database()
        coll = db[COLLECTION_NAME]
        if coll.count_documents({}) == 0:
            coll.insert_many([dict(doc) for doc in DEFAULT_STRATEGIES])
            logger.info("Seeded %d strategy documents into MongoDB '%s'.", len(DEFAULT_STRATEGIES), COLLECTION_NAME)
    except Exception as exc:
        logger.debug("MongoDB seed strategies check: %s (using local fallback)", exc)


def search_knowledge_documents(
    query: str,
    k: int = 3,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Searches campaign strategy documents and playbooks directly from MongoDB
    with in-memory fallback for offline or standalone testing.
    """
    clean_query = query.strip() if query else ""
    if not clean_query:
        return []

    # Extract keywords for flexible matching
    terms = [re.escape(w) for w in re.split(r"\W+", clean_query) if len(w) > 2]
    regex_pattern = "|".join(terms) if terms else re.escape(clean_query)

    agency_filter = None
    if filter_metadata and "agency" in filter_metadata:
        agency_filter = filter_metadata["agency"]

    # Check ambient tenant context
    from backend.security.tenant_context import current_tenant_cv
    tenant = current_tenant_cv.get()
    if tenant:
        if agency_filter and not tenant.can_access_agency(agency_filter):
            agency_filter = tenant.agency_id
        elif not agency_filter:
            agency_filter = tenant.agency_id

    # 1. Try querying MongoDB Atlas
    results: List[Dict[str, Any]] = []
    try:
        db = get_database()
        coll = db[COLLECTION_NAME]
        ensure_seed_strategies()

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
        if results:
            return results
    except Exception as exc:
        logger.debug("MongoDB query failed, falling back to local seed strategies: %s", exc)

    # 2. Local fallback if MongoDB is unreachable or empty
    candidates = DEFAULT_STRATEGIES
    if agency_filter:
        candidates = [d for d in candidates if agency_filter.lower() in d.get("agency", "").lower()]

    for doc in candidates:
        text_block = f"{doc.get('title', '')} {doc.get('topic', '')} {doc.get('content', '')} {doc.get('agency', '')}"
        matches = len(re.findall(regex_pattern, text_block, flags=re.IGNORECASE)) if regex_pattern else 0
        if matches > 0:
            results.append(
                {
                    "title": doc.get("title", "Strategy Document"),
                    "source": doc.get("source", "Internal Documentation"),
                    "content": doc.get("content", ""),
                    "metadata": {
                        "agency": doc.get("agency", ""),
                        "topic": doc.get("topic", ""),
                        "source": doc.get("source", ""),
                    },
                    "relevance_score": min(0.99, round(0.7 + matches * 0.05, 2)),
                }
            )

    return results[:k]
