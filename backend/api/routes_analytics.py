"""
api/routes_analytics.py
Analytics and chat routes alias, re-exporting from routes_chat for backwards and structural compatibility.
"""

from backend.api.routes_chat import (
    router,
    ChatRequest,
    EvidenceItem,
    ChatResponse,
    HealthResponse,
    chat_endpoint,
    health_check,
)

__all__ = [
    "router",
    "ChatRequest",
    "EvidenceItem",
    "ChatResponse",
    "HealthResponse",
    "chat_endpoint",
    "health_check",
]
