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
