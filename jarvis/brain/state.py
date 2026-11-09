"""
JARVIS Unified Cognitive State Schema
Defines strongly-typed Pydantic validation models and the 15-field JarvisState / BrainState
TypedDict for the 8-node cyclic state machine, with 100% backward compatibility.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


# ── Pydantic Component Validation Models ─────────────────────────────────────


class InputEvent(BaseModel):
    """Normalized multimodal input stimulus."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:10]}")
    timestamp: float = Field(default_factory=time.time)
    text: str = ""
    modality: Literal["text", "voice", "system", "gui"] = "text"
    source: str = "user_input"
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """Atomic step in a decomposed cognitive execution plan."""

    step_id: str = Field(default_factory=lambda: f"stp_{uuid.uuid4().hex[:8]}")
    description: str
    tool: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    depends_on: List[str] = Field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None


class RetrievedMemory(BaseModel):
    """Scoped recalled memory with authority and provenance metadata."""

    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:10]}")
    content: str
    provenance: str = "memory_store"
    is_explicit: bool = True
    category: str = "fact"
    score: float = 0.0
    status: str = "active"


class ToolExecutionRecord(BaseModel):
    """Audit record of an invoked tool or power execution."""

    call_id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["invoked", "success", "error", "blocked"] = "invoked"
    output: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = Field(default_factory=time.time)
    duration_ms: float = 0.0


class EvidenceItem(BaseModel):
    """Observable ground-truth receipt verifying an action or output."""

    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    source: str = "observation"
    claim: str = ""
    quote: Optional[str] = None
    confidence: float = 1.0
    timestamp: float = Field(default_factory=time.time)
    artifact_hash: Optional[str] = None


class PolicyDecisionState(BaseModel):
    """Security gate evaluation decision."""

    tier: int = Field(0, ge=0, le=3)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    approval_required: bool = False
    reason: str = "Tier 0 permitted"
    allowed_tools: List[str] = Field(default_factory=list)
    approval_id: Optional[str] = None


class ApprovalState(BaseModel):
    """Human-in-the-loop cryptographic approval status."""

    status: Literal["NONE", "PENDING", "APPROVED", "DENIED", "EXPIRED"] = "NONE"
    approval_id: Optional[str] = None
    power_id: Optional[str] = None
    action_summary: Optional[str] = None
    payload_hash: Optional[str] = None
    token: Optional[str] = None
    expires_at: Optional[float] = None


class CognitiveError(BaseModel):
    """Structured error classification item."""

    code: Literal[
        "TRANSIENT_NETWORK",
        "SESSION_EXPIRED",
        "POLICY_DENIED",
        "AI_USAGE_LIMIT",
        "INSUFFICIENT_EVIDENCE",
        "PERMANENT_FAILURE",
    ]
    message: str
    recoverable: bool
    retry_count: int = 0
    timestamp: float = Field(default_factory=time.time)
    details: Dict[str, Any] = Field(default_factory=dict)


class CostLedger(BaseModel):
    """Granular token expenditure and cost tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_usd: float = 0.0
    model_breakdown: Dict[str, float] = Field(default_factory=dict)


# ── Unified Cognitive State TypedDict ────────────────────────────────────────


class JarvisState(TypedDict, total=False):
    """
    Unified cognitive state dictionary passed across all 8 nodes:
    perceive -> recall -> plan -> policy -> act -> verify -> reflect -> remember

    Includes all 15 required cognitive fields and preserves backward-compatible keys.
    """

    # 1. Identity & Tracking (Mandatory Core Fields)
    user_id: str
    session_id: str
    trace_id: str
    task_id: str

    # 2. Perception & Intent (Mandatory Core Fields)
    input_event: Dict[str, Any]
    user_input: str
    goal: str
    messages: Annotated[list, add_messages]

    # 3. Context & Working Memory (Mandatory Core Fields)
    retrieved_memories: List[Any]
    retrieved_memory_records: List[Dict[str, Any]]
    scratchpad: str

    # 4. Planning & Routing (Mandatory Core Fields)
    plan: List[Dict[str, Any]]
    current_step_index: int
    is_fast_path: bool
    task_type: str
    model_route: str
    selected_model: str
    provider: str
    routing_reason: str
    selected_tools: List[str]
    selected_agents: List[str]

    # 5. Security & Approvals (Mandatory Core Fields)
    policy_tier: int
    risk_level: str
    policy_decision: Dict[str, Any]
    approval_required: bool
    approval_id: Optional[str]
    policy_reason: str
    approvals: Dict[str, Any]

    # 6. Execution & Telemetry (Mandatory Core Fields)
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    final_response: str
    duration_ms: float

    # 7. Verification & Evidence (Mandatory Core Fields)
    evidence: List[Dict[str, Any]]
    confidence: float

    # 8. Learning, Reflection & Governance (Mandatory Core Fields)
    errors: List[Dict[str, Any]]
    reflection_count: int
    cost: Dict[str, Any]
    estimated_cost_usd: float
    memory_written: bool


# Canonical alias for Phase 1 Brain State
BrainState = JarvisState

__all__ = [
    "InputEvent",
    "PlanStep",
    "RetrievedMemory",
    "ToolExecutionRecord",
    "EvidenceItem",
    "PolicyDecisionState",
    "ApprovalState",
    "CognitiveError",
    "CostLedger",
    "JarvisState",
    "BrainState",
]
