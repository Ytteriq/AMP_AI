"""
backend/security/__init__.py
Exports security and multi-tenant isolation modules.
"""

from backend.security.audit_logger import AuditLogger, audit_logger
from backend.security.encryption_service import (
    EncryptionService,
    encryption_service,
)
from backend.security.exceptions import (
    CrossAgencySubstitutionError,
    DecryptionError,
    EncryptionError,
    InvalidPayloadError,
    KeyManagementError,
    KeyNotFoundError,
    KMSError,
    SecurityError,
    TamperedCiphertextError,
    TenantAccessDeniedError,
    TenantAuthorizationError,
)
from backend.security.key_manager import KeyManager, key_manager
from backend.security.kms_service import KMSService, kms_service
from backend.security.tenant_context import (
    TenantContext,
    create_tenant_token,
    decode_tenant_token,
    get_current_tenant,
    require_roles,
    current_tenant_cv,
)

__all__ = [
    "AuditLogger",
    "audit_logger",
    "EncryptionService",
    "encryption_service",
    "KeyManager",
    "key_manager",
    "KMSService",
    "kms_service",
    "TenantContext",
    "create_tenant_token",
    "decode_tenant_token",
    "get_current_tenant",
    "require_roles",
    "current_tenant_cv",
    "SecurityError",
    "TenantAuthorizationError",
    "TenantAccessDeniedError",
    "EncryptionError",
    "DecryptionError",
    "TamperedCiphertextError",
    "CrossAgencySubstitutionError",
    "KeyManagementError",
    "KeyNotFoundError",
    "KMSError",
    "InvalidPayloadError",
]
