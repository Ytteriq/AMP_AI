"""
backend/security/key_manager.py
Per-agency Data Encryption Key (DEK) lifecycle, rotation, and secure caching.
Manages versioned wrapped DEKs in MongoDB 'agency_encryption_keys' collection.
Enforces that plaintext DEKs are never persisted or returned to the client.
"""

import base64
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from backend.config import settings
from backend.database.connection import AGENCY_KEYS_COLLECTION, get_database
from backend.security.exceptions import KeyManagementError, KeyNotFoundError
from backend.security.kms_service import KMSService, kms_service

logger = logging.getLogger("ai_reel.security.key_manager")


class DEKCacheEntry:
    """Represents a short-lived, TTL-bounded in-memory plaintext DEK."""
    __slots__ = ("agency_id", "key_version", "dek", "expires_at")

    def __init__(self, agency_id: str, key_version: int, dek: bytes, ttl_seconds: int) -> None:
        self.agency_id = agency_id
        self.key_version = key_version
        self.dek = dek
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class KeyManager:
    """
    Manages per-agency envelope encryption keys.
    Each agency has an independent encryption key with explicit versioning.
    """

    def __init__(
        self,
        kms: Optional[KMSService] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self.kms = kms or kms_service
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.DEK_CACHE_TTL_SECONDS
        self._cache: Dict[Tuple[str, int], DEKCacheEntry] = {}
        self._lock = threading.Lock()

    def _get_collection(self):
        db = get_database()
        return db[AGENCY_KEYS_COLLECTION]

    def _cache_get(self, agency_id: str, key_version: int) -> Optional[bytes]:
        key = (agency_id, key_version)
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.dek

    def _cache_set(self, agency_id: str, key_version: int, dek: bytes) -> None:
        key = (agency_id, key_version)
        with self._lock:
            self._cache[key] = DEKCacheEntry(agency_id, key_version, dek, self.ttl_seconds)

    def invalidate_cache(self, agency_id: str, key_version: Optional[int] = None) -> None:
        """Evicts cached DEK entries for an agency."""
        with self._lock:
            if key_version is not None:
                self._cache.pop((agency_id, key_version), None)
            else:
                to_delete = [k for k in self._cache.keys() if k[0] == agency_id]
                for k in to_delete:
                    self._cache.pop(k, None)

    def create_agency_key(self, agency_id: str, kms_key_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Provisions a new cryptographically secure 256-bit DEK for an agency.
        The DEK is encrypted via AWS KMS and persisted as a wrappedDEK.
        """
        clean_agency_id = str(agency_id).strip()
        if not clean_agency_id:
            raise KeyManagementError("Agency ID cannot be empty.")

        coll = self._get_collection()

        # Check if an active key already exists
        existing = coll.find_one({"agencyId": clean_agency_id, "status": "active"})
        if existing:
            raise KeyManagementError(f"Active encryption key already exists for agency '{clean_agency_id}'. Use rotate_agency_key instead.")

        target_kms_id = kms_key_id or self.kms.kms_key_id
        plaintext_dek, wrapped_dek_bytes = self.kms.generate_data_key(kms_key_id=target_kms_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        wrapped_b64 = base64.b64encode(wrapped_dek_bytes).decode("utf-8")

        key_doc = {
            "_id": f"{clean_agency_id}_v1",
            "agencyId": clean_agency_id,
            "wrappedDEK": wrapped_b64,
            "kmsKeyId": target_kms_id,
            "keyVersion": 1,
            "status": "active",
            "createdAt": now_iso,
            "rotatedAt": None,
        }

        coll.insert_one(key_doc)
        # Populate short-lived cache with fresh DEK
        self._cache_set(clean_agency_id, 1, plaintext_dek)

        logger.info("Successfully provisioned encryption key v1 for agency '%s'", clean_agency_id)
        return {
            "agencyId": clean_agency_id,
            "keyVersion": 1,
            "kmsKeyId": target_kms_id,
            "status": "active",
            "createdAt": now_iso,
        }

    def get_or_create_agency_key(self, agency_id: str) -> Dict[str, Any]:
        """Idempotently gets the active agency key, or provisions a new one if not found."""
        clean_agency_id = str(agency_id).strip()
        if not clean_agency_id:
            raise KeyManagementError("Agency ID cannot be empty.")

        coll = self._get_collection()
        doc = coll.find_one({"agencyId": clean_agency_id, "status": "active"})
        if doc:
            return doc
        return self.create_agency_key(clean_agency_id)

    def get_agency_key(self, agency_id: str, key_version: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves wrapped key document for an agency.
        If key_version is omitted, returns the currently active key.
        """
        clean_agency_id = str(agency_id).strip()
        coll = self._get_collection()

        query: Dict[str, Any] = {"agencyId": clean_agency_id}
        if key_version is not None:
            query["keyVersion"] = int(key_version)
        else:
            query["status"] = "active"

        doc = coll.find_one(query)
        if not doc:
            # If asking for active but none marked, find highest version
            if key_version is None:
                doc = coll.find_one({"agencyId": clean_agency_id}, sort=[("keyVersion", -1)])
            if not doc:
                raise KeyNotFoundError(f"No encryption key found for agency '{clean_agency_id}' (version={key_version}).")

        return doc

    def unwrap_dek(self, agency_id: str, key_version: Optional[int] = None) -> Tuple[bytes, int]:
        """
        Retrieves the agency's wrapped DEK and decrypts it via KMS.
        Returns (plaintext_dek, key_version).
        Checks short-lived cache before invoking KMS.
        """
        clean_agency_id = str(agency_id).strip()
        key_doc = self.get_agency_key(clean_agency_id, key_version=key_version)
        version = int(key_doc["keyVersion"])

        # 1. Try cache
        cached = self._cache_get(clean_agency_id, version)
        if cached:
            return cached, version

        # 2. Unwrap via KMS
        wrapped_b64 = key_doc["wrappedDEK"]
        wrapped_bytes = base64.b64decode(wrapped_b64)
        kms_key_id = key_doc.get("kmsKeyId")

        plaintext_dek = self.kms.decrypt_dek(wrapped_bytes, kms_key_id=kms_key_id)
        if len(plaintext_dek) != 32:
            raise KeyManagementError(f"Unwrapped DEK has invalid length: {len(plaintext_dek)}")

        # 3. Store in cache
        self._cache_set(clean_agency_id, version, plaintext_dek)
        return plaintext_dek, version

    def rotate_agency_key(self, agency_id: str, kms_key_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a new DEK for the agency with an incremented keyVersion.
        Marks previous active key as 'retired' and persists new key as 'active'.
        Invalidates cached keys for that agency.
        """
        clean_agency_id = str(agency_id).strip()
        coll = self._get_collection()

        # Find all keys for agency to determine max version
        existing_keys = list(coll.find({"agencyId": clean_agency_id}).sort("keyVersion", -1))
        if not existing_keys:
            return self.create_agency_key(clean_agency_id, kms_key_id=kms_key_id)

        current_max_version = existing_keys[0]["keyVersion"]
        new_version = current_max_version + 1

        target_kms_id = kms_key_id or self.kms.kms_key_id
        plaintext_dek, wrapped_dek_bytes = self.kms.generate_data_key(kms_key_id=target_kms_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        wrapped_b64 = base64.b64encode(wrapped_dek_bytes).decode("utf-8")

        # Mark existing active keys as retired
        coll.update_many(
            {"agencyId": clean_agency_id, "status": "active"},
            {"$set": {"status": "retired", "rotatedAt": now_iso}},
        )

        # Insert new key version
        new_key_doc = {
            "_id": f"{clean_agency_id}_v{new_version}",
            "agencyId": clean_agency_id,
            "wrappedDEK": wrapped_b64,
            "kmsKeyId": target_kms_id,
            "keyVersion": new_version,
            "status": "active",
            "createdAt": now_iso,
            "rotatedAt": None,
        }
        coll.insert_one(new_key_doc)

        # Invalidate cache and prime new version
        self.invalidate_cache(clean_agency_id)
        self._cache_set(clean_agency_id, new_version, plaintext_dek)

        logger.info(
            "Rotated encryption key for agency '%s' to version %d (previous: %d)",
            clean_agency_id,
            new_version,
            current_max_version,
        )
        return {
            "agencyId": clean_agency_id,
            "keyVersion": new_version,
            "kmsKeyId": target_kms_id,
            "status": "active",
            "createdAt": now_iso,
            "previousVersion": current_max_version,
        }

    def rewrap_agency_key(self, agency_id: str, new_kms_key_id: str, key_version: Optional[int] = None) -> Dict[str, Any]:
        """
        Rewraps an existing agency DEK under a new AWS KMS Key ID without changing
        the underlying DEK itself (meaning existing encrypted data does not need re-encryption).
        """
        clean_agency_id = str(agency_id).strip()
        coll = self._get_collection()

        key_doc = self.get_agency_key(clean_agency_id, key_version=key_version)
        version = key_doc["keyVersion"]

        # Unwrap with old KMS key
        plaintext_dek, _ = self.unwrap_dek(clean_agency_id, key_version=version)

        # Wrap with new KMS key
        new_wrapped_bytes = self.kms.encrypt_dek(plaintext_dek, kms_key_id=new_kms_key_id)
        new_wrapped_b64 = base64.b64encode(new_wrapped_bytes).decode("utf-8")

        now_iso = datetime.now(timezone.utc).isoformat()
        coll.update_one(
            {"_id": key_doc["_id"]},
            {
                "$set": {
                    "wrappedDEK": new_wrapped_b64,
                    "kmsKeyId": new_kms_key_id,
                    "rewrappedAt": now_iso,
                }
            },
        )

        # Invalidate cache so next access refreshes
        self.invalidate_cache(clean_agency_id, version)

        logger.info(
            "Rewrapped DEK for agency '%s' (v%d) under new KMS Key ID: %s",
            clean_agency_id,
            version,
            new_kms_key_id,
        )
        return {
            "agencyId": clean_agency_id,
            "keyVersion": version,
            "newKmsKeyId": new_kms_key_id,
            "rewrappedAt": now_iso,
        }


# Global singleton KeyManager
key_manager = KeyManager()
