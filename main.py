"""
main.py
Centralized FastAPI application entrypoint for AI Reel Multi-Agent Platform.

Coordinates:
- Agent 1: AI Reel Performance Analyst (Analytics, MongoDB, ChromaDB, Mathematical Metrics)
- Agent 2: AI Reel Scriptwriter (Creative Hinglish/Hindi Storytelling & Script Generation)
Through a centralized Orchestration Layer on port 8000.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import app
from backend.config import settings

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    print(f"🎬 Starting Centralized AI Reel Server on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
