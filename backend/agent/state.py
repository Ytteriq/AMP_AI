"""
agent/state.py
Defines the typed state structure for the LangGraph agent workflow.
"""

from typing import Annotated, Any, Dict, List, Optional, Sequence
from typing_extensions import TypedDict

try:
    from langchain_core.messages import BaseMessage
    from langgraph.graph.message import add_messages
except ImportError:
    # Fallback types if imports are initializing
    BaseMessage = Any
    add_messages = lambda x, y: y


class AgentState(TypedDict):
    """
    Typed state containing:
    - User question.
    - Message history.
    - Tool results.
    - Retrieved analytics data.
    - Retrieved document context.
    - Final answer.
    - Structured table representation.
    - Error information when necessary.
    """
    question: str
    messages: Annotated[Sequence[Any], add_messages]
    tool_results: List[Dict[str, Any]]
    retrieved_analytics: Dict[str, Any]
    retrieved_documents: List[Dict[str, Any]]
    final_answer: str
    table: Optional[Dict[str, Any]]
    error: Optional[str]
