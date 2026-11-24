"""
backend/api/routes_chat.py
Re-exports router and models from centralized analysis_routes for backward compatibility.
"""

from backend.routes.analysis_routes import (
    ChatRequest,
    ChatResponse,
    chat_analysis_endpoint as chat_endpoint,
    get_all_reels,
    get_portfolio_summary,
    router,
)

__all__ = [
    "router",
    "ChatRequest",
    "ChatResponse",
    "chat_endpoint",
    "get_all_reels",
    "get_portfolio_summary",
]
