"""
story_generation/routes_scripts.py
FastAPI router for generating Instagram Reel scripts.
Defines POST /api/scripts/generate with input validation and structured responses.
"""

from fastapi import APIRouter, HTTPException, status

try:
    from story_generation.script_schema import (
        ScriptGenerationRequest,
        ScriptGenerationResponse,
    )
    from story_generation.scriptwriter_agent import generate_reel_scripts
except ImportError:
    from script_schema import (
        ScriptGenerationRequest,
        ScriptGenerationResponse,
    )
    from scriptwriter_agent import generate_reel_scripts

router = APIRouter(prefix="/api/scripts", tags=["Reel Scriptwriter"])


@router.post(
    "/generate",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Instagram Reel script variations",
)
async def generate_scripts_endpoint(payload: ScriptGenerationRequest):
    """
    Accepts brand brief and generates three distinct Instagram Reel script variations
    (Hook-Focused, Storytelling, and Conversion-Focused) tailored for Indian audiences.
    """
    try:
        result = generate_reel_scripts(
            brand_name=payload.brand_name,
            product_or_service=payload.product_or_service,
            target_audience=payload.target_audience,
            duration=payload.duration,
            language=payload.language,
            content_style=payload.content_style,
            marketing_objective=payload.marketing_objective,
        )

        if isinstance(result, dict):
            status_val = result.get("status")
            scripts_list = result.get("scripts", [])
            error_msg = result.get("error", "Failed to generate script variations.")
        else:
            status_val = getattr(result, "status", "success")
            scripts_list = getattr(result, "scripts", [])
            error_msg = getattr(result, "error", "Failed to generate script variations.")

        if status_val == "error" or not scripts_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
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

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating reel scripts: {str(exc)}",
        )
