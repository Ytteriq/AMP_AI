"""
backend/api/routes_scripts.py
Re-exports router from centralized storytelling_routes for backward compatibility.
"""

from backend.routes.storytelling_routes import generate_scripts_endpoint, router

__all__ = [
    "router",
    "generate_scripts_endpoint",
]
