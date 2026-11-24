"""
story_generation/script_schema.py
Pydantic schemas for the AI Reel Scriptwriter (Agent 2).
Validates user inputs, duration, language, style, and marketing objectives.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class SceneItem(BaseModel):
    """Individual scene within an Instagram Reel script."""
    scene_number: int = Field(..., description="Sequential scene index starting from 1")
    timestamp: str = Field(..., description="Scene timestamp, e.g., '0:00 - 0:03' or '0:03 - 0:08'")
    visual_direction: str = Field(..., description="Camera framing, visual action, actor movements, scene setting")
    dialogue_or_vo: str = Field(..., description="Spoken dialogue, character line, or voiceover in requested language")
    on_screen_text: str = Field(..., description="Text overlays, animated captions, or stickers on screen")


class ScriptVariation(BaseModel):
    """Complete script variation for a specific creative angle."""
    variation_type: str = Field(
        ...,
        description="Type of variation: 'Hook-Focused', 'Storytelling', or 'Conversion-Focused'",
    )
    script_title: str = Field(..., description="Creative, catchy title for the Reel")
    creative_concept: str = Field(..., description="High-level concept, creative hook, and angle explanation")
    opening_hook: str = Field(..., description="Attention-grabbing opening hook for the first 3 seconds")
    scenes: List[SceneItem] = Field(..., description="Scene-by-scene breakdown fitting requested duration")
    call_to_action: str = Field(..., description="Clear call to action aligned with the marketing objective")
    suggested_caption: str = Field(..., description="Ready-to-post caption with relevant Indian marketing hashtags")
    estimated_duration_seconds: int = Field(..., description="Estimated total duration in seconds")


class ScriptGenerationRequest(BaseModel):
    """User input form payload for generating 3 Reel scripts."""
    brand_name: str = Field(
        ...,
        min_length=1,
        description="Business or brand name",
        examples=["ChaiPoint Express"],
    )
    product_or_service: str = Field(
        ...,
        min_length=1,
        description="Product or service being promoted",
        examples=["Instant Ginger Cardamom Tea Premix"],
    )
    target_audience: str = Field(
        ...,
        min_length=1,
        description="Demographics, psychographics, and target audience persona",
        examples=["WFH professionals and college students in Tier 1/2 cities"],
    )
    duration: int = Field(
        default=30,
        description="Reel duration in seconds: 15, 30, 45, or 60",
        examples=[30],
    )
    language: str = Field(
        default="Hinglish",
        description="Language: Hindi, Hinglish, Marathi, or English",
        examples=["Hinglish"],
    )
    content_style: str = Field(
        default="Relatable",
        description="Style: Funny, Emotional, Storytelling, Relatable, Promotional, Educational, Cinematic, Trend-inspired",
        examples=["Relatable"],
    )
    marketing_objective: str = Field(
        default="Product sales",
        description="Objective: Brand awareness, Engagement, Product sales, Lead generation, Website visits",
        examples=["Product sales"],
    )

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        allowed = [15, 30, 45, 60]
        if v not in allowed:
            raise ValueError(f"Duration must be one of {allowed} seconds. Received: {v}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        clean = v.strip().title()
        allowed = ["Hindi", "Hinglish", "Marathi", "English"]
        for opt in allowed:
            if clean.lower() == opt.lower():
                return opt
        raise ValueError(f"Language must be one of {allowed}. Received: '{v}'")

    @field_validator("content_style")
    @classmethod
    def validate_content_style(cls, v: str) -> str:
        clean = v.strip()
        allowed = [
            "Funny",
            "Emotional",
            "Storytelling",
            "Relatable",
            "Promotional",
            "Educational",
            "Cinematic",
            "Trend-inspired",
        ]
        for opt in allowed:
            if clean.lower() == opt.lower():
                return opt
        raise ValueError(
            f"Invalid content style '{v}'. Supported styles: {', '.join(allowed)}"
        )

    @field_validator("marketing_objective")
    @classmethod
    def validate_marketing_objective(cls, v: str) -> str:
        clean = v.strip()
        allowed = [
            "Brand awareness",
            "Engagement",
            "Product sales",
            "Lead generation",
            "Website visits",
        ]
        for opt in allowed:
            if clean.lower() == opt.lower():
                return opt
        raise ValueError(
            f"Invalid marketing objective '{v}'. Supported objectives: {', '.join(allowed)}"
        )


class ScriptGenerationResponse(BaseModel):
    """API response model containing exactly three distinct script variations."""
    status: str = "success"
    brand_name: str
    product_or_service: str
    duration: int
    language: str
    content_style: str
    marketing_objective: str
    scripts: List[ScriptVariation] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three distinct script variations (Hook-Focused, Storytelling, Conversion-Focused)",
    )
