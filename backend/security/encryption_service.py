"""
backend/security/encryption_service.py
Reusable, production-grade AES-256-GCM per-agency encryption service.
Uses Authenticated Additional Data (AAD) bound to (agency_id, record_id, algorithm, schema_version).
Enforces fresh 96-bit nonces, detects tampered payloads, and prevents cross-agency ciphertext substitution.
"""

import base64
from datetime import date, datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple, Union
from bson import ObjectId

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.security.exceptions import (
    CrossAgencySubstitutionError,
    DecryptionError,
    EncryptionError,
    InvalidPayloadError,
    TamperedCiphertextError,
)
from backend.security.key_manager import KeyManager, key_manager

logger = logging.getLogger("ai_reel.security.encryption")

ALGORITHM_NAME = "AES-256-GCM"
CURRENT_SCHEMA_VERSION = 1
NONCE_BYTES_LENGTH = 12
AUTH_TAG_BYTES_LENGTH = 16


class SafeJSONEncoder(json.JSONEncoder):
    """Encodes MongoDB ObjectIds, datetimes, and custom objects safely."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("utf-8")
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return obj.model_dump()
        if hasattr(obj, "dict") and callable(obj.dict):
            return obj.dict()
        return super().default(obj)


def serialize_payload(data: Any) -> bytes:
    """Serializes arbitrary python data to canonical UTF-8 JSON bytes."""
    return json.dumps(data, cls=SafeJSONEncoder, sort_keys=True, ensure_ascii=False).encode("utf-8")


def deserialize_payload(raw_bytes: bytes) -> Any:
    """Deserializes UTF-8 JSON bytes back to Python data structure."""
    return json.loads(raw_bytes.decode("utf-8"))


class EncryptionService:
    """
    Per-agency cryptographic service implementing AES-256-GCM authenticated envelope encryption.
    """

    def __init__(self, km: Optional[KeyManager] = None) -> None:
        self.key_manager = km or key_manager

    @staticmethod
    def construct_aad(agency_id: str, record_id: str, algorithm: str = ALGORITHM_NAME, schema_version: int = CURRENT_SCHEMA_VERSION) -> bytes:
        """
        Builds Authenticated Additional Data (AAD) cryptographically binding the ciphertext
        to the agency, record ID, algorithm, and schema version.
        """
        clean_agency = str(agency_id).strip()
        clean_record = str(record_id).strip()
        return f"{clean_agency}:{clean_record}:{algorithm}:{schema_version}".encode("utf-8")

    def create_agency_key(self, agency_id: str) -> Dict[str, Any]:
        """Provisions a new envelope encryption key for the agency."""
        return self.key_manager.create_agency_key(agency_id)

    def rotate_agency_key(self, agency_id: str) -> Dict[str, Any]:
        """Rotates the agency's encryption key to a new version."""
        return self.key_manager.rotate_agency_key(agency_id)

    def verify_encrypted_payload(self, encrypted_data: Dict[str, Any]) -> None:
        """
        Validates that the provided dictionary contains valid envelope encryption fields.
        Raises InvalidPayloadError if malformed.
        """
        if not isinstance(encrypted_data, dict):
            raise InvalidPayloadError("Encrypted payload must be a dictionary.")

        # Support both top-level payload structure and nested encryptedPayload structure
        payload = encrypted_data.get("encryptedPayload", encrypted_data)
        if not isinstance(payload, dict):
            raise InvalidPayloadError("encryptedPayload must be a dictionary.")

        for required_field in ("ciphertext", "nonce", "authTag"):
            val = payload.get(required_field)
            if not val or not isinstance(val, str):
                raise InvalidPayloadError(f"Missing or invalid required encryption field: '{required_field}'.")

    def encrypt_agency_data(
        self,
        agency_id: str,
        record_id: str,
        data: Any,
        user_id: Optional[str] = None,
        feature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Encrypts arbitrary agency data using the agency's active DEK with AES-256-GCM.
        Generates a fresh 96-bit nonce and binds AAD to agency_id and record_id.
        Returns the standardized MongoDB document structure ready for ai_outputs.
        """
        clean_agency = str(agency_id).strip()
        clean_record = str(record_id).strip()
        if not clean_agency:
            raise EncryptionError("agency_id is required for encryption.")
        if not clean_record:
            raise EncryptionError("record_id is required for encryption.")

        # Ensure agency has a key
        try:
            dek, key_version = self.key_manager.unwrap_dek(clean_agency)
        except Exception:
            # Auto-provision on first AI output if key does not exist
            self.key_manager.get_or_create_agency_key(clean_agency)
            dek, key_version = self.key_manager.unwrap_dek(clean_agency)

        try:
            plaintext_bytes = serialize_payload(data)
            nonce = os.urandom(NONCE_BYTES_LENGTH)
            aad = self.construct_aad(clean_agency, clean_record, ALGORITHM_NAME, CURRENT_SCHEMA_VERSION)

            aesgcm = AESGCM(dek)
            combined_ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, aad)

            # Separate ciphertext and 16-byte authentication tag
            ciphertext_bytes = combined_ciphertext[:-AUTH_TAG_BYTES_LENGTH]
            auth_tag_bytes = combined_ciphertext[-AUTH_TAG_BYTES_LENGTH:]

            now_iso = datetime.now(timezone.utc).isoformat()
            doc = {
                "_id": clean_record,
                "agencyId": clean_agency,
                "userId": str(user_id or "system"),
                "feature": str(feature or "general_ai_output"),
                "encryptedPayload": {
                    "ciphertext": base64.b64encode(ciphertext_bytes).decode("utf-8"),
                    "nonce": base64.b64encode(nonce).decode("utf-8"),
                    "authTag": base64.b64encode(auth_tag_bytes).decode("utf-8"),
                },
                "keyVersion": key_version,
                "algorithm": ALGORITHM_NAME,
                "schemaVersion": CURRENT_SCHEMA_VERSION,
                "createdAt": now_iso,
                "updatedAt": now_iso,
            }
            return doc
        except Exception as exc:
            logger.error("Encryption failed for agency '%s', record '%s': %s", clean_agency, clean_record, exc)
            raise EncryptionError(f"Failed to encrypt data: {str(exc)}") from exc
        finally:
            # Clear local reference
            del dek

    def decrypt_agency_data(
        self,
        agency_id: str,
        record_id: str,
        encrypted_data: Dict[str, Any],
    ) -> Any:
        """
        Decrypts an encrypted AI output payload.
        Verifies agency ownership, schema integrity, fresh nonce, and AAD tag.
        Rejects cross-agency ciphertext substitution and tampered ciphertext.
        """
        clean_agency = str(agency_id).strip()
        clean_record = str(record_id).strip()

        if not clean_agency:
            raise DecryptionError("agency_id is required for decryption.")
        if not clean_record:
            raise DecryptionError("record_id is required for decryption.")

        # 1. Structure validation
        self.verify_encrypted_payload(encrypted_data)

        # 2. Prevent cross-agency substitution
        payload_agency = encrypted_data.get("agencyId")
        if payload_agency and str(payload_agency).strip() != clean_agency:
            logger.warning(
                "Cross-agency ciphertext substitution detected! Calling agency: '%s', record owner: '%s'",
                clean_agency,
                payload_agency,
            )
            raise CrossAgencySubstitutionError(
                f"Cross-agency access violation: payload belongs to '{payload_agency}', not '{clean_agency}'."
            )

        # 3. Prevent record ID substitution
        payload_record = encrypted_data.get("_id")
        if payload_record and str(payload_record).strip() != clean_record:
            raise TamperedCiphertextError(
                f"Record ID mismatch: expected '{clean_record}', got '{payload_record}'."
            )

        payload = encrypted_data.get("encryptedPayload", encrypted_data)
        key_version = encrypted_data.get("keyVersion", 1)
        algo = encrypted_data.get("algorithm", ALGORITHM_NAME)
        schema_ver = encrypted_data.get("schemaVersion", CURRENT_SCHEMA_VERSION)

        try:
            ciphertext_bytes = base64.b64decode(payload["ciphertext"])
            nonce_bytes = base64.b64decode(payload["nonce"])
            auth_tag_bytes = base64.b64decode(payload["authTag"])
        except Exception as b64_err:
            raise InvalidPayloadError(f"Corrupted base64 encoding in encrypted payload: {str(b64_err)}") from b64_err

        if len(nonce_bytes) != NONCE_BYTES_LENGTH:
            raise TamperedCiphertextError(f"Invalid nonce length: {len(nonce_bytes)} bytes (expected {NONCE_BYTES_LENGTH}).")
        if len(auth_tag_bytes) != AUTH_TAG_BYTES_LENGTH:
            raise TamperedCiphertextError(f"Invalid authTag length: {len(auth_tag_bytes)} bytes (expected {AUTH_TAG_BYTES_LENGTH}).")

        # 4. Retrieve key by version
        try:
            dek, _ = self.key_manager.unwrap_dek(clean_agency, key_version=key_version)
        except Exception as ke:
            raise DecryptionError(f"Failed to retrieve encryption key for agency '{clean_agency}' (v{key_version}): {str(ke)}") from ke

        # 5. Construct AAD and perform authenticated decryption
        aad = self.construct_aad(clean_agency, clean_record, algo, schema_ver)
        combined_ciphertext = ciphertext_bytes + auth_tag_bytes

        try:
            aesgcm = AESGCM(dek)
            plaintext_bytes = aesgcm.decrypt(nonce_bytes, combined_ciphertext, aad)
            return deserialize_payload(plaintext_bytes)
        except InvalidTag as it:
            logger.error("AES-GCM authentication failed for agency '%s', record '%s'. Possible tampering or key mismatch.", clean_agency, clean_record)
            raise TamperedCiphertextError("Authentication tag or ciphertext has been altered or decrypted with invalid key.") from it
        except Exception as exc:
            logger.error("Decryption failed for agency '%s', record '%s': %s", clean_agency, clean_record, exc)
            raise DecryptionError(f"Failed to decrypt payload: {str(exc)}") from exc
        finally:
            del dek

    def re_encrypt_agency_data(
        self,
        agency_id: str,
        record_id: str,
        encrypted_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Decrypts data using its existing key version and re-encrypts it under the
        agency's current active key version (used after key rotation or during migrations).
        """
        # 1. Decrypt with existing key
        decrypted = self.decrypt_agency_data(agency_id, record_id, encrypted_data)
        user_id = encrypted_data.get("userId")
        feature = encrypted_data.get("feature")

        # 2. Re-encrypt under active key
        return self.encrypt_agency_data(
            agency_id=agency_id,
            record_id=record_id,
            data=decrypted,
            user_id=user_id,
            feature=feature,
        )


# Global singleton EncryptionService
encryption_service = EncryptionService()
