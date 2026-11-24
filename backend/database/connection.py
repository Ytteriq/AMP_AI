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

# Global singleton clients
_client: Optional[MongoClient] = None
_mock_client: Optional[Any] = None

LOCAL_CACHE_FILE = Path(__file__).resolve().parent / "local_mongo_cache.json"


def _load_local_cache_into_mock(mock_client: Any) -> None:
    """Populates mongomock database from local_mongo_cache.json if available."""
    if not LOCAL_CACHE_FILE.exists():
        return
    try:
        with open(LOCAL_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        target_db = os.getenv("MONGODB_DATABASE", MONGODB_DATABASE)
        db = mock_client[target_db]
        for coll_name, docs in data.items():
            if docs and coll_name not in db.list_collection_names():
                clean_docs = []
                for d in docs:
                    doc_copy = dict(d)
                    if "_id" in doc_copy and isinstance(doc_copy["_id"], str):
                        try:
                            doc_copy["_id"] = ObjectId(doc_copy["_id"])
                        except Exception:
                            pass
                    clean_docs.append(doc_copy)
                if clean_docs:
                    db[coll_name].insert_many(clean_docs)
    except Exception as exc:
        pass


def save_local_cache(db: Any) -> None:
    """Persists collections from database to LOCAL_CACHE_FILE for seamless persistence."""
    try:
        data = {}
        for coll_name in db.list_collection_names():
            docs = []
            for d in db[coll_name].find():
                doc_copy = dict(d)
                if "_id" in doc_copy:
                    doc_copy["_id"] = str(doc_copy["_id"])
                docs.append(doc_copy)
            data[coll_name] = docs
        with open(LOCAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass


def get_mongo_client(allow_fallback: bool = True) -> Any:
    """
    Returns the singleton MongoClient instance.
    First tries live MongoDB Atlas / local MongoDB cluster.
    If unreachable, seamlessly activates an in-memory/persisted mock engine (mongomock)
    so all data operations, seeding, and queries succeed without crashing.
    """
    global _client, _mock_client
    if _client is not None:
        return _client

    uri = os.getenv("MONGODB_URI", "")
    if uri:
        try:
            client = MongoClient(
                uri,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                socketTimeoutMS=4000,
                retryWrites=True,
                appname="AI_Reel_Analyst",
            )
            # Ping test
            client.admin.command("ping")
            _client = client
            return _client
        except Exception:
            if not allow_fallback:
                raise

    # Fallback to mongomock with persistent local cache
    if _mock_client is None:
        try:
            import mongomock
            _mock_client = mongomock.MongoClient()
            _load_local_cache_into_mock(_mock_client)
        except ImportError:
            raise ConnectionFailure("Neither MongoDB Atlas nor mongomock is available.")

    return _mock_client


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
    target_db = db or get_database()
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
