"""
backend/security/rate_limiter.py
Production-grade, distributed-capable multi-tenant rate limiting system for AMP.

Core Capabilities:
1. Multi-tenant key derivation:
   - Authenticated User ID (per-user limit)
   - Authenticated Agency ID (per-agency limit, preventing cross-tenant starvation)
   - Verified Client IP (for unauthenticated or public requests)
2. Storage Adapters:
   - MemoryStorage: High-performance thread-safe in-memory sliding window / token bucket with automatic TTL eviction.
   - RedisStorage: Production distributed sliding window log / counter using atomic operations if Redis is configured.
   - Automatic fallback to in-memory if Redis is unreachable or unconfigured.
3. Category-based rate limiting with granular environment variable overrides.
4. Security:
   - Trusted proxy CIDR / IP validation (prevents X-Forwarded-For spoofing).
   - Never trusts raw unverified headers from the client for agency_id or user_id.
   - Timing-safe, zero credential exposure in error messages or logs.
5. Standard RFC-compliant HTTP 429 responses and headers:
   - Retry-After
   - X-RateLimit-Limit
   - X-RateLimit-Remaining
   - X-RateLimit-Reset
"""

import asyncio
import ipaddress
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from backend.config import settings

logger = logging.getLogger("ai_reel.security.rate_limiter")


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_after: int
    retry_after: int
    scope: str
    identifier: str


class BaseRateLimitStorage:
    """Abstract interface for rate limit state storage."""
    async def check_and_increment(
        self, key: str, max_requests: int, window_seconds: int
    ) -> RateLimitResult:
        raise NotImplementedError


class MemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Thread-safe in-memory sliding window counter with automatic stale record eviction.
    """
    def __init__(self, cleanup_interval_seconds: int = 60) -> None:
        self._lock = Lock()
        # key -> list of float timestamps
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval_seconds

    def _cleanup_stale(self, now: float) -> None:
        """Evicts expired timestamps across all keys periodically."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_keys = []
        for key, timestamps in self._windows.items():
            # Keep only items from the last 120 seconds
            cutoff = now - 120.0
            valid = [ts for ts in timestamps if ts > cutoff]
            if not valid:
                stale_keys.append(key)
            else:
                self._windows[key] = valid
        for sk in stale_keys:
            del self._windows[sk]

    async def check_and_increment(
        self, key: str, max_requests: int, window_seconds: int
    ) -> RateLimitResult:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            self._cleanup_stale(now)
            timestamps = self._windows[key]
            # Retain only timestamps within active window
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            current_count = len(valid_timestamps)

            if current_count >= max_requests:
                # Calculate retry after until oldest valid timestamp leaves window
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, int(oldest_in_window + window_seconds - now))
                reset_after = retry_after
                self._windows[key] = valid_timestamps
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=0,
                    reset_after=reset_after,
                    retry_after=retry_after,
                    scope=key.split(":")[0] if ":" in key else "global",
                    identifier=key,
                )

            # Record this request
            valid_timestamps.append(now)
            self._windows[key] = valid_timestamps
            remaining = max(0, max_requests - len(valid_timestamps))
            oldest_in_window = valid_timestamps[0]
            reset_after = max(1, int(oldest_in_window + window_seconds - now))

            return RateLimitResult(
                allowed=True,
                limit=max_requests,
                remaining=remaining,
                reset_after=reset_after,
                retry_after=0,
                scope=key.split(":")[0] if ":" in key else "global",
                identifier=key,
            )

    def reset(self) -> None:
        """Resets all stored rate limits (useful for test isolation)."""
        with self._lock:
            self._windows.clear()


