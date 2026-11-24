"""
backend/routes/report_routes.py
FastAPI router for the AI Marketing Report Generation Platform.
Exposes endpoints for dashboard metrics, client catalog, report generation,
and report export (HTML / PDF).
Enforces centralized tenant isolation, RBAC, and AES-256-GCM encrypted persistence.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, JSONResponse

from backend.orchestration.orchestrator import orchestrator
from backend.schemas.report_schemas import (
    ReportGenerationRequest,
    SaveReportRequest,
)
from backend.security.encryption_service import encryption_service
from backend.security.key_manager import key_manager
from backend.security.tenant_context import (
    TenantContext,
    get_current_tenant,
    require_roles,
)
from backend.services.client_data_service import (
    get_ai_output,
    get_all_clients,
    get_client_by_id,
    get_dashboard_summary,
    get_saved_reports,
    list_ai_outputs,
    save_report_to_db,
)
from backend.services.report_renderer import render_report_to_html

router = APIRouter(prefix="/api", tags=["Marketing Reports"])


@router.get("/dashboard/summary", summary="Retrieve agency dashboard metrics")
def dashboard_summary_endpoint(
    agency_id: Optional[str] = Query(None, description="Optional agency filter (must match authenticated tenant)"),
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Returns overview KPI cards: clients, campaigns, spend, revenue, ROAS, and recent reports."""
    if agency_id:
        tenant.require_agency_access(agency_id)
    target_agency = agency_id or tenant.agency_id
    summary = get_dashboard_summary(agency_id=target_agency)
    return summary


@router.get("/clients", summary="List clients for agency")
def list_clients_endpoint(
    agency_id: Optional[str] = Query(None, description="Optional agency filter (must match authenticated tenant)"),
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Returns list of clients belonging to the agency for client selector."""
    if agency_id:
        tenant.require_agency_access(agency_id)
    target_agency = agency_id or tenant.agency_id
    clients = get_all_clients(agency_id=target_agency)
    return {"clients": clients, "total": len(clients)}


@router.get("/clients/{client_id}", summary="Retrieve full client profile")
def client_detail_endpoint(
    client_id: str,
    agency_id: Optional[str] = Query(None, description="Optional agency filter (must match authenticated tenant)"),
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Returns comprehensive client details including brand guidelines, products, and connected platforms."""
    if agency_id:
        tenant.require_agency_access(agency_id)
    target_agency = agency_id or tenant.agency_id
    client = get_client_by_id(client_id, agency_id=target_agency)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found in authorized agency records.",
        )
    return client


@router.post(
    "/reports/generate",
    status_code=status.HTTP_200_OK,
    summary="Generate client-ready marketing report",
)
async def generate_report_endpoint(
    payload: ReportGenerationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """
    Primary report generation endpoint.
    Retrieves client data, calculates KPIs, routes to specialized agent via Orchestrator,
    encrypts sensitive AI output, and returns validated structured report JSON.
    """
    # Enforce verified tenant agency identity
    if payload.agency_id:
        tenant.require_agency_access(payload.agency_id)
    else:
        payload.agency_id = tenant.agency_id

    # Validate that requested client belongs to the authenticated agency
    client = get_client_by_id(payload.client_id, agency_id=payload.agency_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{payload.client_id}' not found or does not belong to agency '{payload.agency_id}'.",
        )

    orch_response = orchestrator.dispatch_report(payload)

    if not orch_response.success or not orch_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=orch_response.error or "Failed to generate report.",
        )

    # Automatically save generated report in encrypted format
    report_data = orch_response.data
    report_id = save_report_to_db(report_data, agency_id=payload.agency_id, user_id=tenant.user_id)
    report_data["report_id"] = report_id

    return report_data


