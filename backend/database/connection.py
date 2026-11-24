"""
database/connection.py
Manages MongoDB Atlas connection, client lifecycle, health checks, and collection access.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional
from bson import ObjectId

from dotenv import find_dotenv, load_dotenv
import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError, PyMongoError, ServerSelectionTimeoutError

# Locate and load environment variables
env_file = find_dotenv(usecwd=True)
if not env_file:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "..", ".env"),
        os.path.join(script_dir, "..", "..", ".env"),
        os.path.join(script_dir, ".env"),
    ]
    for c in candidates:
        if os.path.exists(c):
            env_file = c
            break

if env_file:
    load_dotenv(env_file)
else:
    load_dotenv()

try:
    from backend.config import settings
    MONGODB_URI = settings.MONGODB_URI or os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE = settings.MONGODB_DATABASE or os.getenv("MONGODB_DATABASE", "ytteriq_amp_ai")
    DEFAULT_COLLECTION = settings.MONGODB_COLLECTION or os.getenv("MONGODB_COLLECTION", "reels")
except ImportError:
    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "ytteriq_amp_ai")
    DEFAULT_COLLECTION = os.getenv("MONGODB_COLLECTION", "reels")

# Standardized multi-tenant shared collection names
AI_OUTPUTS_COLLECTION = "ai_outputs"
AGENCY_KEYS_COLLECTION = "agency_encryption_keys"
AGENCY_AI_METADATA_COLLECTION = "agency_ai_metadata"
REPORTS_COLLECTION = "reports"
CLIENTS_COLLECTION = "clients"
CAMPAIGNS_COLLECTION = "campaigns"
CREATIVES_COLLECTION = "creatives"
REELS_COLLECTION = "reels"
STRATEGIES_COLLECTION = "strategies"
CONTENT_CALENDAR_COLLECTION = "content_calendar"

# Meta Marketing API sync collections
CAMPAIGN_METRICS_COLLECTION = "campaign_metrics"
PERIOD_REACH_COLLECTION = "period_reach"
AD_SETS_COLLECTION = "ad_sets"
ADS_COLLECTION = "ads"
PRODUCTS_COLLECTION = "products"
PLATFORM_CONNECTIONS_COLLECTION = "platform_connections"
SYNC_JOBS_COLLECTION = "sync_jobs"

# Global singleton client
_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """
    Returns the singleton MongoClient instance connected strictly to MongoDB.
    Raises ConnectionFailure if MONGODB_URI is missing or the cluster is unreachable.
    """
    global _client
    if _client is not None:
        return _client

    uri = os.getenv("MONGODB_URI", "") or MONGODB_URI
    if not uri:
        raise ConnectionFailure("MONGODB_URI is not configured in the environment.")

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
        retryWrites=True,
        appname="AI_Reel_Analyst",
    )
    client.admin.command("ping")
    _client = client
    return _client


def get_database(db_name: Optional[str] = None) -> Database:
    """Returns the configured MongoDB database."""
    target_db = db_name or os.getenv("MONGODB_DATABASE", MONGODB_DATABASE)
    client = get_mongo_client()
    return client[target_db]


def get_collection(collection_name: Optional[str] = None) -> Collection:
    """
    Returns the specified collection (defaults to 'reels').
    Checks that the database connection is valid.
    """
    target_coll = collection_name or os.getenv("MONGODB_COLLECTION", DEFAULT_COLLECTION)
    db = get_database()
    return db[target_coll]


def close_mongo_client() -> None:
    """Closes the MongoDB connection safely during application shutdown."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        finally:
            _client = None


