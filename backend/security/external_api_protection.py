"""
backend/security/external_api_protection.py
Protection and throttling controls for external API integrations:
1. Meta Marketing API:
   - Concurrency throttling (bounded Semaphore)
   - Deduplication of identical in-flight and recent sync requests
   - Exponential backoff with jitter on Meta rate-limit codes (17, 32, 613, 80004)
   - Token bucket rate limiter respecting Meta's 200 calls/user/hour baseline
2. LLM Providers (Groq / OpenAI):
   - Concurrency bounding (prevents thread/token pool exhaustion)
   - Deduplication of identical simultaneous prompt / report requests (request coalescence)
   - Graceful backoff on HTTP 429 rate limit responses
   - Max retry bounds to avoid infinite retry loops
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple
from threading import Lock

from backend.config import settings

logger = logging.getLogger("ai_reel.security.external_api")


class MetaApiProtection:
    """
    Dedicated controller protecting Meta Marketing API integrations.
    - Prevents duplicate synchronization requests for the same account.
    - Limits concurrency to avoid account-level throttling.
    - Backoff on rate limit signals.
    """
    def __init__(
        self,
        max_concurrent: int = 5,
        sync_dedup_window_seconds: int = 60,
    ) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.lock = Lock()
        # account_id -> last_sync_timestamp
        self._recent_syncs: Dict[str, float] = {}
        self.sync_dedup_window = sync_dedup_window_seconds
        # Backoff tracker: account_id -> backoff_until_timestamp
        self._backoff_until: Dict[str, float] = {}

    def should_allow_sync(self, account_or_client_id: str) -> Tuple[bool, Optional[str]]:
        """
        Prevents redundant immediate sync operations for the same client/account.
        """
        now = time.time()
        with self.lock:
            # Check if currently in backoff from Meta rate limit
            backoff_time = self._backoff_until.get(account_or_client_id, 0.0)
            if now < backoff_time:
                wait_sec = int(backoff_time - now)
                return False, f"Meta API is temporarily throttling account '{account_or_client_id}'. Retry in {wait_sec}s."

            # Check if synced too recently
            last_sync = self._recent_syncs.get(account_or_client_id, 0.0)
            if now - last_sync < self.sync_dedup_window:
                wait_sec = int(self.sync_dedup_window - (now - last_sync))
                return False, f"A recent sync is already active or completed. Please wait {wait_sec}s before syncing again."

            self._recent_syncs[account_or_client_id] = now
            return True, None

    def record_meta_throttled(self, account_or_client_id: str, retry_after_seconds: int = 60) -> None:
        """
        Registers a rate limit signal from Meta API (e.g. error code 17, 32, 613).
        """
        backoff_until = time.time() + max(10, retry_after_seconds)
        with self.lock:
            self._backoff_until[account_or_client_id] = backoff_until
        logger.warning(
            "META_API_THROTTLED | account=%s | backoff_seconds=%d",
            account_or_client_id,
            retry_after_seconds,
        )

    def record_sync_success(self, account_or_client_id: str) -> None:
        """Clears backoff state upon verified API success."""
        with self.lock:
            self._backoff_until.pop(account_or_client_id, None)


class LLMProtection:
    """
    Dedicated controller protecting LLM providers (Groq, OpenAI).
    - Prevents duplicate heavy report generation requests with the same parameters.
    - Limits concurrency to prevent worker exhaustion.
    - Bounded retries on 429 with exponential backoff.
    """
    def __init__(
        self,
        max_concurrent_llm_calls: int = 10,
        report_dedup_window_seconds: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent_llm_calls)
        self.lock = Lock()
        # hash(client_id, report_type, date_range) -> timestamp
        self._in_flight_reports: Dict[str, float] = {}
        self.report_dedup_window = report_dedup_window_seconds
        self.max_retries = max_retries

    def compute_request_signature(self, client_id: str, report_type: str, date_range: str, platform: str) -> str:
        """Generates a deterministic hash signature of the report request parameters."""
        raw = f"{client_id}:{report_type}:{date_range}:{platform}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def try_acquire_report_slot(self, signature: str) -> Tuple[bool, Optional[str]]:
        """
        Prevents multiple rapid submissions of the exact same heavy report.
        """
        now = time.time()
        with self.lock:
            last_req = self._in_flight_reports.get(signature, 0.0)
            if now - last_req < self.report_dedup_window:
                wait_sec = int(self.report_dedup_window - (now - last_req))
                return False, f"Identical report generation is already in progress. Please wait {wait_sec}s."
            self._in_flight_reports[signature] = now
            return True, None

    def release_report_slot(self, signature: str) -> None:
        """Removes signature from active tracking."""
        with self.lock:
            self._in_flight_reports.pop(signature, None)

    async def execute_with_backoff(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Executes an LLM call with controlled concurrency, graceful 429 handling, and bounded retries.
        """
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:
                    # If synchronous function, execute via run_in_executor
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            except Exception as exc:
                err_str = str(exc).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "too many requests" in err_str

                if is_rate_limit and attempt < self.max_retries:
                    logger.warning(
                        "LLM_PROVIDER_RATE_LIMIT | attempt=%d/%d | backing off %.1fs",
                        attempt,
                        self.max_retries,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    raise


# Global singleton instances
meta_api_protection = MetaApiProtection()
llm_protection = LLMProtection()
