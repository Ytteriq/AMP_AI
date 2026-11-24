"""
backend/routes/storytelling_routes.py
FastAPI route handlers for Storytelling Agent / Scriptwriter operations.
Dispatches requests through the centralized AgentOrchestrator.
Supports both semantic /api/storytelling/... endpoints and legacy /api/scripts/... endpoints.
Enforces tenant isolation and encrypts generated scripts into 'ai_outputs'.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.orchestration.orchestrator import orchestrator
from backend.security.rate_limit_middleware import rate_limit_dependency
from backend.security.tenant_context import TenantContext, get_current_tenant
from backend.services.client_data_service import save_ai_output
from story_generation.script_schema import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
)

router = APIRouter(tags=["Storytelling Agent"])


def _handle_script_generation(
    payload: ScriptGenerationRequest,
    tenant: TenantContext,
) -> ScriptGenerationResponse:
    """Helper invoking orchestrator, persisting encrypted scripts, and returning ScriptGenerationResponse."""
    orch_response = orchestrator.dispatch_storytelling(payload)

    if not orch_response.success or not orch_response.data:
        err_detail = orch_response.error or "Failed to generate reel scripts."
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

    response_obj = ScriptGenerationResponse(
        status="success",
        brand_name=payload.brand_name,
        product_or_service=payload.product_or_service,
        duration=payload.duration,
        language=payload.language,
        content_style=payload.content_style,
        marketing_objective=payload.marketing_objective,
        scripts=scripts_list,
    )

    # Persist generated scripts encrypted in ai_outputs
    try:
        save_ai_output(
            agency_id=tenant.agency_id,
            user_id=tenant.user_id,
            feature="reel_scripts",
            payload=response_obj.model_dump(),
        )
    except Exception:
        pass

    return response_obj


# Semantic storytelling endpoints
@router.post(
    "/api/storytelling/generate",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Centralized)",
    dependencies=[Depends(rate_limit_dependency("ai_agents"))],
)
@router.post(
    "/api/storytelling",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Alias)",
    dependencies=[Depends(rate_limit_dependency("ai_agents"))],
)
# Backward-compatibility endpoint
@router.post(
    "/api/scripts/generate",
    response_model=ScriptGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate 3 distinct Reel script variations (Legacy Compatibility)",
    dependencies=[Depends(rate_limit_dependency("ai_agents"))],
)
async def generate_scripts_endpoint(
    payload: ScriptGenerationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """
    Accepts brand brief and generates 3 distinct Instagram Reel script variations
    (Hook-Focused, Storytelling, and Conversion-Focused) via Orchestrator with tenant encryption.
    """
    return _handle_script_generation(payload, tenant)
