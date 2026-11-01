"""
JARVIS LangGraph State Definition
Defines the unified state container passed across all cognitive nodes.
"""

from typing import Annotated, TypedDict, List, Dict, Optional, Any
from langgraph.graph.message import add_messages

class JarvisState(TypedDict, total=False):
    task_id: str
    user_id: str
    messages: Annotated[list, add_messages]
    user_input: str
    retrieved_memories: list[str]
    task_type: str
    risk_level: str
    policy_tier: int
    approval_required: bool
    approval_id: Optional[str]
    policy_reason: str
    selected_tools: list[str]
    selected_agents: list[str]
    model_route: str
    selected_model: str
    provider: str
    routing_reason: str
    tool_results: list[dict]
    final_response: str
    evidence: list[dict]
    duration_ms: float
    estimated_cost_usd: float
    memory_written: bool
