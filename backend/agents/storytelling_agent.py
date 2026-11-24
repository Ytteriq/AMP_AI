"""
backend/agents/storytelling_agent.py
Modular interface for Agent 2: AI Reel Scriptwriter / Storytelling Agent.
Generates creative, high-converting Instagram Reel scripts for Indian brands.
"""

import logging
from typing import Any, Dict, Optional, Union

from story_generation.script_schema import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
)
from story_generation.scriptwriter_agent import (
    create_scriptwriter_graph,
    generate_reel_scripts,
    scriptwriter_graph,
)

logger = logging.getLogger("ai_reel.agents.storytelling")


def run_storytelling_agent(
    payload: Union[ScriptGenerationRequest, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes the Storytelling Agent workflow to generate 3 distinct Reel script variations.
    Accepts either a validated ScriptGenerationRequest Pydantic object or a raw dictionary.
    """
    if isinstance(payload, dict):
        req = ScriptGenerationRequest(**payload)
    else:
        req = payload

    logger.info(
        "Executing Storytelling Agent for brand: '%s', duration: %ds, lang: %s",
        req.brand_name,
        req.duration,
        req.language,
    )

    from story_generation import routes_scripts as sg_routes

    gen_func = getattr(sg_routes, "generate_reel_scripts", generate_reel_scripts)
    result = gen_func(
        brand_name=req.brand_name,
        product_or_service=req.product_or_service,
        target_audience=req.target_audience,
        duration=req.duration,
        language=req.language,
        content_style=req.content_style,
        marketing_objective=req.marketing_objective,
    )

    if isinstance(result, dict):
        status_val = result.get("status", "success")
        scripts_list = result.get("scripts", [])
        error_msg = result.get("error", "Failed to generate script variations.")
    else:
        status_val = getattr(result, "status", "success")
        scripts_list = getattr(result, "scripts", [])
        error_msg = getattr(result, "error", "Failed to generate script variations.")

    if status_val == "error" or not scripts_list:
        raise ValueError(error_msg)

    return {
        "status": "success",
        "brand_name": req.brand_name,
        "product_or_service": req.product_or_service,
        "duration": req.duration,
        "language": req.language,
        "content_style": req.content_style,
        "marketing_objective": req.marketing_objective,
        "scripts": scripts_list,
    }


__all__ = [
    "run_storytelling_agent",
    "generate_reel_scripts",
    "create_scriptwriter_graph",
    "scriptwriter_graph",
]
