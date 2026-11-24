"""
story_generation/llm_client.py
Configures and initializes the Storytelling Agent's dedicated Groq LLM client.
Uses Groq model: llama-3.3-70b-versatile with STORYTELLING_API_KEY.
Does NOT share the Analysis Agent's model configuration.
"""

from typing import Any, Dict, List, Optional
from langchain_groq import ChatGroq

from backend.llm_clients.storytelling_llm import (
    STORYTELLING_MODEL as DEFAULT_MODEL,
    get_storytelling_api_key as get_groq_api_key,
    get_storytelling_llm,
    invoke_storytelling_llm,
    verify_storytelling_llm as verify_llm_availability,
)


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = 4096,
    request_timeout: float = 60.0,
    max_retries: int = 2,
) -> ChatGroq:
    """
    Initializes and returns the Storytelling ChatGroq model instance.
    Model: llama-3.3-70b-versatile
    API Key: STORYTELLING_API_KEY
    """
    return get_storytelling_llm(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=request_timeout,
        max_retries=max_retries,
    )


__all__ = [
    "DEFAULT_MODEL",
    "get_groq_api_key",
    "get_llm",
    "get_storytelling_llm",
    "invoke_storytelling_llm",
    "verify_llm_availability",
]
