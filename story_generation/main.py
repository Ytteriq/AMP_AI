"""
story_generation/main.py
Centralized proxy entrypoint for Agent 2: AI Reel Scriptwriter.

NOTE: The independent server on port 8001 has been deprecated and unified into
the centralized AI Reel Multi-Agent Platform on port 8000 (root main.py).
This file re-exports the centralized application for backward compatibility.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Re-export the centralized application
from main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    from backend.config import settings

    print("⚠️  Notice: Standalone story_generation server has been unified into root main.py.")
    print(f"🎬 Starting Centralized AI Reel Server on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
