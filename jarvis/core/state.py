"""
JARVIS LangGraph State Definition
Defines the unified state container passed across all cognitive nodes.
"""

from typing import Annotated, TypedDict, List, Dict, Optional, Any
from langgraph.graph.message import add_messages

class JarvisState(TypedDict):
    task_id: str
    user_id: str
    messages: Annotated[list, add_messages]
    user_input: str
    retrieved_memories: list[str]
    task_type: str
    risk_level: str
    approval_required: bool
    approval_id: Optional[str]
    selected_tools: list[str]
    selected_agents: list[str]
    model_route: str
    tool_results: list[dict]
    final_response: str
    evidence: list[dict]