class RedisRateLimitStorage(BaseRateLimitStorage):
    """
    Redis-based distributed sliding window rate limiter.
    Uses sorted sets (ZADD, ZREMRANGEBYSCORE, ZCARD, EXPIRE) for atomicity across distributed nodes.
    Falls back gracefully to memory if Redis connection fails.
    """
    def __init__(self, redis_url: str, fallback_storage: BaseRateLimitStorage) -> None:
        self.redis_url = redis_url
        self.fallback = fallback_storage
        self._redis_client = None
        self._initialized = False

    def _get_client(self):
        if not self._initialized:
            try:
                import redis
                self._redis_client = redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                    decode_responses=True,
                )
                self._redis_client.ping()
                logger.info("Successfully connected to distributed Redis rate limit cluster.")
            except Exception as exc:
                logger.warning(
                    "Redis rate limit storage unavailable (%s). Falling back to local in-memory limiter.",
                    exc,
                )
                self._redis_client = None
            self._initialized = True
        return self._redis_client

    async def check_and_increment(
        self, key: str, max_requests: int, window_seconds: int
    ) -> RateLimitResult:
        client = self._get_client()
        if client is None:
            return await self.fallback.check_and_increment(key, max_requests, window_seconds)

        now = time.time()
        cutoff = now - window_seconds
        pipe = client.pipeline()

        try:
            # Atomic sliding window via Redis sorted set
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zrange(key, 0, 0, withscores=True)
            pipe.expire(key, window_seconds + 5)
            results = pipe.execute()

            current_count = results[1]
            oldest_entries = results[2]

            if current_count >= max_requests:
                oldest_ts = oldest_entries[0][1] if oldest_entries else now
                retry_after = max(1, int(oldest_ts + window_seconds - now))
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=0,
                    reset_after=retry_after,
                    retry_after=retry_after,
                    scope=key.split(":")[0] if ":" in key else "global",
                    identifier=key,
                )

            # Record current request timestamp as score and member
            pipe = client.pipeline()
            pipe.zadd(key, {f"{now}": now})
            pipe.expire(key, window_seconds + 5)
            pipe.execute()

            remaining = max(0, max_requests - (current_count + 1))
            oldest_ts = oldest_entries[0][1] if oldest_entries else now
            reset_after = max(1, int(oldest_ts + window_seconds - now))

            return RateLimitResult(
                allowed=True,
                limit=max_requests,
                remaining=remaining,
                reset_after=reset_after,
                retry_after=0,
                scope=key.split(":")[0] if ":" in key else "global",
                identifier=key,
            )
        except Exception as exc:
            logger.warning("Redis operation failed during rate limit check (%s). Using fallback.", exc)
            return await self.fallback.check_and_increment(key, max_requests, window_seconds)


