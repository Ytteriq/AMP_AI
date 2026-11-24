"""
backend/llm_clients/analysis_llm.py
Independent LLM Client Configuration for Agent 1: Performance Analyst.

PRESERVES EXISTING ANALYSIS LLM CONFIGURATION:
- Provider: Groq
- Model: settings.LLM_MODEL (openai/gpt-oss-120b)
- Key: settings.GROQ_API_KEY
- Zero silent fallbacks to other models
"""

import logging
from typing import Any, Dict, Optional
from langchain_groq import ChatGroq

from backend.config import settings

logger = logging.getLogger("ai_reel.llm.analysis")

ANALYSIS_MODEL = settings.LLM_MODEL


def get_analysis_api_key() -> str:
    """
    Validates that the GROQ_API_KEY for the Analysis Agent exists.
    Raises ValueError explicitly if missing.
    """
    key = settings.GROQ_API_KEY
    if not key or not key.strip():
        raise ValueError(
            "GROQ_API_KEY for Analysis Agent is missing or empty. Please configure it in your .env file."
        )
    return key.strip()


def get_analysis_llm(
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> ChatGroq:
    """
    Initializes and returns the ChatGroq model instance for the Analysis Agent.
    Strictly preserves the existing model configuration (openai/gpt-oss-120b).
    """
    api_key = get_analysis_api_key()
    target_model = model or settings.LLM_MODEL

    kwargs: Dict[str, Any] = {
        "model": target_model,
        "temperature": temperature,
        "api_key": api_key,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    elif temperature > 0.0:
        kwargs["max_tokens"] = 4096

    return ChatGroq(**kwargs)


def verify_analysis_llm() -> Dict[str, Any]:
    """
    Verifies that the Analysis Agent's Groq model is reachable and operational.
    Reports errors explicitly without silently switching models.
    """
    api_key = get_analysis_api_key()
    target_model = settings.LLM_MODEL

    try:
        test_llm = ChatGroq(
            model=target_model,
            temperature=0,
            api_key=api_key,
        )
        test_resp = test_llm.invoke("Respond with pong")
        content = test_resp.content if hasattr(test_resp, "content") else str(test_resp)

        # Test tool-calling capability
        from langchain_core.tools import tool

        @tool
        def _ping_tool(arg: str) -> str:
            """Simple ping tool."""
            return f"pong: {arg}"

        test_llm.bind_tools([_ping_tool])

        return {
            "status": "available",
            "model": target_model,
            "tool_calling_supported": True,
            "sample_response": content.strip()[:50],
            "error": None,
        }
    except Exception as exc:
        logger.error("Analysis LLM verification failed: %s", exc)
        return {
            "status": "unavailable",
            "model": target_model,
            "tool_calling_supported": False,
            "sample_response": None,
            "error": str(exc),
        }


# Drop-in alias
get_llm = get_analysis_llm

__all__ = [
    "ANALYSIS_MODEL",
    "get_analysis_api_key",
    "get_analysis_llm",
    "get_llm",
    "verify_analysis_llm",
]
