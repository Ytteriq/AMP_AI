"""
backend/routes/report_routes.py
FastAPI router for the AI Marketing Report Generation Platform.
Exposes endpoints for dashboard metrics, client catalog, report generation,
and report export (HTML / PDF).
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse, JSONResponse

from backend.orchestration.orchestrator import orchestrator
from backend.schemas.report_schemas import (
    ReportGenerationRequest,
    SaveReportRequest,
)
from backend.services.client_data_service import (
    get_all_clients,
    get_client_by_id,
    get_dashboard_summary,
    get_saved_reports,
    save_report_to_db,
)
from backend.services.report_renderer import render_report_to_html

router = APIRouter(prefix="/api", tags=["Marketing Reports"])


@router.get("/dashboard/summary", summary="Retrieve agency dashboard metrics")
def dashboard_summary_endpoint(agency_id: str = "agency_default"):
    """Returns overview KPI cards: clients, campaigns, spend, revenue, ROAS, and recent reports."""
    summary = get_dashboard_summary(agency_id=agency_id)
    return summary


@router.get("/clients", summary="List clients for agency")
def list_clients_endpoint(agency_id: str = "agency_default"):
    """Returns list of clients belonging to the agency for client selector."""
    clients = get_all_clients(agency_id=agency_id)
    return {"clients": clients, "total": len(clients)}


@router.get("/clients/{client_id}", summary="Retrieve full client profile")
def client_detail_endpoint(client_id: str, agency_id: str = "agency_default"):
    """Returns comprehensive client details including brand guidelines, products, and connected platforms."""
    client = get_client_by_id(client_id, agency_id=agency_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found.",
        )
    return client


@router.post(
    "/reports/generate",
    status_code=status.HTTP_200_OK,
    summary="Generate client-ready marketing report",
)
async def generate_report_endpoint(payload: ReportGenerationRequest):
    """
    Primary report generation endpoint.
    Retrieves client data, calculates KPIs, routes to specialized agent via Orchestrator,
    and returns validated structured report JSON.
    """
    orch_response = orchestrator.dispatch_report(payload)

    if not orch_response.success or not orch_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=orch_response.error or "Failed to generate report.",
        )

    return orch_response.data


@router.post("/reports/save", summary="Persist generated report to MongoDB")
def save_report_endpoint(payload: SaveReportRequest):
    """Saves a generated report to the MongoDB 'reports' collection."""
    inserted_id = save_report_to_db(payload.model_dump())
    return {
        "status": "success",
        "message": "Report saved successfully to MongoDB.",
        "report_id": inserted_id,
    }


@router.get("/reports", summary="List previously generated reports")
def list_reports_endpoint(agency_id: str = "agency_default", client_id: Optional[str] = None):
    """Retrieves previously generated reports from MongoDB."""
    reports = get_saved_reports(agency_id=agency_id, client_id=client_id)
    return {"reports": reports, "total": len(reports)}


@router.post("/reports/export/html", summary="Export report as standalone HTML")
def export_report_html_endpoint(report_payload: Dict[str, Any]):
    """Renders structured report JSON as standalone, professional HTML."""
    html_content = render_report_to_html(report_payload)
    return HTMLResponse(content=html_content, status_code=200)


@router.post("/reports/export/pdf", summary="Export report formatted for PDF printing")
def export_report_pdf_endpoint(report_payload: Dict[str, Any]):
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