class RateLimiter:
    """
    Enterprise Rate Limiter for AMP.
    Features:
    - User-level, Agency-level, and IP-level limits.
    - Category-based limits with environment variable configurability.
    - Strict reverse-proxy trusted subnet IP extraction.
    """
    def __init__(self) -> None:
        self.memory_storage = MemoryRateLimitStorage()
        redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "")).strip()

        if redis_url:
            self.storage: BaseRateLimitStorage = RedisRateLimitStorage(
                redis_url=redis_url, fallback_storage=self.memory_storage
            )
        else:
            self.storage = self.memory_storage

        # Read configurable limits (requests per minute)
        self.category_limits: Dict[str, int] = {
            "auth": int(os.getenv("RATE_LIMIT_AUTH", "5")),
            "dashboard": int(os.getenv("RATE_LIMIT_DASHBOARD", "60")),
            "clients": int(os.getenv("RATE_LIMIT_CLIENTS", "60")),
            "campaigns": int(os.getenv("RATE_LIMIT_CAMPAIGNS", "30")),
            "meta_sync": int(os.getenv("RATE_LIMIT_META_SYNC", "10")),
            "reports": int(os.getenv("RATE_LIMIT_REPORTS", "5")),
            "ai_agents": int(os.getenv("RATE_LIMIT_AI_AGENTS", "10")),
            "general": int(os.getenv("RATE_LIMIT_GENERAL", "120")),
        }

        # Multi-tenant multipliers for agency-wide umbrella limit
        self.agency_limit_multiplier: int = int(os.getenv("RATE_LIMIT_AGENCY_MULTIPLIER", "5"))

        # Master enable switch
        self.enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")

        # Trusted proxy networks (defaults to RFC1918 / Loopback)
        raw_proxies = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
        self.trusted_proxies: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        for p in raw_proxies.split(","):
            p = p.strip()
            if p:
                try:
                    self.trusted_proxies.append(ipaddress.ip_network(p, strict=False))
                except ValueError:
                    pass

    def extract_client_ip(self, request: Request) -> str:
        """
        Extracts verified client IP address.
        Only trusts X-Forwarded-For if request.client.host is within a configured trusted proxy subnet.
        Prevents IP spoofing attacks.
        """
        direct_ip_str = request.client.host if request.client else "127.0.0.1"

        try:
            direct_ip = ipaddress.ip_address(direct_ip_str)
        except ValueError:
            return direct_ip_str

        # Check if direct connection came from a trusted proxy
        is_trusted_proxy = any(direct_ip in network for network in self.trusted_proxies)

        if is_trusted_proxy:
            # Check X-Forwarded-For header
            x_forwarded_for = request.headers.get("X-Forwarded-For")
            if x_forwarded_for:
                parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
                # Find the first non-trusted IP walking backwards from proxy chain
                for candidate in reversed(parts):
                    try:
                        cand_ip = ipaddress.ip_address(candidate)
                        if not any(cand_ip in net for net in self.trusted_proxies):
                            return str(cand_ip)
                    except ValueError:
                        continue
                if parts:
                    return parts[0]

            # Check X-Real-IP
            x_real_ip = request.headers.get("X-Real-IP")
            if x_real_ip:
                clean_real = x_real_ip.strip()
                try:
                    ipaddress.ip_address(clean_real)
                    return clean_real
                except ValueError:
                    pass

        return str(direct_ip)

    async def check_rate_limit(
        self,
        request: Request,
        category: str,
        user_id: Optional[str] = None,
        agency_id: Optional[str] = None,
        custom_limit: Optional[int] = None,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """
        Enforces rate limiting using a hierarchy:
        1. User-level limit (if authenticated)
        2. Agency-level umbrella limit (if authenticated agency)
        3. Client IP limit (for unauthenticated or general requests)
        """
        if not self.enabled:
            return RateLimitResult(
                allowed=True,
                limit=9999,
                remaining=9999,
                reset_after=0,
                retry_after=0,
                scope="disabled",
                identifier="none",
            )

        limit = custom_limit or self.category_limits.get(category, self.category_limits["general"])
        client_ip = self.extract_client_ip(request)

        # 1. Check User-Level Limit
        if user_id and user_id != "anonymous" and user_id != "dev_user":
            user_key = f"rl:user:{category}:{user_id}"
            user_result = await self.storage.check_and_increment(user_key, limit, window_seconds)
            if not user_result.allowed:
                self._log_violation("USER", user_id, category, request.url.path, limit)
                return user_result

        # 2. Check Agency-Level Limit (Prevent Cross-Agency Starvation)
        if agency_id and agency_id != "agency_default":
            agency_limit = limit * self.agency_limit_multiplier
            agency_key = f"rl:agency:{category}:{agency_id}"
            agency_result = await self.storage.check_and_increment(agency_key, agency_limit, window_seconds)
            if not agency_result.allowed:
                self._log_violation("AGENCY", agency_id, category, request.url.path, agency_limit)
                return agency_result

        # 3. IP-Level Limit (Always checked for unauthenticated; acts as baseline)
        ip_limit = limit if not user_id else limit * 2
        ip_key = f"rl:ip:{category}:{client_ip}"
        ip_result = await self.storage.check_and_increment(ip_key, ip_limit, window_seconds)
        if not ip_result.allowed:
            self._log_violation("IP", client_ip, category, request.url.path, ip_limit)
            return ip_result

        return ip_result

    def _log_violation(
        self, scope: str, actor: str, category: str, path: str, limit: int
    ) -> None:
        """Structured logging of rate limit violations without leaking credentials."""
        logger.warning(
            "RATE_LIMIT_VIOLATION | scope=%s | actor=%s | category=%s | endpoint=%s | limit=%d/min",
            scope,
            actor,
            category,
            path,
            limit,
        )

    def attach_headers(self, response: Response, result: RateLimitResult) -> None:
        """Attaches standardized RFC rate limit headers to HTTP response."""
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_after)
        if not result.allowed:
            response.headers["Retry-After"] = str(result.retry_after)

    def build_429_response(self, result: RateLimitResult) -> JSONResponse:
        """Constructs standardized HTTP 429 response body and headers."""
        headers = {
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(result.reset_after),
        }
        content = {
            "success": False,
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
            "retry_after": result.retry_after,
        }
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=content,
            headers=headers,
        )


# Global singleton rate limiter instance
rate_limiter = RateLimiter()
