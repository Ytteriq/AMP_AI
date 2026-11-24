"""
agent/graph.py
LangGraph workflow for the AI Reel Performance Analyst.
Coordinates LLM tool decisions, execution, multi-tool loops, and final answer synthesis.
"""

import ast
import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from backend.agent.state import AgentState
from backend.ai.llm_client import get_llm
from backend.ai.prompts import SYSTEM_PROMPT
from backend.tools.analytics_tools import (
    analyze_performance,
    analyze_performance_patterns,
    analyze_profitable_reels,
    compare_agencies,
    compare_campaigns,
    find_underperforming_reels,
    get_portfolio_metric,
)
from backend.tools.database_tools import query_reel_data
from backend.tools.rag_tools import search_knowledge

logger = logging.getLogger("ai_reel.analyst")

# Register all specialized analytics and retrieval tools
TOOLS = [
    get_portfolio_metric,
    analyze_profitable_reels,
    analyze_performance_patterns,
    compare_agencies,
    compare_campaigns,
    find_underperforming_reels,
    query_reel_data,
    analyze_performance,
    search_knowledge,
]
tool_node = ToolNode(TOOLS)


def call_agent(state: AgentState) -> Dict[str, Any]:
    """
    LLM agent node: decides whether to invoke tools or answer directly.
    Guarantees the user question HumanMessage is ALWAYS included in context across all tool steps.
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = list(state.get("messages", []))
    q = state.get("question", "").strip()

    # Separate non-system messages
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    # Guarantee user HumanMessage is present in conversation history
    if not any(isinstance(m, HumanMessage) for m in non_system):
        non_system = [HumanMessage(content=q)] + non_system

    final_messages = [SystemMessage(content=SYSTEM_PROMPT)] + non_system

    logger.info("Agent step invocation: question='%s', history_depth=%d", q, len(final_messages))
    response = llm_with_tools.invoke(final_messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        action_names = [tc.get("name") for tc in response.tool_calls]
        logger.info("Agent selected tool actions: %s", action_names)
    else:
        logger.info("Agent completed synthesis with direct textual answer.")

    # On first turn, return HumanMessage alongside response so LangGraph saves it in state
    if not any(isinstance(m, HumanMessage) for m in state.get("messages", [])):
        return {"messages": [HumanMessage(content=q), response]}

    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", "finalize_response"]:
    """Conditional router: checks if the agent decided to call tools."""
    messages = state.get("messages", [])
    if not messages:
        return "finalize_response"

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_count = sum(1 for m in messages if isinstance(m, ToolMessage))
        if tool_count >= 8:
            logger.warning("Reached maximum tool call loop limit (8). Finalizing response.")
            return "finalize_response"
        return "tools"

    return "finalize_response"


def clean_markdown_and_unwanted_sections(text: str, question: str) -> str:
    """
    Strips unnecessary backslash escaping and removes unrequested auto-appended sections
    such as follow-up questions, recommendations, or reporting-period notes.
    """
    if not text:
        return text

    # 1. Clean backslash escaping before table pipes, hashes, asterisks, underscores, dashes, backticks
    cleaned = re.sub(r"\\([|#*_\-`])", r"\1", str(text))

    q_lower = question.lower()
    explicitly_wants_report = any(
        w in q_lower
        for w in [
            "detailed report",
            "full report",
            "complete report",
            "summarize the performance of all",
            "summary report",
        ]
    )
    explicitly_wants_recommendations = any(
        w in q_lower for w in ["recommend", "next steps", "suggestion", "suggest"]
    )
    explicitly_wants_followup = any(
        w in q_lower for w in ["follow-up", "follow up", "followup", "next question"]
    )

    # 2. Strip unrequested suggested questions or follow-up prompts
    if not explicitly_wants_followup:
        cleaned = re.sub(
            r"(?is)\n*#{1,4}\s*(?:Suggested\s+Follow-up\s+Questions?|Suggested\s+Questions?|Follow-up\s+Questions?|Quick\s+Test\s+Questions?).*$",
            "",
            cleaned,
        )
        cleaned = re.sub(
            r"(?is)\n*(?:\*\*|__)?(?:Suggested\s+Follow-up\s+Questions?|Suggested\s+Questions?|Follow-up\s+Questions?):(?:\*\*|__)?\s*\n(?:[-*0-9.]\s+.*(?:\n|$))+",
            "",
            cleaned,
        )

    # 3. Strip unrequested strategic recommendations or next steps unless requested or detailed report
    if not (explicitly_wants_recommendations or explicitly_wants_report):
        cleaned = re.sub(
            r"(?is)\n*#{1,4}\s*(?:Strategic\s+Recommendations?|Strategic\s+Implications?|Next\s+Steps?|Actionable\s+Recommendations?).*$",
            "",
            cleaned,
        )

    # 4. For single metric or concise requests, strip unrequested reporting period notes / interpretations
    is_short_metric = any(
        w in q_lower
        for w in [
            "only",
            "just",
            "short answer",
            "in one line",
            "overall spend",
            "total revenue",
            "overall profit",
            "overall roi",
        ]
    )
    if is_short_metric and not explicitly_wants_report:
        cleaned = re.sub(
            r"(?is)\n*#{1,4}\s*(?:Reporting\s+Period|Interpretation|Methodology|Overview).*$",
            "",
            cleaned,
        )

    return cleaned.strip()


def finalize_response(state: AgentState) -> Dict[str, Any]:
    """Final answer node: extracts structured evidence, metrics, citations, and final text."""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    raw_final_text = (
        last_message.content if (last_message and hasattr(last_message, "content")) else ""
    )

    question = state.get("question", "")
    final_text = clean_markdown_and_unwanted_sections(raw_final_text, question)

    evidence: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    reporting_period: Dict[str, Any] = {}
    extracted_table: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = list(state.get("tool_results", []))

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_name = msg.name or getattr(msg, "tool_name", "tool")
            content = msg.content
            tool_results.append({"tool": tool_name, "output": content})

            data = content
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                except Exception:
                    try:
                        data = ast.literal_eval(content)
                    except Exception:
                        data = {}

            if isinstance(data, dict):
                # Extract structured table if returned by any analytics tool
                if "table" in data and isinstance(data["table"], dict) and not extracted_table:
                    extracted_table = data["table"]

                # Extract database evidence & reporting period
                if tool_name == "query_reel_data" or "records" in data:
                    if "records" in data and isinstance(data["records"], list):
                        for r in data["records"]:
                            if isinstance(r, dict) and "reel_id" in r:
                                evidence.append(
                                    {
                                        "reel_id": r.get("reel_id"),
                                        "reel_name": r.get("reel_name"),
                                        "agency_name": r.get("agency_name"),
                                        "profit": r.get("profit"),
                                        "roi_percentage": r.get("roi_percentage"),
                                        "views": r.get("views"),
                                    }
                                )
                    if "reporting_period" in data and isinstance(data["reporting_period"], dict):
                        reporting_period.update(data["reporting_period"])

                # Extract analytical metrics
                if tool_name == "analyze_performance" or "operation" in data or "total_net_profit" in data:
                    if "operation" in data:
                        op = data["operation"]
                        metrics[op] = {k: v for k, v in data.items() if k not in ["reels", "rankings"]}
                    else:
                        metrics.update({k: v for k, v in data.items() if k not in ["reels", "rankings"]})

                # Extract document sources from RAG
                if tool_name == "search_knowledge" or "results" in data:
                    if "results" in data and isinstance(data["results"], list):
                        for doc_res in data["results"]:
                            if isinstance(doc_res, dict) and "source" in doc_res:
                                sources.append(
                                    {
                                        "title": doc_res.get("title"),
                                        "source": doc_res.get("source"),
                                        "relevance_score": doc_res.get("relevance_score"),
                                    }
                                )

    logger.info(
        "Final response synthesized: length=%d chars, evidence=%d, sources=%d, table_present=%s",
        len(str(final_text)),
        len(evidence),
        len(sources),
        bool(extracted_table),
    )

    return {
        "final_answer": str(final_text),
        "tool_results": tool_results,
        "retrieved_analytics": metrics,
        "retrieved_documents": sources,
        "table": extracted_table,
    }


def create_agent_graph():
    """Builds and compiles the StateGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", tool_node)
    workflow.add_node("finalize_response", finalize_response)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("finalize_response", END)

    return workflow.compile()


# Module-level compiled agent graph
agent_executor = create_agent_graph()
