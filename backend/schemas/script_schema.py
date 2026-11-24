"""
backend/schemas/script_schema.py
Re-exports Pydantic models for Agent 2: AI Reel Scriptwriter.
"""

from story_generation.script_schema import (
    SceneItem,
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptVariation,
)

__all__ = [
    "SceneItem",
    "ScriptGenerationRequest",
    "ScriptGenerationResponse",
    "ScriptVariation",
]
