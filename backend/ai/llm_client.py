"""
backend/ai/llm_client.py
Analysis Agent LLM Client Interface (openai/gpt-oss-120b).
Preserves full backward compatibility for existing imports across the platform:
- DEFAULT_MODEL
- get_groq_api_key()
- get_llm()
- verify_llm_availability()
"""

from typing import Any, Dict, Optional
from langchain_groq import ChatGroq

from backend.config import settings
from backend.llm_clients.analysis_llm import (
    ANALYSIS_MODEL as DEFAULT_MODEL,
    get_analysis_api_key as get_groq_api_key,
    get_analysis_llm as get_llm,
    verify_analysis_llm as verify_llm_availability,
)

__all__ = [
    "DEFAULT_MODEL",
    "get_groq_api_key",
    "get_llm",
    "verify_llm_availability",
]
