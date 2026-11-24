"""backend/routes package."""
from backend.routes.analysis_routes import router as analysis_router
from backend.routes.storytelling_routes import router as storytelling_router
from backend.routes.report_routes import router as report_router

__all__ = [
    "analysis_router",
    "storytelling_router",
    "report_router",
]