@router.post("/reports/save", summary="Persist generated report to encrypted MongoDB")
def save_report_endpoint(
    payload: SaveReportRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Saves a generated report to the encrypted MongoDB 'ai_outputs' collection."""
    data = payload.model_dump()
    if data.get("report_payload") and isinstance(data["report_payload"], dict):
        merged = dict(data["report_payload"])
        for k in ("client_id", "report_type", "report_title", "platform", "reporting_period"):
            if k in data and data[k] and k not in merged:
                merged[k] = data[k]
        data = merged

    if "agency_id" in data and data["agency_id"]:
        tenant.require_agency_access(data["agency_id"])
    data["agency_id"] = tenant.agency_id
    data["user_id"] = tenant.user_id

    inserted_id = save_report_to_db(data, agency_id=tenant.agency_id, user_id=tenant.user_id)
    return {
        "status": "success",
        "message": "Report saved successfully to encrypted MongoDB.",
        "report_id": inserted_id,
    }


@router.get("/reports", summary="List previously generated reports")
def list_reports_endpoint(
    agency_id: Optional[str] = Query(None, description="Optional agency filter (must match authenticated tenant)"),
    client_id: Optional[str] = None,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Retrieves previously generated reports from encrypted MongoDB."""
    if agency_id:
        tenant.require_agency_access(agency_id)
    target_agency = agency_id or tenant.agency_id
    reports = get_saved_reports(agency_id=target_agency, client_id=client_id)
    return {"reports": reports, "total": len(reports)}


@router.get("/reports/{report_id}", summary="Retrieve single decrypted report")
def get_single_report_endpoint(
    report_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Retrieves and decrypts a specific saved report strictly scoped to the tenant's agency."""
    report = get_ai_output(agency_id=tenant.agency_id, record_id=report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found in authorized agency records.",
        )
    return report


@router.get("/ai/outputs", summary="List decrypted AI outputs for agency")
def list_agency_ai_outputs_endpoint(
    feature: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = 20,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Lists and decrypts all AI outputs belonging strictly to the authenticated agency."""
    outputs = list_ai_outputs(
        agency_id=tenant.agency_id,
        feature=feature,
        client_id=client_id,
        limit=limit,
    )
    return {"outputs": outputs, "total": len(outputs)}


@router.get("/ai/outputs/{output_id}", summary="Retrieve single decrypted AI output")
def get_single_ai_output_endpoint(
    output_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Retrieves and decrypts a specific AI output belonging strictly to the authenticated agency."""
    output = get_ai_output(agency_id=tenant.agency_id, record_id=output_id)
    if not output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI output '{output_id}' not found in authorized agency records.",
        )
    return output


@router.post("/security/key/rotate", summary="Rotate agency encryption key")
def rotate_key_endpoint(
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Rotates the agency's data encryption key (DEK) to an incremented version."""
    tenant.require_role(["owner", "admin"])
    rotated = key_manager.rotate_agency_key(tenant.agency_id)
    return {
        "status": "success",
        "message": f"Successfully rotated encryption key for agency '{tenant.agency_id}'.",
        "key_metadata": rotated,
    }


@router.post("/reports/export/html", summary="Export report as standalone HTML")
def export_report_html_endpoint(
    report_payload: Dict[str, Any],
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Renders structured report JSON as standalone, professional HTML."""
    html_content = render_report_to_html(report_payload)
    return HTMLResponse(content=html_content, status_code=200)


@router.post("/reports/export/pdf", summary="Export report formatted for PDF printing")
def export_report_pdf_endpoint(
    report_payload: Dict[str, Any],
    tenant: TenantContext = Depends(get_current_tenant),
):
    """
    Returns printer-optimized HTML with clean page breaks and print stylesheets.
    Browser / print-drivers directly save this as a high-fidelity PDF.
    """
    html_content = render_report_to_html(report_payload)
    client_name = report_payload.get("client_info", {}).get("client_name", "Client").replace(" ", "_")
    report_title = report_payload.get("report_title", "Report").replace(" ", "_")

    headers = {
        "Content-Disposition": f'inline; filename="{client_name}_{report_title}.html"'
    }
    return Response(content=html_content, media_type="text/html", headers=headers)
