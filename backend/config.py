"""
backend/config.py
Centralized configuration management for AI Reel Multi-Agent System.
MongoDB Atlas and Groq API settings.
"""

import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

_env_candidates = [
    PROJECT_ROOT / ".env",
    CURRENT_DIR / ".env",
    CURRENT_DIR.parent / "story_generation" / ".env",
]

_loaded = False
for candidate in _env_candidates:
    if candidate.exists():
        load_dotenv(candidate, override=False)
        _loaded = True

if not _loaded:
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found)
    else:
        load_dotenv()


class Settings:
    """Centralized application settings."""

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Groq LLM Configuration - Analysis Agent (DO NOT CHANGE)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip()

    # Groq LLM Configuration - Storytelling Agent (Independent Client)
    STORYTELLING_API_KEY: str = os.getenv("STORYTELLING_API_KEY", "").strip()
    STORYTELLING_MODEL: str = os.getenv("STORYTELLING_MODEL", "openai/gpt-oss-20b").strip()

    # MongoDB Atlas Configuration
    MONGODB_URI: str = os.getenv("MONGODB_URI", "").strip()
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "ai_reels_analytics").strip()
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "reels").strip()

    @classmethod
    def validate_core(cls) -> None:
        """Validates that essential environment variables are defined."""
        missing = []
        if not cls.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not cls.MONGODB_URI:
            missing.append("MONGODB_URI")
        if missing:
            import logging
            logging.getLogger("ai_reel.config").warning(
                "Missing environment variables: %s. Some live services may fail.",
                ", ".join(missing),
            )


settings = Settings()
