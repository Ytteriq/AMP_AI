"""
backend/security/kms_service.py
Production-grade AWS KMS envelope encryption service.
Wraps and unwraps agency Data Encryption Keys (DEKs) using AWS KMS Customer Master Keys (CMKs).
Includes secure local master key fallback for offline testing and air-gapped development.
"""

import base64
import hashlib
import logging
import os
from typing import Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings
from backend.security.exceptions import KMSError

logger = logging.getLogger("ai_reel.security.kms")


class KMSService:
    """
    AWS Key Management Service (KMS) integration for envelope encryption.
    DEKs are never stored in plaintext: they are encrypted (wrapped) by KMS CMKs
    before being persisted to the database.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        kms_key_id: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        mock_fallback: bool = True,
    ) -> None:
        self.region_name = region_name or settings.AWS_REGION or "us-east-1"
        self.kms_key_id = kms_key_id or settings.AWS_KMS_KEY_ID or "arn:aws:kms:us-east-1:123456789012:key/amp-root-master-key"
        self.endpoint_url = endpoint_url or (settings.AWS_KMS_ENDPOINT_URL if settings.AWS_KMS_ENDPOINT_URL else None)
        self.mock_fallback = mock_fallback if mock_fallback is not None else settings.KMS_MOCK_FALLBACK

        self._client = None
        self._is_live = False
        self._init_client()

    def _init_client(self) -> None:
        """Initializes boto3 KMS client if AWS credentials or endpoints are available."""
        has_creds = bool(
            os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("AWS_ROLE_ARN")
            or os.getenv("AWS_PROFILE")
            or settings.AWS_ACCESS_KEY_ID
        )
        if (has_creds or self.endpoint_url) and not (self.kms_key_id.startswith("arn:aws:kms") and "123456789012" in self.kms_key_id):
            try:
                session = boto3.Session(
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
                    region_name=self.region_name,
                )
                self._client = session.client("kms", endpoint_url=self.endpoint_url)
                # Verify connectivity with describe_key or get_caller_identity if key is set
                self._is_live = True
                logger.info("Initialized live AWS KMS client for region: %s", self.region_name)
                return
            except Exception as exc:
                logger.warning("AWS KMS client initialization error: %s. Using mock fallback: %s", exc, self.mock_fallback)

        if not self.mock_fallback:
            raise KMSError("AWS KMS credentials / key not configured and mock fallback is disabled.")
        logger.info("Using local cryptographic Master Key mock for AWS KMS envelope encryption.")
        self._client = None
        self._is_live = False

    def _get_mock_master_key(self) -> bytes:
        """
        Generates deterministic 256-bit root master key from SESSION_SECRET for local mock.
        Strictly used only when AWS KMS is not configured.
        """
        seed = settings.SESSION_SECRET.encode("utf-8")
        return hashlib.sha256(b"AMP_KMS_MOCK_MASTER_ROOT_KEY:" + seed).digest()

    def encrypt_dek(self, plaintext_dek: bytes, kms_key_id: Optional[str] = None) -> bytes:
        """
        Encrypts a raw 256-bit agency DEK using AWS KMS (or local mock CMK).
        Returns ciphertext blob (wrapped DEK).
        """
        if not plaintext_dek or len(plaintext_dek) != 32:
            raise KMSError("DEK must be a valid 256-bit (32 bytes) binary key.")

        key_id = kms_key_id or self.kms_key_id

        if self._is_live and self._client:
            try:
                response = self._client.encrypt(
                    KeyId=key_id,
                    Plaintext=plaintext_dek,
                    EncryptionAlgorithm="SYMMETRIC_DEFAULT",
                )
                return response["CiphertextBlob"]
            except (BotoCoreError, ClientError) as exc:
                logger.error("AWS KMS encrypt failed: %s", exc)
                raise KMSError(f"AWS KMS encrypt_dek failed: {str(exc)}") from exc

        # Local mock implementation of KMS CMK envelope encryption
        master_key = self._get_mock_master_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(master_key)
        aad = f"KMS_MOCK_CMK:{key_id}".encode("utf-8")
        encrypted = aesgcm.encrypt(nonce, plaintext_dek, aad)
        # Pack nonce + encrypted as wrappedDEK blob
        return nonce + encrypted

    def decrypt_dek(self, wrapped_dek: bytes, kms_key_id: Optional[str] = None) -> bytes:
        """
        Decrypts a wrapped agency DEK using AWS KMS (or local mock CMK).
        Returns raw 256-bit plaintext DEK.
        """
        if not wrapped_dek or len(wrapped_dek) < 28:
            raise KMSError("Invalid wrapped DEK payload: data too short.")

        key_id = kms_key_id or self.kms_key_id

        if self._is_live and self._client:
            try:
                response = self._client.decrypt(
                    CiphertextBlob=wrapped_dek,
                    KeyId=key_id,
                    EncryptionAlgorithm="SYMMETRIC_DEFAULT",
                )
                plaintext = response["Plaintext"]
                if len(plaintext) != 32:
                    raise KMSError(f"Decrypted DEK has unexpected length: {len(plaintext)} (expected 32 bytes)")
                return plaintext
            except (BotoCoreError, ClientError) as exc:
                logger.error("AWS KMS decrypt failed: %s", exc)
                raise KMSError(f"AWS KMS decrypt_dek failed: {str(exc)}") from exc

        # Local mock implementation
        master_key = self._get_mock_master_key()
        nonce = wrapped_dek[:12]
        ciphertext_and_tag = wrapped_dek[12:]
        aesgcm = AESGCM(master_key)
        aad = f"KMS_MOCK_CMK:{key_id}".encode("utf-8")
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, aad)
            if len(plaintext) != 32:
                raise KMSError("Decrypted mock DEK has invalid length.")
            return plaintext
        except Exception as exc:
            raise KMSError(f"Mock KMS unwrap failed: {str(exc)}") from exc

    def generate_data_key(self, kms_key_id: Optional[str] = None) -> Tuple[bytes, bytes]:
        """
        Generates a new 256-bit DEK, returning (plaintext_dek, wrapped_dek).
        """
        key_id = kms_key_id or self.kms_key_id
        if self._is_live and self._client:
            try:
                response = self._client.generate_data_key(
                    KeyId=key_id,
                    KeySpec="AES_256",
                )
                return response["Plaintext"], response["CiphertextBlob"]
            except (BotoCoreError, ClientError) as exc:
                logger.error("AWS KMS generate_data_key failed: %s", exc)
                raise KMSError(f"AWS KMS generate_data_key failed: {str(exc)}") from exc

        # Local mock generation
        plaintext_dek = os.urandom(32)
        wrapped_dek = self.encrypt_dek(plaintext_dek, kms_key_id=key_id)
        return plaintext_dek, wrapped_dek


# Global singleton KMS service
kms_service = KMSService()
