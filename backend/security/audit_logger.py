"""
backend/security/audit_logger.py
Structured audit logging for tenant data access, key management, and cryptographic events.
Redacts all sensitive payloads, plaintext DEKs, secrets, and customer data.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_reel.audit")

REDACTED_TEXT = "[REDACTED]"
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "dek",
    "key",
    "plaintext",
    "ciphertext",
    "wrappeddek",
    "authtag",
    "cookie",
    "authorization",
    "credit_card",
    "revenue",
    "prompt",
    "answer",
}


def redact_sensitive_dict(data: Any) -> Any:
    """Recursively removes or masks sensitive credentials and data payloads from logs."""
    if isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                clean[k] = REDACTED_TEXT
            elif isinstance(v, (dict, list)):
                clean[k] = redact_sensitive_dict(v)
            else:
                clean[k] = v
        return clean
    elif isinstance(data, list):
        return [redact_sensitive_dict(item) for item in data]
    return data


class AuditLogger:
    """Centralized security audit logger for compliance and operational tracking."""

    @staticmethod
    def log_event(
        event_type: str,
        agency_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Emits a structured audit entry. Never logs plaintext data or credentials.
        """
        clean_details = redact_sensitive_dict(details or {})
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agency_id": agency_id or "ANONYMOUS",
            "user_id": user_id or "ANONYMOUS",
            "resource_id": resource_id or "N/A",
            "status": status,
            "details": clean_details,
        }

        log_level = logging.INFO if status == "SUCCESS" else logging.WARNING
        logger.log(log_level, "AUDIT_EVENT: %s", json.dumps(record, default=str))
        return record


# Global singleton audit logger
audit_logger = AuditLogger()
