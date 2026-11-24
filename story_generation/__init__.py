"""
story_generation package
AI Reel Scriptwriter (Agent 2) for Indian marketing agency campaigns.
"""

from story_generation.script_schema import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    ScriptVariation,
    SceneItem,
)
from story_generation.scriptwriter_agent import generate_reel_scripts

__all__ = [
    "ScriptGenerationRequest",
    "ScriptGenerationResponse",
    "ScriptVariation",
    "SceneItem",
    "generate_reel_scripts",
]
