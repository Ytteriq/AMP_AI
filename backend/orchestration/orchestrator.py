"""
backend/orchestration/orchestrator.py
Centralized Orchestration Layer for the AI Marketing Report Generation Platform.

Routes requests across specialized agents:
- Performance Analysis Agent (Performance, Campaign, Monthly Marketing, Creative)
- Content Strategy Agent (Content Strategy, Content Calendar, Advertising Strategy)
- Legacy Analysis & Scriptwriting Agents (Backward compatibility)

Enforces data isolation, request validation, error normalization, and standardized output.
"""

from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from backend.agents.analysis_agent import run_analysis_agent
from backend.agents.storytelling_agent import run_storytelling_agent
from backend.agents.report_agents import (
    generate_content_strategy_report,
    generate_performance_report,
)
from backend.schemas.report_schemas import ReportGenerationRequest
from story_generation.script_schema import ScriptGenerationRequest

logger = logging.getLogger("ai_reel.orchestration")


class AgentType(str, Enum):
    """Supported agent types."""
    REPORT_PERFORMANCE = "report_performance"
    REPORT_CONTENT = "report_content"
    ANALYSIS = "analysis"
    STORYTELLING = "storytelling"


class OrchestrationResponse(BaseModel):
    """Standardized response envelope returned by the orchestration layer."""
    success: bool = Field(..., description="Whether execution completed successfully.")
    agent: str = Field(..., description="The agent that processed the request.")
    operation: str = Field(..., description="The specific operation executed.")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Structured output payload.")
    error: Optional[str] = Field(default=None, description="Human-readable error description if failed.")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentOrchestrator:
    """Centralized orchestrator coordinating multi-agent reporting workflows."""

    def __init__(self) -> None:
        self.registered_agents = {
            AgentType.REPORT_PERFORMANCE: self._handle_performance_report,
            AgentType.REPORT_CONTENT: self._handle_content_report,
            AgentType.ANALYSIS: self._handle_analysis,
            AgentType.STORYTELLING: self._handle_storytelling,
        }
        logger.info("AgentOrchestrator initialized with agents: %s", list(self.registered_agents.keys()))

    def route(
        self,
        agent_type: Union[AgentType, str],
        operation: str,
        payload: Any,
        **kwargs: Any,
    ) -> OrchestrationResponse:
        """Generic entrypoint to route an operation to a designated agent."""
        matched_type: Optional[AgentType] = None
        if isinstance(agent_type, AgentType):
            matched_type = agent_type
        else:
            agent_str = str(getattr(agent_type, "value", agent_type)).lower()
            if "." in agent_str:
                agent_str = agent_str.split(".")[-1]
            for at in AgentType:
                if at.value == agent_str or at.name.lower() == agent_str:
                    matched_type = at
                    break

        if not matched_type:
            err_msg = f"Unknown agent '{agent_type}'. Available agents: {[a.value for a in AgentType]}."
            logger.error("Routing error: %s", err_msg)
            return OrchestrationResponse(
                success=False,
                agent=str(agent_type),
                operation=operation,
                error=err_msg,
            )

        handler = self.registered_agents.get(matched_type)
        if not handler:
            return OrchestrationResponse(
                success=False,
                agent=matched_type.value,
                operation=operation,
                error=f"No handler registered for agent '{matched_type.value}'.",
            )

        try:
            return handler(operation=operation, payload=payload, **kwargs)
        except Exception as exc:
            logger.exception("Orchestration error running '%s' on '%s': %s", operation, matched_type.value, exc)
            return OrchestrationResponse(
                success=False,
                agent=matched_type.value,
                operation=operation,
                error=f"Operation failed: {str(exc)}",
            )

    # -------------------------------------------------------------------------
    # Specialized Report Orchestration Entrypoint
    # -------------------------------------------------------------------------

    def dispatch_report(self, request: Union[ReportGenerationRequest, Dict[str, Any]]) -> OrchestrationResponse:
        """
        Main entrypoint for agency marketing report generation.
        Inspects requested report_type and automatically routes to the specialized agent.
        """
        if isinstance(request, dict):
            try:
                validated_req = ReportGenerationRequest(**request)
            except Exception as ve:
                return OrchestrationResponse(
                    success=False,
                    agent="report_orchestrator",
                    operation="generate_report",
                    error=f"Invalid report request parameters: {str(ve)}",
                )
        else:
            validated_req = request

        rpt_type = validated_req.report_type

        # Route to Content Strategy Agent
        if rpt_type in ["content_strategy", "content_calendar", "advertising_strategy"]:
            return self.route(
                agent_type=AgentType.REPORT_CONTENT,
                operation="generate_content_report",
                payload=validated_req,
            )

        # Route to Performance Analysis Agent
        return self.route(
            agent_type=AgentType.REPORT_PERFORMANCE,
            operation="generate_performance_report",
            payload=validated_req,
        )

    def dispatch_analysis(self, question: str, session_id: str = "default_session") -> OrchestrationResponse:
        """Legacy analysis agent dispatcher."""
        return self.route(
            agent_type=AgentType.ANALYSIS,
            operation="analyze_performance",
            payload={"question": question, "session_id": session_id},
        )

    def dispatch_storytelling(self, payload: Union[ScriptGenerationRequest, Dict[str, Any]]) -> OrchestrationResponse:
        """Legacy scriptwriter agent dispatcher."""
        return self.route(
            agent_type=AgentType.STORYTELLING,
            operation="generate_scripts",
            payload=payload,
        )

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------

    def _handle_performance_report(self, operation: str, payload: Any, **kwargs: Any) -> OrchestrationResponse:
        """Executes Performance Analysis Agent workflow."""
        req: ReportGenerationRequest = payload if isinstance(payload, ReportGenerationRequest) else ReportGenerationRequest(**payload)
        logger.info("Orchestrator running Performance Report for client '%s'", req.client_id)

        report_data = generate_performance_report(
            client_id=req.client_id,
            agency_id=req.agency_id,
            report_type=req.report_type,
            platform=req.platform,
            date_range=req.date_range,
            start_date=req.start_date,
            end_date=req.end_date,
            campaign_filter=req.campaign_filter,
        )

        return OrchestrationResponse(
            success=True,
            agent=AgentType.REPORT_PERFORMANCE.value,
            operation=operation,
            data=report_data,
        )

    def _handle_content_report(self, operation: str, payload: Any, **kwargs: Any) -> OrchestrationResponse:
        """Executes Content Strategy Agent workflow."""
        req: ReportGenerationRequest = payload if isinstance(payload, ReportGenerationRequest) else ReportGenerationRequest(**payload)
        logger.info("Orchestrator running Content Strategy Report for client '%s'", req.client_id)

        report_data = generate_content_strategy_report(
            client_id=req.client_id,
            agency_id=req.agency_id,
            report_type=req.report_type,
            platform=req.platform,
            date_range=req.date_range,
        )

        return OrchestrationResponse(
            success=True,
            agent=AgentType.REPORT_CONTENT.value,
            operation=operation,
            data=report_data,
        )

    def _handle_analysis(self, operation: str, payload: Any, **kwargs: Any) -> OrchestrationResponse:
        """Legacy analysis agent."""
        if isinstance(payload, dict):
            question = payload.get("question", "")
            session_id = payload.get("session_id", "default_session")
        elif isinstance(payload, str):
            question = payload
            session_id = kwargs.get("session_id", "default_session")
        else:
            return OrchestrationResponse(
                success=False,
                agent=AgentType.ANALYSIS.value,
                operation=operation,
                error="Invalid payload: question must be a string or dictionary containing 'question'.",
            )

        clean_q = str(question).strip()
        if not clean_q:
            return OrchestrationResponse(
                success=False,
                agent=AgentType.ANALYSIS.value,
                operation=operation,
                error="Question cannot be empty or purely whitespace.",
            )

        result = run_analysis_agent(question=clean_q, session_id=session_id)
        return OrchestrationResponse(
            success=True,
            agent=AgentType.ANALYSIS.value,
            operation=operation,
            data=result,
        )

    def _handle_storytelling(self, operation: str, payload: Any, **kwargs: Any) -> OrchestrationResponse:
        """Legacy storytelling agent."""
        if isinstance(payload, dict):
            try:
                validated_req = ScriptGenerationRequest(**payload)
            except Exception as ve:
                return OrchestrationResponse(
                    success=False,
                    agent=AgentType.STORYTELLING.value,
                    operation=operation,
                    error=f"Validation failed: {str(ve)}",
                )
        elif isinstance(payload, ScriptGenerationRequest):
            validated_req = payload
        else:
            return OrchestrationResponse(
                success=False,
                agent=AgentType.STORYTELLING.value,
                operation=operation,
                error="Invalid payload for storytelling: expected ScriptGenerationRequest or dictionary.",
            )

        result = run_storytelling_agent(validated_req)
        return OrchestrationResponse(
            success=True,
            agent=AgentType.STORYTELLING.value,
            operation=operation,
            data=result,
        )


# Global singleton orchestrator
orchestrator = AgentOrchestrator()
