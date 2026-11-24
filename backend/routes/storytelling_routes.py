"""
backend/routes/storytelling_routes.py
FastAPI route handlers for Storytelling Agent / Scriptwriter operations.
Dispatches requests through the centralized AgentOrchestrator.
Supports both semantic /api/storytelling/... endpoints and legacy /api/scripts/... endpoints.
"""

from fastapi import APIRouter, HTTPException, status

from backend.orchestration.orchestrator import orchestrator
from story_generation.script_schema import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
)

router = APIRouter(tags=["Storytelling Agent"])


def _handle_script_generation(payload: ScriptGenerationRequest) -> ScriptGenerationResponse:
    """Helper invoking orchestrator and converting result to ScriptGenerationResponse."""
    orch_response = orchestrator.dispatch_storytelling(payload)

    if not orch_response.success or not orch_response.data:
        err_detail = orch_response.error or "Failed to generate reel scripts."
        # If it was a validation error from the agent, return 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_detail,
        )

    data = orch_response.data
    scripts_list = data.get("scripts", [])
    if not scripts_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=data.get("error", "Failed to generate script variations."),
        )

    return ScriptGenerationResponse(
        status="success",
        brand_name=payload.brand_name,
        product_or_service=payload.product_or_service,
        duration=payload.duration,
        language=payload.language,
        content_style=payload.content_style,
        marketing_objective=payload.marketing_objective,
        scripts=scripts_list,
    )


# Semantic storytelling endpoints
@router.post(
    "/api/storytelling/generate",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Centralized)",
)
@router.post(
    "/api/storytelling",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Alias)",
)
# Backward-compatibility endpoint
@router.post(
    "/api/scripts/generate",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Legacy Compatibility)",
)
async def generate_scripts_endpoint(payload: ScriptGenerationRequest):
    """
    Accepts brand brief and generates 3 distinct Instagram Reel script variations
    (Hook-Focused, Storytelling, and Conversion-Focused) via Orchestrator.
    """
    return _handle_script_generation(payload)
