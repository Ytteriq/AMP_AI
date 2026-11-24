"""
backend/llm_clients/storytelling_llm.py
Independent LLM Client Configuration for Agent 2: Storytelling & Scriptwriter Agent.

STORYTELLING LLM CONFIGURATION:
- Provider: Groq
- Model: settings.STORYTELLING_MODEL (llama-3.3-70b-versatile)
- Key: settings.STORYTELLING_API_KEY
- Zero silent fallback to Analysis Agent's LLM or model
"""

import logging
import os
from typing import Any, Dict, List, Optional
from langchain_groq import ChatGroq

from backend.config import settings

logger = logging.getLogger("ai_reel.llm.storytelling")

STORYTELLING_MODEL = settings.STORYTELLING_MODEL or "openai/gpt-oss-20b"


def mask_api_key(key: Optional[str]) -> str:
    """Safely masks API key for logging without exposing secret credentials."""
    if not key:
        return "<MISSING>"
    stripped = key.strip()
    if len(stripped) <= 8:
        return "***"
    return f"{stripped[:6]}...{stripped[-4:]}"


def get_storytelling_api_key() -> str:
    """
    Validates that the STORYTELLING_API_KEY for the Storytelling Agent exists.
    CRITICAL RULE: Never silently falls back to the Analysis Agent's GROQ_API_KEY.
    """
    key = settings.STORYTELLING_API_KEY or os.getenv("STORYTELLING_API_KEY", "")
    if not key or not key.strip():
        raise ValueError(
            "STORYTELLING_API_KEY is missing or empty. "
            "Please configure STORYTELLING_API_KEY in your .env file. "
            "Storytelling Agent requires its own dedicated Groq API credentials."
        )
    return key.strip()


def get_storytelling_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = 4096,
    request_timeout: float = 60.0,
    max_retries: int = 2,
) -> ChatGroq:
    """
    Initializes and returns an independent ChatGroq model instance for the Storytelling Agent.
    Strictly configured for creative scriptwriting and storytelling:
    - Target Model: llama-3.3-70b-versatile
    - Dedicated API Key: STORYTELLING_API_KEY
    - Default Temperature: 0.7 for varied hooks and natural dialogue
    - Explicit timeout and retry boundaries
    """
    api_key = get_storytelling_api_key()
    target_model = model or settings.STORYTELLING_MODEL or "openai/gpt-oss-20b"

    masked = mask_api_key(api_key)
    logger.info(
        "Initializing Storytelling LLM client with model '%s' (key: %s, temp: %.2f)",
        target_model,
        masked,
        temperature,
    )

    return ChatGroq(
        model=target_model,
        temperature=temperature,
        api_key=api_key,
        max_tokens=max_tokens,
        request_timeout=request_timeout,
        max_retries=max_retries,
    )


def invoke_storytelling_llm(llm: ChatGroq, messages: List[Any]) -> Any:
    """
    Executes an LLM invocation with strict error categorization:
    - Authentication errors (invalid/expired key)
    - Rate limit errors
    - Timeout errors
    - Connection errors
    Ensures safe error logging without leaking API keys.
    """
    try:
        from groq import (
            AuthenticationError,
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
        )
    except ImportError:
        # Fallback to standard Exception handling if groq sub-module exceptions differ
        AuthenticationError = PermissionError  # type: ignore
        RateLimitError = RuntimeError  # type: ignore
        APITimeoutError = TimeoutError  # type: ignore
        APIConnectionError = ConnectionError  # type: ignore

    try:
        return llm.invoke(messages)
    except AuthenticationError as auth_err:
        logger.error("Storytelling LLM Authentication Error: %s", auth_err)
        raise PermissionError(
            "Storytelling Agent Authentication Failed: Invalid or unauthorized STORYTELLING_API_KEY. "
            "Please check your configured Groq API key."
        ) from auth_err
    except RateLimitError as rl_err:
        logger.error("Storytelling LLM Rate Limit Reached: %s", rl_err)
        raise RuntimeError(
            f"Storytelling Agent Rate Limit Exceeded: Groq API limit reached for {settings.STORYTELLING_MODEL}. "
            "Please wait a few moments before retrying."
        ) from rl_err
    except APITimeoutError as to_err:
        logger.error("Storytelling LLM Request Timeout: %s", to_err)
        raise TimeoutError(
            "Storytelling Agent Request Timeout: Groq API did not respond within the configured timeout window."
        ) from to_err
    except APIConnectionError as conn_err:
        logger.error("Storytelling LLM Connection Error: %s", conn_err)
        raise ConnectionError(
            "Storytelling Agent Connection Error: Unable to reach Groq API endpoint. Check your network connection."
        ) from conn_err
    except Exception as exc:
        err_str = str(exc)
        # Check if error message mentions auth or rate limit
        if "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower():
            logger.error("Storytelling LLM unauthorized error: %s", err_str)
            raise PermissionError(
                "Storytelling Agent Authentication Failed: Invalid STORYTELLING_API_KEY."
            ) from exc
        if "429" in err_str or "rate limit" in err_str.lower():
            logger.error("Storytelling LLM rate limit error: %s", err_str)
            raise RuntimeError(
                f"Storytelling Agent Rate Limit Exceeded for model {settings.STORYTELLING_MODEL}."
            ) from exc
        logger.error("Storytelling LLM invocation error: %s", exc)
        raise


def verify_storytelling_llm() -> Dict[str, Any]:
    """
    Verifies that the Storytelling Agent's Groq model
    is reachable and authenticates with STORYTELLING_API_KEY.
    """
    try:
        api_key = get_storytelling_api_key()
    except Exception as exc:
        return {
            "status": "unavailable",
            "model": STORYTELLING_MODEL,
            "error": str(exc),
            "authenticated": False,
        }

    target_model = settings.STORYTELLING_MODEL or "openai/gpt-oss-20b"
    masked = mask_api_key(api_key)

    try:
        test_llm = ChatGroq(
            model=target_model,
            temperature=0.1,
            api_key=api_key,
            request_timeout=30.0,
            max_retries=1,
        )
        test_resp = invoke_storytelling_llm(test_llm, ["Respond with pong"])
        content = test_resp.content if hasattr(test_resp, "content") else str(test_resp)

        return {
            "status": "available",
            "model": target_model,
            "api_key_masked": masked,
            "authenticated": True,
            "sample_response": content.strip()[:50],
            "error": None,
        }
    except Exception as exc:
        logger.error("Storytelling LLM verification failed: %s", exc)
        return {
            "status": "unavailable",
            "model": target_model,
            "api_key_masked": masked,
            "authenticated": False,
            "sample_response": None,
            "error": str(exc),
        }


# Drop-in alias
get_llm = get_storytelling_llm

__all__ = [
    "STORYTELLING_MODEL",
    "mask_api_key",
    "get_storytelling_api_key",
    "get_storytelling_llm",
    "get_llm",
    "invoke_storytelling_llm",
    "verify_storytelling_llm",
]
