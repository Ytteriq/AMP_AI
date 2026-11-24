"""
story_generation/scriptwriter_agent.py
LangGraph workflow for Agent 2: AI Reel Scriptwriter.
Coordinates input validation, Groq LLM script generation, and structured output synthesis.
"""

import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

try:
    from story_generation.llm_client import get_llm, invoke_storytelling_llm
except ImportError:
    try:
        from llm_client import get_llm, invoke_storytelling_llm
    except ImportError:
        from backend.llm_clients.storytelling_llm import (
            get_storytelling_llm as get_llm,
            invoke_storytelling_llm,
        )

try:
    from story_generation.prompts import (
        SCRIPTWRITER_SYSTEM_PROMPT,
        build_scriptwriter_user_prompt,
    )
    from story_generation.script_schema import ScriptVariation, SceneItem
except ImportError:
    from prompts import (
        SCRIPTWRITER_SYSTEM_PROMPT,
        build_scriptwriter_user_prompt,
    )
    from script_schema import ScriptVariation, SceneItem

logger = logging.getLogger("ai_reel.scriptwriter")


class ScriptwriterState(TypedDict):
    """LangGraph state schema for reel scriptwriter workflow."""
    brand_name: str
    product_or_service: str
    target_audience: str
    duration: int
    language: str
    content_style: str
    marketing_objective: str
    validation_error: Optional[str]
    raw_response: Optional[str]
    generated_scripts: List[Dict[str, Any]]


def validate_inputs_node(state: ScriptwriterState) -> Dict[str, Any]:
    """Validates user brief before invoking the LLM."""
    brand = state.get("brand_name", "").strip()
    product = state.get("product_or_service", "").strip()
    audience = state.get("target_audience", "").strip()
    duration = state.get("duration", 30)
    language = state.get("language", "Hinglish").strip()

    if not brand:
        return {"validation_error": "Brand or business name is required."}
    if not product:
        return {"validation_error": "Product or service description is required."}
    if not audience:
        return {"validation_error": "Target audience description is required."}
    if duration not in [15, 30, 45, 60]:
        return {"validation_error": f"Reel duration must be 15, 30, 45, or 60 seconds. Got {duration}."}

    valid_langs = ["Hindi", "Hinglish", "Marathi", "English"]
    if language.title() not in valid_langs:
        return {"validation_error": f"Language must be one of {valid_langs}. Got {language}."}

    logger.info("Scriptwriter inputs validated for brand: '%s', duration: %ds", brand, duration)
    return {"validation_error": None}


def should_generate(state: ScriptwriterState) -> Literal["generate_scripts", "__end__"]:
    """Conditional edge checking if validation passed."""
    if state.get("validation_error"):
        logger.warning("Input validation failed: %s", state["validation_error"])
        return "__end__"
    return "generate_scripts"


def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """Robust JSON extraction from LLM response (handles code fences and stray text)."""
    text = raw_text.strip()

    # 1. Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Extract content inside markdown code block if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Extract between first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = text[first_brace : last_brace + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    logger.warning("Unparseable LLM output sample: %s", text[:300])
    raise ValueError("LLM did not return a parseable JSON object.")


def generate_scripts_node(state: ScriptwriterState) -> Dict[str, Any]:
    """Invokes Groq LLM to generate exactly three distinct script variations."""
    brand = state["brand_name"].strip()
    product = state["product_or_service"].strip()
    audience = state["target_audience"].strip()
    duration = state["duration"]
    language = state["language"].strip()
    style = state.get("content_style", "Relatable").strip()
    objective = state.get("marketing_objective", "Product sales").strip()

    system_prompt = SCRIPTWRITER_SYSTEM_PROMPT.replace("{duration}", str(duration))
    user_prompt = build_scriptwriter_user_prompt(
        brand_name=brand,
        product_or_service=product,
        target_audience=audience,
        duration=duration,
        language=language,
        content_style=style,
        marketing_objective=objective,
    )

    logger.info("Invoking Storytelling Groq LLM (llama-3.3-70b-versatile) for 3 script variations (brand=%s, duration=%d, lang=%s)", brand, duration, language)
    llm = get_llm(temperature=0.7)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = invoke_storytelling_llm(llm, messages)
        raw_text = response.content if hasattr(response, "content") else str(response)
    except Exception as api_err:
        logger.error("Storytelling LLM API error: %s", api_err)
        return {
            "validation_error": f"Storytelling Agent API Error: {str(api_err)}",
            "raw_response": None,
            "generated_scripts": [],
        }

    try:
        parsed = _clean_and_parse_json(raw_text)
        scripts_list = parsed.get("scripts", [])
        if not isinstance(scripts_list, list) or len(scripts_list) == 0:
            raise ValueError("Parsed JSON does not contain a non-empty 'scripts' list.")
    except Exception as exc:
        logger.error("Failed to parse script JSON from Groq: %s", exc)
        return {
            "validation_error": f"Failed to synthesize valid script structures: {str(exc)}",
            "raw_response": raw_text,
            "generated_scripts": [],
        }

    return {
        "raw_response": raw_text,
        "generated_scripts": scripts_list,
    }


