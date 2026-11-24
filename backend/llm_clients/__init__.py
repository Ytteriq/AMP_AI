"""
backend/llm_clients/__init__.py
Centralized package for independent LLM clients:
- Analysis LLM Client (openai/gpt-oss-120b)
- Storytelling LLM Client (llama-3.3-70b-versatile)
"""

from backend.llm_clients.analysis_llm import (
    ANALYSIS_MODEL,
    get_analysis_api_key,
    get_analysis_llm,
    verify_analysis_llm,
)
from backend.llm_clients.storytelling_llm import (
    STORYTELLING_MODEL,
    get_storytelling_api_key,
    get_storytelling_llm,
    verify_storytelling_llm,
    invoke_storytelling_llm,
)

__all__ = [
    "ANALYSIS_MODEL",
    "get_analysis_api_key",
    "get_analysis_llm",
    "verify_analysis_llm",
    "STORYTELLING_MODEL",
    "get_storytelling_api_key",
    "get_storytelling_llm",
    "verify_storytelling_llm",
    "invoke_storytelling_llm",
]
