"""
backend/app.py
Centralized FastAPI application factory and instance for AI Reel Multi-Agent Platform.
Unified backend serving Agent 1 (Analysis) and Agent 2 (Storytelling) through Orchestration.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import settings
from backend.database.connection import check_database_health, close_mongo_client
from backend.orchestration.orchestrator import AgentType
from backend.routes.analysis_routes import router as analysis_router
from backend.routes.storytelling_routes import router as storytelling_router
from backend.routes.report_routes import router as report_router
from backend.security.exceptions import (
    CrossAgencySubstitutionError,
    DecryptionError,
    SecurityError,
    TamperedCiphertextError,
    TenantAccessDeniedError,
    TenantAuthorizationError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger("ai_reel.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for graceful multi-agent startup and shutdown."""
    logger.info("Initializing AI Reel Centralized Multi-Agent Platform...")
    settings.validate_core()
    yield
    logger.info("Shutting down AI Reel Centralized Multi-Agent Platform...")
    close_mongo_client()


def create_app() -> FastAPI:
    """Creates and configures the unified FastAPI application."""
    application = FastAPI(
        title="AI Reel Centralized Multi-Agent Platform",
        description=(
            "Centralized dual-agent AI marketing system for Indian agencies:\n"
            "- Analysis Agent (Performance Analyst): MongoDB Atlas analytics, ROI metrics, agency playbooks.\n"
            "- Storytelling Agent (Scriptwriter): 3 distinct Reel script variations (Hook, Story, Conversion).\n"
            "Unified through a single orchestration layer and single server on port 8000."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for React, Next.js, and browser frontends
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register security and tenant exception handlers
    @application.exception_handler(TenantAccessDeniedError)
    async def tenant_access_denied_handler(request, exc: TenantAccessDeniedError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @application.exception_handler(TenantAuthorizationError)
    async def tenant_auth_handler(request, exc: TenantAuthorizationError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)}, headers={"WWW-Authenticate": "Bearer"})

    @application.exception_handler(CrossAgencySubstitutionError)
    async def cross_agency_handler(request, exc: CrossAgencySubstitutionError):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @application.exception_handler(TamperedCiphertextError)
    async def tampered_ciphertext_handler(request, exc: TamperedCiphertextError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @application.exception_handler(DecryptionError)
    async def decryption_error_handler(request, exc: DecryptionError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    # Register centralized routers
    application.include_router(report_router)
    application.include_router(analysis_router)
    application.include_router(storytelling_router)

    # Static UI routes
    @application.get(
        "/",
        tags=["Dashboard"],
        summary="Interactive Web Dashboard & Performance Analyst Tester",
    )
    def serve_dashboard():
        index_path = PROJECT_ROOT / "index.html"
        if not index_path.exists():
            index_path = PROJECT_ROOT / "backend" / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "service": "AI Reel Centralized Multi-Agent Platform",
                "status": "online",
                "version": "2.0.0",
                "documentation": "/docs",
                "health": "/health",
            },
        )

    @application.get(
        "/scriptwriter",
        tags=["Scriptwriter UI"],
        summary="Dedicated AI Reel Scriptwriter Interface",
    )
    @application.get(
        "/storytelling",
        tags=["Scriptwriter UI"],
        summary="Dedicated AI Reel Storytelling Interface",
    )
    @application.get(
        "/scripts-ui",
        tags=["Scriptwriter UI"],
        summary="Dedicated AI Reel Scriptwriter Interface (Alias)",
    )
    @application.get(
        "/story_generation",
        tags=["Scriptwriter UI"],
        summary="Dedicated AI Reel Scriptwriter Interface (Alias)",
    )
    def serve_scriptwriter_page():
        scriptwriter_path = PROJECT_ROOT / "backend" / "scriptwriter.html"
        if not scriptwriter_path.exists():
            scriptwriter_path = PROJECT_ROOT / "story_generation" / "index.html"
        if scriptwriter_path.exists():
            return FileResponse(str(scriptwriter_path))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "service": "AI Reel Scriptwriter Studio",
                "status": "online",
                "endpoint": "/api/storytelling/generate",
                "documentation": "/docs",
            },
        )

    # Health & Diagnostics Endpoints
    @application.get(
        "/health",
        tags=["System Health"],
        summary="Centralized Application & Multi-Agent Health Check",
        status_code=status.HTTP_200_OK,
    )
    def health_check():
        return {
            "status": "healthy",
            "service": "AI Reel Centralized Multi-Agent Platform",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_agents": [agent.value for agent in AgentType],
            "model": settings.LLM_MODEL,
            "models": {
                "analysis": settings.LLM_MODEL,
                "storytelling": settings.STORYTELLING_MODEL or "llama-3.3-70b-versatile",
            },
        }

    @application.get(
        "/health/database",
        tags=["System Health"],
        summary="MongoDB Atlas Connection Health Check",
        status_code=status.HTTP_200_OK,
    )
    def database_health_check():
        health_info = check_database_health()
        status_code = (
            status.HTTP_200_OK
            if health_info.get("status") == "healthy"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return JSONResponse(status_code=status_code, content=health_info)

    @application.get(
        "/api/orchestration/agents",
        tags=["Orchestration"],
        summary="List available agents and registered capabilities",
    )
    def get_registered_agents():
        return {
            "agents": [
                {
                    "id": "analysis",
                    "name": "AI Reel Performance Analyst",
                    "model": settings.LLM_MODEL,
                    "provider": "Groq",
                    "description": "Analyzes marketing metrics, calculates profit, CPA, and ROAS, performs agency benchmarks, searches strategy playbooks.",
                    "endpoints": [
                        "POST /api/analysis/chat",
                        "POST /api/chat",
                        "GET /api/analysis/reels",
                        "GET /api/analysis/summary",
                        "POST /api/reports/generate",
                    ],
                },
                {
                    "id": "storytelling",
                    "name": "AI Reel Scriptwriter & Storyteller",
                    "model": settings.STORYTELLING_MODEL or "llama-3.3-70b-versatile",
                    "provider": "Groq",
                    "description": "Generates 3 tailored script variations (Hook, Storytelling, Conversion) and creative content strategies.",
                    "endpoints": [
                        "POST /api/storytelling/generate",
                        "POST /api/scripts/generate",
                    ],
                },
            ],
            "orchestrator_status": "ready",
        }

    return application


# Global application singleton
app = create_app()
