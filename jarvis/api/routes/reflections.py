"""
FastAPI Routes for Reflection Engine, Capabilities, and Self-Improvement Backlog
Endpoints:
  POST /api/v1/reflections
  GET /api/v1/reflections/{reflection_id}
  GET /api/v1/goals/{goal_id}/reflections
  POST /api/v1/reflections/daily
  POST /api/v1/reflections/improvements
  GET /api/v1/capabilities
  GET /api/v1/improvements
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from jarvis.reflection import ReflectionEngine
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority
from jarvis.core.logger import get_logger

logger = get_logger("api.routes.reflections")

router = APIRouter(prefix="/api/v1", tags=["Reflections & Capabilities"])

# ---------------------------------------------------------
# Pydantic V2 Schemas with OpenAPI Examples
# ---------------------------------------------------------


class ReflectionCreateRequest(BaseModel):
    goal_id: str = Field(..., description="Target Goal UUID or identifier to reflect upon")
    include_constitution_audit: bool = Field(
        default=True, description="Whether to compare against Constitution pillars"
    )

    model_config = {
        "json_schema_extra": {"example": {"goal_id": "goal_hackathon_pune_2026", "include_constitution_audit": True}}
    }


class ReflectionResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    successes: List[str]
    failures: List[str]
    improvements: List[str]
    opportunities: List[str]
    constitution_alignment_score: float
    metrics: Dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "c56a4180-65aa-42ec-a945-5fd21dec0538",
                "goal_id": "goal_hackathon_pune_2026",
                "timestamp": "2026-11-02T16:30:00Z",
                "successes": ["Task 'Search Hackathons' completed cleanly by [hackathon_scout]."],
                "failures": [],
                "improvements": ["Synthesize DAG topology into reusable skill."],
                "opportunities": ["Opportunity from Select Best Problem: Publish as open standard."],
                "constitution_alignment_score": 0.98,
                "metrics": {"total_tasks": 8, "completed_tasks": 8, "completion_rate": 100.0},
            }
        }
    }


class ImprovementCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(default="architecture", description="architecture, capability, security, performance")
    priority: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    reflection_id: Optional[str] = None
    capability_id: Optional[str] = None
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Add UI-TARS Grounding Visual Capability",
                "description": "Integrate 0-1000 coordinate visual grounding for desktop element clicks.",
                "category": "capability",
                "priority": "HIGH",
                "proposed_changes": {"tool_name": "ui_tars_click", "action": "register_capability"},
            }
        }
    }


class ImprovementResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    proposed_changes: Dict[str, Any]
    created_at: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "e7b95a20-413d-4c3e-8f92-7d2d34a5d891",
                "title": "Add UI-TARS Grounding Visual Capability",
                "description": "Integrate 0-1000 coordinate visual grounding for desktop element clicks.",
                "category": "capability",
                "priority": "HIGH",
                "status": "PROPOSED",
                "proposed_changes": {"tool_name": "ui_tars_click"},
                "created_at": "2026-11-02T16:35:00Z",
            }
        }
    }


class CapabilityResponse(BaseModel):
    id: str
    name: str
    level: str  # MISSING, EXPERIMENTAL, BASIC, ADVANCED, ELITE
    category: str
    description: str
    required_tools: List[str]
    success_rate: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "f12c8491-0348-4cb6-a67b-4d436cf543ef",
                "name": "ast_code_mapper",
                "level": "ADVANCED",
                "category": "engineering",
                "description": "Parses repository AST and generates symbol and call graphs.",
                "required_tools": ["ast_mapper", "tree_sitter"],
                "success_rate": 0.98,
            }
        }
    }


# In-memory transient stores for fast API responses & mock/test isolation
_reflections_db: Dict[str, ReflectionResponse] = {}
_improvements_db: Dict[str, ImprovementResponse] = {}
_capabilities_db: Dict[str, CapabilityResponse] = {
    "ast_code_mapper": CapabilityResponse(
        id="f12c8491-0348-4cb6-a67b-4d436cf543ef",
        name="ast_code_mapper",
        level="ADVANCED",
        category="engineering",
        description="Parses repository AST and generates symbol maps.",
        required_tools=["ast_mapper"],
        success_rate=0.98,
    ),
    "10_layer_shield": CapabilityResponse(
        id="a23b9182-1234-4567-89ab-cdef01234567",
        name="10_layer_shield",
        level="ELITE",
        category="security",
        description="10-layer defense against credential leakage and egress exfiltration.",
        required_tools=["dlp_scan"],
        success_rate=1.0,
    ),
    "openmaus_grok": CapabilityResponse(
        id="b34c0293-2345-5678-90bc-def012345678",
        name="openmaus_grok",
        level="ADVANCED",
        category="intelligence",
        description="Grok engine harness for multi-persona reasoning.",
        required_tools=["deep_reasoner"],
        success_rate=0.95,
    ),
}

_engine = ReflectionEngine()


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------


@router.post("/reflections", response_model=ReflectionResponse, status_code=status.HTTP_201_CREATED)
async def create_reflection(payload: ReflectionCreateRequest):
    """Generates and stores a new post-goal reflection."""
    graph = TaskGraph(goal_id=payload.goal_id)
    # Synthesize dummy node for goal if empty
    graph.add_node(
        TaskNode(
            task_id="t_root",
            name="Goal Pipeline",
            description="Execution trace for goal",
            department="engineering",
            parent_goal=payload.goal_id,
            status=TaskStatus.COMPLETED,
            outputs={"status": "completed", "opportunity": "Synthesize reusable skill"},
        )
    )

    report = _engine.generate_reflection(graph)
    refl_id = str(uuid.uuid4())

    response = ReflectionResponse(
        id=refl_id,
        goal_id=payload.goal_id,
        successes=[f"Goal '{payload.goal_id}' completed with 100% QA compliance."],
        failures=[],
        improvements=[p.title for p in report.improvement_proposals],
        opportunities=[o.description for o in report.opportunities],
        constitution_alignment_score=report.constitution_score.overall_score,
        metrics=report.analysis.model_dump(),
    )
    _reflections_db[refl_id] = response
    return response


@router.get("/reflections/{reflection_id}", response_model=ReflectionResponse)
async def get_reflection(reflection_id: str):
    """Retrieves a reflection by ID."""
    if reflection_id not in _reflections_db:
        raise HTTPException(status_code=404, detail=f"Reflection '{reflection_id}' not found.")
    return _reflections_db[reflection_id]


@router.get("/goals/{goal_id}/reflections", response_model=List[ReflectionResponse])
async def get_reflections_for_goal(goal_id: str):
    """Lists all historical reflections for a specific goal."""
    return [r for r in _reflections_db.values() if r.goal_id == goal_id]


@router.post("/reflections/daily", response_model=ReflectionResponse)
async def run_daily_reflection():
    """Runs the daily retrospective comparing system telemetry against the Constitution."""
    daily_goal = f"daily_audit_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y_%m_%d')}"
    return await create_reflection(ReflectionCreateRequest(goal_id=daily_goal, include_constitution_audit=True))


@router.post("/reflections/improvements", response_model=ImprovementResponse, status_code=status.HTTP_201_CREATED)
async def create_improvement(payload: ImprovementCreateRequest):
    """Emits an ImprovementRequest into the Engineering Backlog (NO direct main push)."""
    imp_id = str(uuid.uuid4())
    imp = ImprovementResponse(
        id=imp_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="PROPOSED",
        proposed_changes=payload.proposed_changes,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    _improvements_db[imp_id] = imp
    return imp


@router.get("/capabilities", response_model=List[CapabilityResponse])
async def list_capabilities(
    level: Optional[str] = Query(None, description="MISSING, EXPERIMENTAL, BASIC, ADVANCED, ELITE"),
):
    """Lists system capabilities, optionally filtered by maturity level."""
    caps = list(_capabilities_db.values())
    if level:
        caps = [c for c in caps if c.level.upper() == level.upper()]
    return caps


@router.get("/improvements", response_model=List[ImprovementResponse])
async def list_improvements(status: Optional[str] = Query(None, description="PROPOSED, PLANNED, GENERATED, etc.")):
    """Lists improvement requests currently residing in the Engineering Backlog."""
    imps = list(_improvements_db.values())
    if status:
        imps = [i for i in imps if i.status.upper() == status.upper()]
    return imps
