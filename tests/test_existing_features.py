"""
tests/test_existing_features.py
Verifies that all existing AMP AI features, routers, health checks,
and orchestrator dispatches continue functioning with tenant isolation enabled.
"""

from fastapi.testclient import TestClient
import pytest


def test_health_checks(client: TestClient):
    # System health check
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "active_agents" in data

    # Database health check
    db_res = client.get("/health/database")
    assert db_res.status_code == 200
    db_data = db_res.json()
    assert db_data["status"] == "healthy"
    assert "available_collections" in db_data

    # Orchestration agents registration
    agents_res = client.get("/api/orchestration/agents")
    assert agents_res.status_code == 200
    assert "agents" in agents_res.json()


def test_report_generation_performance(client: TestClient, token_agency_a: str):
    headers = {"Authorization": f"Bearer {token_agency_a}"}

    # Generate performance report for authorized client
    gen_res = client.post(
        "/api/reports/generate",
        json={
            "client_id": "client_scentora",
            "agency_id": "agency_apex_growth",
            "report_type": "performance_analysis",
            "platform": "Meta Ads",
            "date_range": "Last 30 Days",
        },
        headers=headers,
    )
    # If the user's token has agency_alpha, client_scentora belongs to agency_apex_growth
    # So requesting an agency the user doesn't belong to must be forbidden!
    assert gen_res.status_code == 403 or gen_res.status_code == 404


def test_report_generation_authorized(client: TestClient):
    from backend.security.tenant_context import create_tenant_token

    # Token for agency_apex_growth
    token = create_tenant_token(
        user_id="user_apex",
        agency_id="agency_apex_growth",
        roles=["admin", "staff"],
    )
    headers = {"Authorization": f"Bearer {token}"}

    gen_res = client.post(
        "/api/reports/generate",
        json={
            "client_id": "client_scentora",
            "agency_id": "agency_apex_growth",
            "report_type": "performance_analysis",
            "platform": "Meta Ads",
            "date_range": "Last 30 Days",
        },
        headers=headers,
    )
    assert gen_res.status_code == 200, gen_res.text
    data = gen_res.json()
    assert "report_id" in data
    assert data["client_info"]["client_id"] == "client_scentora"
    assert "executive_summary" in data
    assert "performance_overview" in data


def test_script_generation(client: TestClient, token_agency_a: str):
    headers = {"Authorization": f"Bearer {token_agency_a}"}

    res = client.post(
        "/api/storytelling/generate",
        json={
            "brand_name": "Scentora",
            "product_or_service": "Luxury Perfume",
            "target_audience": "Urban young adults",
            "duration": 30,
            "language": "Hinglish",
            "content_style": "Storytelling",
            "marketing_objective": "Product sales",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert "scripts" in data
    assert len(data["scripts"]) >= 1


def test_analysis_reels_endpoint(client: TestClient, token_agency_a: str):
    headers = {"Authorization": f"Bearer {token_agency_a}"}

    reels_res = client.get("/api/analysis/reels", headers=headers)
    assert reels_res.status_code == 200
    assert "reels" in reels_res.json()

    summary_res = client.get("/api/analysis/summary", headers=headers)
    assert summary_res.status_code == 200
