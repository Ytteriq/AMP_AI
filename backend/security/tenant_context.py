"""
backend/security/tenant_context.py
Centralized tenant identification, server-side agency membership verification, and RBAC.
Derives agency identity strictly from verified server-side tokens and sessions.
Rejects any unverified agencyId supplied via query parameters or body payloads.
"""

from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import Depends, Header, HTTPException, Request, status
import jwt

from backend.config import settings
from backend.database.connection import get_database
from backend.security.audit_logger import audit_logger
from backend.security.exceptions import (
    TenantAccessDeniedError,
    TenantAuthorizationError,
)

logger = logging.getLogger("ai_reel.security.tenant")

JWT_ALGORITHM = "HS256"

# Thread-safe ContextVar providing ambient tenant context to downstream tools & agents
current_tenant_cv: ContextVar[Optional["TenantContext"]] = ContextVar("current_tenant_cv", default=None)


class TenantContext:
    """Immutable verified tenant context for the active backend request."""

    def __init__(
        self,
        user_id: str,
        agency_id: str,
        roles: Optional[List[str]] = None,
        allowed_agencies: Optional[List[str]] = None,
        is_admin: bool = False,
        is_staff: bool = False,
        raw_token: Optional[str] = None,
    ) -> None:
        self.user_id = str(user_id).strip()
        self.agency_id = str(agency_id).strip()
        self.roles: List[str] = roles or ["viewer"]
        self.allowed_agencies: List[str] = allowed_agencies or [self.agency_id]
        self.is_admin = is_admin or ("admin" in self.roles) or ("owner" in self.roles)
        self.is_staff = is_staff or ("staff" in self.roles) or self.is_admin
        self.raw_token = raw_token

    def can_access_agency(self, target_agency_id: str) -> bool:
        """Verifies if the user is authorized to access the specified agency."""
        clean_target = str(target_agency_id).strip()
        if clean_target == self.agency_id:
            return True
        return clean_target in self.allowed_agencies

    def require_agency_access(self, target_agency_id: str) -> None:
        """Enforces that the current tenant context matches or owns target_agency_id."""
        clean_target = str(target_agency_id).strip()
        if not self.can_access_agency(clean_target):
            audit_logger.log_event(
                event_type="UNAUTHORIZED_TENANT_ACCESS_ATTEMPT",
                agency_id=self.agency_id,
                user_id=self.user_id,
                resource_id=clean_target,
                status="DENIED",
                details={"target_agency": clean_target, "allowed_agencies": self.allowed_agencies},
            )
            raise TenantAccessDeniedError(
                f"Forbidden: User '{self.user_id}' does not have active membership in agency '{clean_target}'."
            )

    def has_role(self, required_role: str) -> bool:
        """Checks if the user possesses the required role or superuser permissions."""
        if self.is_admin:
            return True
        return required_role in self.roles

    def require_role(self, required_roles: List[str]) -> None:
        """Enforces that the user has at least one of the required roles."""
        if self.is_admin:
            return
        if not any(r in self.roles for r in required_roles):
            raise TenantAccessDeniedError(
                f"Forbidden: Operation requires one of roles {required_roles}, but user has {self.roles}."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "agency_id": self.agency_id,
            "roles": self.roles,
            "allowed_agencies": self.allowed_agencies,
            "is_admin": self.is_admin,
            "is_staff": self.is_staff,
        }


def create_tenant_token(
    user_id: str,
    agency_id: str,
    roles: Optional[List[str]] = None,
    allowed_agencies: Optional[List[str]] = None,
    expires_in_hours: int = 24,
) -> str:
    """Generates a cryptographically signed HMAC-SHA256 JWT for tenant testing and session establishment."""
    now = datetime.now(timezone.utc)
    clean_agency = str(agency_id).strip()
    agencies = allowed_agencies or [clean_agency]
    if clean_agency not in agencies:
        agencies.append(clean_agency)

    payload = {
        "sub": str(user_id).strip(),
        "user_id": str(user_id).strip(),
        "agency_id": clean_agency,
        "roles": roles or ["staff"],
        "allowed_agencies": agencies,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_in_hours)).timestamp()),
    }

    return jwt.encode(payload, settings.SESSION_SECRET, algorithm=JWT_ALGORITHM)


