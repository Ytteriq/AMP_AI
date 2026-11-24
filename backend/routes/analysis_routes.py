"""
backend/routes/analysis_routes.py
FastAPI route handlers for Analysis Agent operations.
Dispatches requests through the centralized AgentOrchestrator.
Supports both semantic /api/analysis/... endpoints and legacy /api/chat endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.orchestration.orchestrator import orchestrator, AgentType

router = APIRouter(tags=["Analysis Agent"])


class ChatRequest(BaseModel):
    """User performance inquiry payload."""
    question: str = Field(
        ...,
        min_length=1,
        description="Natural language question regarding reel, campaign, or agency performance.",
        examples=["Which agency is performing better?"],
    )
    session_id: Optional[str] = Field(
        default="default_session",
        description="Session identifier for thread management.",
    )


class ChatResponse(BaseModel):
    """Standardized performance analytics response payload."""
    answer: str
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    reporting_period: Dict[str, Any] = Field(default_factory=dict)
    table: Optional[Dict[str, Any]] = Field(default=None)


def _handle_chat_request(payload: ChatRequest) -> ChatResponse:
    """Helper invoking orchestrator and converting result to ChatResponse."""
    clean_question = payload.question.strip()
    if not clean_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty or purely whitespace.",
        )

    orch_response = orchestrator.dispatch_analysis(
        question=clean_question,
        session_id=payload.session_id or "default_session",
    )

    if not orch_response.success or not orch_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=orch_response.error or "Analysis Agent failed to process inquiry.",
        )

    data = orch_response.data
    return ChatResponse(
        answer=data.get("answer", "No answer generated."),
        evidence=data.get("evidence", []),
        sources=data.get("sources", []),
        metrics=data.get("metrics", {}),
        reporting_period=data.get("reporting_period", {}),
        table=data.get("table"),
    )


# Semantic analysis endpoints
@router.post(
    "/api/analysis/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a performance question to the Analysis Agent (Centralized)",
)
@router.post(
    "/api/analysis",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a performance question to the Analysis Agent (Alias)",
)
# Backward-compatibility endpoint
@router.post(
    "/api/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a performance question to the AI Analyst (Legacy Compatibility)",
)
async def chat_analysis_endpoint(payload: ChatRequest):
    """Routes performance analysis question to the Analysis Agent via Orchestrator."""
    return _handle_chat_request(payload)


@router.get("/api/analysis/reels", summary="List reel records (Analysis)")
@router.get("/api/reels", summary="List all reel records (Legacy Compatibility)")
def get_all_reels():
    """Returns reel documents with calculated metrics and formatted dates from MongoDB."""
    from datetime import datetime
    from backend.analytics.metrics import extract_doc_metrics
    from backend.database.connection import get_collection

    collection = get_collection()
    docs = list(collection.find({}).sort("reel_id", 1))
    results = []
    for d in docs:
        item = extract_doc_metrics(d)
        if "_id" in d:
            item["_id"] = str(d["_id"])
        if isinstance(item.get("published_at"), datetime):
            item["published_at"] = item["published_at"].strftime("%Y-%m-%d %H:%M")
        results.append(item)
    return {"reels": results, "total": len(results)}


@router.get("/api/analysis/summary", summary="Get portfolio performance summary (Analysis)")
@router.get("/api/summary", summary="Get portfolio performance summary (Legacy Compatibility)")
def get_portfolio_summary():
    """Returns high-level KPI totals and agency-level breakdowns."""
    from backend.analytics.metrics import summarize_performance
    from backend.database.connection import get_collection

    collection = get_collection()
    docs = list(collection.find({}))
    return summarize_performance(docs)
