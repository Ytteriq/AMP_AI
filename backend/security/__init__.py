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
from backend.security.rate_limiter import RateLimiter, rate_limiter
from backend.security.rate_limit_middleware import (
    RateLimitMiddleware,
    RateLimitExceededException,
    rate_limit_dependency,
)
from backend.security.external_api_protection import (
    meta_api_protection,
    llm_protection,
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
    "rate_limiter",
    "rate_limit_dependency",
    "RateLimitMiddleware",
    "RateLimitExceededException",
    "meta_api_protection",
    "llm_protection",
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