def format_output_node(state: ScriptwriterState) -> Dict[str, Any]:
    """Validates and standardizes each script variation against Pydantic schema."""
    raw_scripts = state.get("generated_scripts", [])
    duration = state.get("duration", 30)

    standardized: List[Dict[str, Any]] = []
    expected_types = ["Hook-Focused", "Storytelling", "Conversion-Focused"]

    for idx, s in enumerate(raw_scripts[:3]):
        # Ensure variation type is clear
        v_type = s.get("variation_type") or expected_types[min(idx, len(expected_types) - 1)]

        # Ensure scenes are structured
        scenes_data: List[Dict[str, Any]] = []
        raw_scenes = s.get("scenes", [])
        if isinstance(raw_scenes, list):
            for sc_idx, sc in enumerate(raw_scenes, 1):
                if isinstance(sc, dict):
                    scenes_data.append(
                        {
                            "scene_number": sc.get("scene_number", sc_idx),
                            "timestamp": sc.get("timestamp", f"Scene {sc_idx}"),
                            "visual_direction": sc.get("visual_direction", "Camera shot"),
                            "dialogue_or_vo": sc.get("dialogue_or_vo", ""),
                            "on_screen_text": sc.get("on_screen_text", ""),
                        }
                    )

        # Build clean variation dict
        variation_obj = {
            "variation_type": v_type,
            "script_title": s.get("script_title", f"{v_type} Reel"),
            "creative_concept": s.get("creative_concept", ""),
            "opening_hook": s.get("opening_hook", ""),
            "scenes": scenes_data,
            "call_to_action": s.get("call_to_action", "Check link in bio"),
            "suggested_caption": s.get("suggested_caption", ""),
            "estimated_duration_seconds": s.get("estimated_duration_seconds", duration),
        }
        standardized.append(variation_obj)

    logger.info("Successfully formatted %d script variations.", len(standardized))
    return {"generated_scripts": standardized}


def create_scriptwriter_graph():
    """Builds and compiles the simple LangGraph scriptwriter workflow."""
    workflow = StateGraph(ScriptwriterState)

    workflow.add_node("validate_inputs", validate_inputs_node)
    workflow.add_node("generate_scripts", generate_scripts_node)
    workflow.add_node("format_output", format_output_node)

    workflow.add_edge(START, "validate_inputs")
    workflow.add_conditional_edges(
        "validate_inputs",
        should_generate,
        {
            "generate_scripts": "generate_scripts",
            "__end__": END,
        },
    )
    workflow.add_edge("generate_scripts", "format_output")
    workflow.add_edge("format_output", END)

    return workflow.compile()


# Module-level compiled graph
scriptwriter_graph = create_scriptwriter_graph()


def generate_reel_scripts(
    brand_name: str,
    product_or_service: str,
    target_audience: str,
    duration: int = 30,
    language: str = "Hinglish",
    content_style: str = "Relatable",
    marketing_objective: str = "Product sales",
) -> Dict[str, Any]:
    """
    Main entrypoint to run the script generation workflow.
    Returns dictionary with 'status', 'scripts', and any 'error'.
    """
    initial_state: ScriptwriterState = {
        "brand_name": brand_name,
        "product_or_service": product_or_service,
        "target_audience": target_audience,
        "duration": duration,
        "language": language,
        "content_style": content_style,
        "marketing_objective": marketing_objective,
        "validation_error": None,
        "raw_response": None,
        "generated_scripts": [],
    }

    result = scriptwriter_graph.invoke(initial_state)

    if result.get("validation_error"):
        return {
            "status": "error",
            "error": result["validation_error"],
            "scripts": [],
        }

    return {
        "status": "success",
        "brand_name": brand_name,
        "product_or_service": product_or_service,
        "duration": duration,
        "language": language,
        "content_style": content_style,
        "marketing_objective": marketing_objective,
        "scripts": result.get("generated_scripts", []),
    }