def ensure_database_indexes(db: Optional[Database] = None) -> Dict[str, Any]:
    """
    Ensures that all multi-tenant shared collections have proper compound indexes
    for high-performance tenant-isolated queries and uniqueness constraints.
    Preserves existing indexes and collections safely.
    """
    target_db = db if db is not None else get_database()
    index_results: Dict[str, List[str]] = {}

    index_specs = {
        AI_OUTPUTS_COLLECTION: [
            ([("agencyId", pymongo.ASCENDING), ("createdAt", pymongo.DESCENDING)], {"name": "idx_ai_outputs_agency_created"}),
            ([("agencyId", pymongo.ASCENDING), ("feature", pymongo.ASCENDING)], {"name": "idx_ai_outputs_agency_feature"}),
            ([("agencyId", pymongo.ASCENDING), ("userId", pymongo.ASCENDING)], {"name": "idx_ai_outputs_agency_user"}),
        ],
        AGENCY_KEYS_COLLECTION: [
            ([("agencyId", pymongo.ASCENDING), ("keyVersion", pymongo.ASCENDING)], {"name": "idx_keys_agency_version", "unique": True}),
            ([("agencyId", pymongo.ASCENDING)], {"name": "idx_keys_agency"}),
        ],
        AGENCY_AI_METADATA_COLLECTION: [
            ([("agencyId", pymongo.ASCENDING), ("feature", pymongo.ASCENDING)], {"name": "idx_meta_agency_feature"}),
            ([("agencyId", pymongo.ASCENDING), ("createdAt", pymongo.DESCENDING)], {"name": "idx_meta_agency_created"}),
        ],
        REPORTS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("creation_date", pymongo.DESCENDING)], {"name": "idx_reports_agency_date"}),
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_reports_agency_client"}),
        ],
        CLIENTS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_clients_agency_client"}),
        ],
        CAMPAIGNS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_campaigns_agency_client"}),
        ],
        CAMPAIGN_METRICS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING), ("date", pymongo.DESCENDING)], {"name": "idx_cmp_metrics_date"}),
            ([("agency_id", pymongo.ASCENDING), ("campaign_id", pymongo.ASCENDING)], {"name": "idx_cmp_metrics_cmp"}),
        ],
        PERIOD_REACH_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_period_reach_client"}),
        ],
        AD_SETS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("campaign_id", pymongo.ASCENDING)], {"name": "idx_adsets_campaign"}),
        ],
        ADS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("campaign_id", pymongo.ASCENDING)], {"name": "idx_ads_campaign"}),
        ],
        PRODUCTS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_products_client"}),
        ],
        PLATFORM_CONNECTIONS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_platform_conn_client"}),
        ],
        SYNC_JOBS_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)], {"name": "idx_sync_jobs_created"}),
        ],
        CONTENT_CALENDAR_COLLECTION: [
            ([("agency_id", pymongo.ASCENDING), ("client_id", pymongo.ASCENDING)], {"name": "idx_content_cal_client"}),
        ],
    }

    for coll_name, specs in index_specs.items():
        coll = target_db[coll_name]
        created_for_coll = []
        for keys, kwargs in specs:
            try:
                idx_name = coll.create_index(keys, **kwargs)
                created_for_coll.append(idx_name)
            except Exception:
                # Fallback for environments / mocks where specific index options are unsupported
                try:
                    idx_name = coll.create_index(keys)
                    created_for_coll.append(idx_name)
                except Exception:
                    pass
        index_results[coll_name] = created_for_coll

    return index_results


def check_database_health() -> Dict[str, Any]:
    """
    Checks MongoDB connectivity and returns operational health metadata.
    Does not expose sensitive credentials in response.
    """
    start_time = time.time()
    try:
        client = get_mongo_client()
        client.admin.command("ping")
        latency_ms = round((time.time() - start_time) * 1000, 2)

        db = get_database()
        collections = db.list_collection_names()
        coll = get_collection()
        doc_count = coll.count_documents({})
        ensure_database_indexes(db)

        return {
            "status": "healthy",
            "database": db.name,
            "collection": coll.name,
            "document_count": doc_count,
            "available_collections": collections,
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as exc:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "unhealthy",
            "database": os.getenv("MONGODB_DATABASE", MONGODB_DATABASE),
            "collection": DEFAULT_COLLECTION,
            "document_count": 0,
            "available_collections": [],
            "latency_ms": latency_ms,
            "error": str(exc),
        }