def decode_tenant_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token against SESSION_SECRET."""
    try:
        return jwt.decode(
            token,
            settings.SESSION_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as ese:
        raise TenantAuthorizationError("Authentication token has expired.") from ese
    except jwt.InvalidTokenError as ite:
        raise TenantAuthorizationError(f"Invalid authentication token: {str(ite)}") from ite


def _extract_token_from_request(request: Request) -> Optional[str]:
    """
    Extracts authentication credentials from:
    1. Authorization: Bearer <token>
    2. Cookie: marketingos_session
    3. Cookie: ytteriq_platform_session
    4. Custom header: X-Tenant-Token
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :].strip()
        if token:
            return token

    # Check cookies
    for cookie_name in (
        settings.SESSION_COOKIE_NAME,
        settings.PLATFORM_COOKIE_NAME,
        "session_token",
        "auth_token",
    ):
        val = request.cookies.get(cookie_name)
        if val:
            return val.strip()

    # Check custom tenant header
    custom_header = request.headers.get("X-Tenant-Token")
    if custom_header:
        return custom_header.strip()

    return None


def verify_server_agency_membership(user_id: str, target_agency_id: str) -> bool:
    """
    Verifies that user has an active membership record in MongoDB for target_agency_id.
    """
    try:
        db = get_database()
        # 1. Check in 'agencies' collection
        agency_doc = db["agencies"].find_one({"agency_id": target_agency_id, "members.user_id": user_id})
        if agency_doc:
            return True

        # 2. Check in 'users' collection
        user_doc = db["users"].find_one({"user_id": user_id, "agency_ids": target_agency_id})
        if user_doc:
            return True
    except Exception as exc:
        logger.debug("Database membership check fallback: %s", exc)

    return False


async def get_current_tenant(
    request: Request,
    x_target_agency_id: Optional[str] = Header(None, alias="X-Target-Agency-ID"),
) -> TenantContext:
    """
    Centralized FastAPI dependency that resolves the verified TenantContext.
    Enforces that agency identity is NEVER taken from untrusted query/body parameters.
    """
    token = _extract_token_from_request(request)

    if not token:
        if not settings.AUTH_ENFORCE:
            # Non-enforcing development sandbox mode only
            default_agency = x_target_agency_id or "agency_default"
            return TenantContext(
                user_id="dev_user",
                agency_id=default_agency,
                roles=["admin", "staff"],
                allowed_agencies=[default_agency],
                is_admin=True,
                is_staff=True,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or session cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_tenant_token(token)
    except TenantAuthorizationError as tae:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(tae),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(claims.get("sub") or claims.get("user_id") or "anonymous").strip()
    primary_agency = str(claims.get("agency_id") or "").strip()
    allowed_agencies = [str(a).strip() for a in claims.get("allowed_agencies", [])]
    roles = claims.get("roles", ["viewer"])

    if primary_agency and primary_agency not in allowed_agencies:
        allowed_agencies.append(primary_agency)

    # Determine active agency
    active_agency = primary_agency
    if x_target_agency_id:
        requested = x_target_agency_id.strip()
        # Verify requested agency is in allowed_agencies or verified in DB
        if requested in allowed_agencies or verify_server_agency_membership(user_id, requested):
            active_agency = requested
        else:
            audit_logger.log_event(
                event_type="ILLEGAL_AGENCY_SWITCH_ATTEMPT",
                agency_id=primary_agency,
                user_id=user_id,
                resource_id=requested,
                status="DENIED",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{user_id}' does not have authorized access to agency '{requested}'.",
            )

    if not active_agency:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User token has no verified agency affiliation.",
        )

    context = TenantContext(
        user_id=user_id,
        agency_id=active_agency,
        roles=roles,
        allowed_agencies=allowed_agencies,
        raw_token=token,
    )

    # Attach tenant context to request state and contextvar for downstream tools and background tasks
    request.state.tenant = context
    current_tenant_cv.set(context)
    return context


def require_roles(allowed_roles: List[str]) -> Callable:
    """Dependency factory requiring specific roles."""
    def role_checker(tenant: TenantContext = Depends(get_current_tenant)) -> TenantContext:
        tenant.require_role(allowed_roles)
        return tenant
    return role_checker
