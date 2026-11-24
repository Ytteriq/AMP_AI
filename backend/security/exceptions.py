"""
backend/security/exceptions.py
Domain-specific exceptions for tenant isolation, key management, and cryptographic operations.
"""


class SecurityError(Exception):
    """Base exception for all security, encryption, and tenant isolation operations."""
    pass


class TenantAuthorizationError(SecurityError):
    """Raised when authentication fails, token is missing/expired, or membership is invalid."""
    def __init__(self, message: str = "Tenant authentication or authorization failed.", status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class TenantAccessDeniedError(TenantAuthorizationError):
    """Raised when an authenticated actor attempts to access resources belonging to another agency."""
    def __init__(self, message: str = "Access to requested agency resource is forbidden.", status_code: int = 403):
        super().__init__(message, status_code=status_code)


class EncryptionError(SecurityError):
    """Raised when encryption of a payload fails."""
    pass


class DecryptionError(SecurityError):
    """Raised when decryption of an encrypted payload fails."""
    pass


class TamperedCiphertextError(DecryptionError):
    """Raised when ciphertext, authentication tag, or nonce has been altered or corrupted."""
    pass


class CrossAgencySubstitutionError(DecryptionError):
    """Raised when an encrypted payload is attempted to be decrypted under a different agency's context."""
    pass


class KeyManagementError(SecurityError):
    """Base exception for agency key management and lifecycle operations."""
    pass


class KeyNotFoundError(KeyManagementError):
    """Raised when an agency's data encryption key cannot be retrieved."""
    pass


class KMSError(SecurityError):
    """Raised when AWS KMS operations fail."""
    pass


class InvalidPayloadError(SecurityError):
    """Raised when an encrypted payload structure is malformed or missing required schema fields."""
    pass
