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
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "ytteriq_amp_ai").strip()
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "reels").strip()

    # AWS KMS Envelope Encryption Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1").strip()
    AWS_KMS_KEY_ID: str = os.getenv("AWS_KMS_KEY_ID", "").strip()
    AWS_KMS_ENDPOINT_URL: str = os.getenv("AWS_KMS_ENDPOINT_URL", "").strip()
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    KMS_MOCK_FALLBACK: bool = os.getenv("KMS_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes")
    DEK_CACHE_TTL_SECONDS: int = int(os.getenv("DEK_CACHE_TTL_SECONDS", "300"))

    # Authentication & Session Configuration
    SESSION_SECRET: str = os.getenv(
        "SESSION_SECRET",
        os.getenv("JWT_SECRET", "ytteriq-amp-super-secure-production-session-secret-key-at-least-32-chars"),
    ).strip()
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "marketingos_session").strip()
    PLATFORM_COOKIE_NAME: str = os.getenv("PLATFORM_COOKIE_NAME", "ytteriq_platform_session").strip()
    AUTH_ENFORCE: bool = os.getenv("AUTH_ENFORCE", "true").lower() in ("true", "1", "yes")

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
