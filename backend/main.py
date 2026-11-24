"""
backend/main.py
Centralized proxy entrypoint for AI Reel Multi-Agent Platform.
Re-exports the unified FastAPI application from backend.app.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import app
from backend.config import settings

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host=settings.HOST, port=settings.PORT, reload=True)
