"""
tools/database_tools.py
Implements query_reel_data tool for querying live structured reel records from MongoDB Atlas.
Validates filters and parameters without allowing arbitrary or injection-prone database commands.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pymongo import ASCENDING

from backend.database.connection import get_collection


def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert MongoDB ObjectId and datetime to JSON-serializable types."""
    res = {}
    for k, v in doc.items():
        if k == "_id":
            res["_id"] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res


@tool
def query_reel_data(
    reel_id: Optional[str] = None,
    agency_name: Optional[str] = None,
    campaign_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
) -> Dict[str, Any]:
    """
    Retrieve current structured reel performance records from MongoDB.

    Parameters:
    - reel_id: Specific reel ID (e.g., 'REEL_IND_001').
    - agency_name: Filter by managing agency (e.g., 'PulseMedia Digital', 'Apex Growth Lab').
    - campaign_name: Filter by campaign name (e.g., 'HydraGlow Summer 2026').
    - start_date: Filter reels published on or after date ('YYYY-MM-DD').
    - end_date: Filter reels published on or before date ('YYYY-MM-DD').
    - limit: Maximum number of records to return (default 20, max 100).
    - skip: Number of records to skip for pagination.
    """
    collection = get_collection()

    query_filter: Dict[str, Any] = {}
    applied_filters: Dict[str, Any] = {}

    if reel_id:
        query_filter["reel_id"] = reel_id.strip()
        applied_filters["reel_id"] = reel_id.strip()

    if agency_name:
        # Case-insensitive matching for user convenience
        query_filter["agency_name"] = {"$regex": f"^{agency_name.strip()}$", "$options": "i"}
        applied_filters["agency_name"] = agency_name.strip()

    if campaign_name:
        query_filter["campaign_name"] = {"$regex": f"^{campaign_name.strip()}$", "$options": "i"}
        applied_filters["campaign_name"] = campaign_name.strip()

    # Date range filters
    date_filter: Dict[str, Any] = {}
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.strip()).replace(tzinfo=timezone.utc)
            date_filter["$gte"] = start_dt
            applied_filters["start_date"] = start_date
        except Exception:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.strip()).replace(tzinfo=timezone.utc)
            date_filter["$lte"] = end_dt
            applied_filters["end_date"] = end_date
        except Exception:
            pass

    if date_filter:
        query_filter["published_at"] = date_filter

    safe_limit = max(1, min(limit, 100))
    safe_skip = max(0, skip)

    cursor = (
        collection.find(query_filter)
        .sort("published_at", ASCENDING)
        .skip(safe_skip)
        .limit(safe_limit)
    )

    raw_docs = list(cursor)
    serialized_docs = [_serialize_doc(doc) for doc in raw_docs]

    # Compute reporting period from retrieved records
    dates = [
        d["published_at"]
        for d in serialized_docs
        if "published_at" in d and d["published_at"]
    ]
    reporting_period = {
        "earliest_published_at": min(dates) if dates else None,
        "latest_published_at": max(dates) if dates else None,
    }

    return {
        "records": serialized_docs,
        "total_matching": len(serialized_docs),
        "applied_filters": applied_filters,
        "reporting_period": reporting_period,
        "data_freshness": datetime.now(timezone.utc).isoformat(),
    }
