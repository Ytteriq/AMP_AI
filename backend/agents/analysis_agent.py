"""
backend/agents/analysis_agent.py
Modular interface for Agent 1: AI Reel Performance Analyst.
Coordinates LangGraph execution, structured evidence aggregation, and metric synthesis.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.agent.graph import agent_executor, create_agent_graph

logger = logging.getLogger("ai_reel.agents.analysis")


def run_analysis_agent(question: str, session_id: str = "default_session") -> Dict[str, Any]:
    """
    Executes the LangGraph analysis agent workflow for a given question.
    Returns structured results containing answer text, evidence records,
    referenced strategy documents, calculated metrics, and tables.
    """
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("Question cannot be empty or purely whitespace.")

    initial_state = {
        "question": clean_question,
        "messages": [],
        "tool_results": [],
        "retrieved_analytics": {},
        "retrieved_documents": [],
        "final_answer": "",
        "error": None,
    }

    logger.info("Executing Analysis Agent for question: '%s' (session=%s)", clean_question[:60], session_id)
    result = agent_executor.invoke(initial_state)

    answer_text = result.get("final_answer") or "No answer could be generated from available data."
    sources = result.get("retrieved_documents", [])
    analytics = result.get("retrieved_analytics", {})
    evidence_list: List[Dict[str, Any]] = []
    reporting_period: Dict[str, Any] = {}
    table: Optional[Dict[str, Any]] = result.get("table")

    for tool_res in result.get("tool_results", []):
        out = tool_res.get("output")
        if isinstance(out, dict):
            if "records" in out and isinstance(out["records"], list):
                evidence_list.extend(out["records"])
            if "reporting_period" in out and out["reporting_period"]:
                reporting_period = out["reporting_period"]
            if "table" in out and isinstance(out["table"], dict) and not table:
                table = out["table"]

    return {
        "answer": answer_text,
        "evidence": evidence_list,
        "sources": sources,
        "metrics": analytics,
        "reporting_period": reporting_period,
        "table": table,
    }


__all__ = [
    "run_analysis_agent",
    "agent_executor",
    "create_agent_graph",
]
