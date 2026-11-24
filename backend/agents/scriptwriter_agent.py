"""
backend/agents/scriptwriter_agent.py
Backward-compatible proxy for Agent 2: AI Reel Scriptwriter / Storytelling Agent.
"""

from backend.agents.storytelling_agent import (
    create_scriptwriter_graph,
    generate_reel_scripts,
    run_storytelling_agent,
    scriptwriter_graph,
)

__all__ = [
    "create_scriptwriter_graph",
    "generate_reel_scripts",
    "run_storytelling_agent",
    "scriptwriter_graph",
]
