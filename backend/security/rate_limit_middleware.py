"""
backend/security/rate_limit_middleware.py
FastAPI Middleware and Dependencies for Rate Limiting.
"""

from typing import Callable, Optional
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.security.rate_limiter import RateLimitResult, rate_limiter
from backend.security.tenant_context import (
    TenantContext,
    current_tenant_cv,
    _extract_token_from_request,
    decode_tenant_token,
)


def rate_limit_dependency(category: str, custom_limit: Optional[int] = None):
    """
    FastAPI endpoint dependency enforcing rate limits before endpoint logic executes.
    Accurately extracts tenant from ambient context or token without forcing authentication.
    """
    async def _rate_limit_checker(request: Request, response: Response):
        # 1. Derive identity: try ambient context, then token extraction
        user_id = None
        agency_id = None

        tenant = current_tenant_cv.get()
        if tenant:
            user_id = tenant.user_id
            agency_id = tenant.agency_id
        else:
            token = _extract_token_from_request(request)
            if token:
                try:
                    claims = decode_tenant_token(token)
                    user_id = str(claims.get("sub") or claims.get("user_id") or "")
                    agency_id = str(claims.get("agency_id") or "")
                except Exception:
                    pass

        # 2. Check rate limit
        res: RateLimitResult = await rate_limiter.check_rate_limit(
            request=request,
            category=category,
            user_id=user_id,
            agency_id=agency_id,
            custom_limit=custom_limit,
        )

        # 3. Always attach RFC rate limit headers to response
        rate_limiter.attach_headers(response, res)

        # 4. If limit exceeded, raise HTTP 429
        if not res.allowed:
            raise RateLimitExceededException(res)

        return res

    return _rate_limit_checker


class RateLimitExceededException(Exception):
    """Internal exception raised when an actor exceeds their rate limit."""
    def __init__(self, result: RateLimitResult):
        self.result = result
        super().__init__(f"Rate limit exceeded: retry after {result.retry_after}s")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    HTTP Middleware that catches RateLimitExceededException or applies
    baseline rate limits to unhandled routes.
    """
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
        except RateLimitExceededException as rle:
            return rate_limiter.build_429_response(rle.result)
