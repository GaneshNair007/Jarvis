"""Task Engine API Endpoints.

Implements the central task lifecycle routes conforming to the Part 2 specification:
- POST /tasks
- POST /tasks/{id}/cancel
- POST /tasks/{id}/approve
- GET /tasks
- GET /tasks/{id}
- GET /tasks/{id}/logs
- GET /tasks/{id}/artifacts
- POST /goals/execute (Phase 1 & 2 Task Graph DAG Integration)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.state_machine import state_machine
from jarvis.core.orchestrator import orchestrator
from jarvis.core.policy_gate import policy_gate
from jarvis.core.audit import audit_ledger
from jarvis.memory.store import db_store
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority as TaskPriority
from jarvis.core.task_executor import TaskExecutor
from jarvis.services.goal_service import GoalService
from jarvis.core.logger import get_logger

logger = get_logger("api.routes_tasks")

router = APIRouter(tags=["tasks"])


class CreateTaskRequest(BaseModel):
    intent: str
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)
    priority: str = "normal"
    deadline: Optional[float] = None
    device_required: str = "laptop"
    context: str = ""
    sensitivity_level: str = "medium"


class TaskApprovalRequest(BaseModel):
    approved: bool
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)
    notes: str = ""


class GoalExecuteRequest(BaseModel):
    title: str = Field(..., description="High-level goal title or natural language user intention")
    description: str = ""
    pipeline_type: str = Field(default="auto", description="auto, hackathon, engineering, research, security, career")
    priority: str = "HIGH"
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Help me find and win an AI hackathon in Pune",
                "description": "Scout Devpost, read rules, select problem, generate architecture, create repo, roadmap.",
                "pipeline_type": "hackathon",
                "priority": "HIGH",
            }
        }
    }


def _decompose_goal_to_dag(goal_id: str, title: str, description: str, pipeline_type: str) -> TaskGraph:
    """Decomposes user goal into a topologically sorted TaskGraph DAG."""
    graph = TaskGraph(goal_id=goal_id)
    title_lower = title.lower()

    if pipeline_type == "hackathon" or "hackathon" in title_lower:
        tasks = [
            ("t1", "Search Hackathons", "hackathon", [], ["web_search"]),
            ("t2", "Filter Pune and Online", "hackathon", ["t1"], ["data_filter"]),
            ("t3", "Read Guidelines", "hackathon", ["t2"], ["doc_parser"]),
            ("t4", "Analyze Rules and Prizes", "hackathon", ["t3"], ["deep_reasoner"]),
            ("t5", "Select Best Problem Statement", "hackathon", ["t4"], ["decision_matrix"]),
            ("t6", "Generate System Architecture", "engineering", ["t5"], ["ast_mapper"]),
            ("t7", "Create Git Repository", "engineering", ["t6"], ["git_cli"]),
            ("t8", "Build MVP and Roadmap", "engineering", ["t7"], ["roadmap_generator"]),
        ]
    elif pipeline_type == "engineering" or "code" in title_lower or "refactor" in title_lower:
        tasks = [
            ("t1", "Audit Repository AST", "engineering", [], ["ast_mapper"]),
            ("t2", "Design System Architecture", "engineering", ["t1"], ["mermaid_gen"]),
            ("t3", "Scaffold Code Implementation", "engineering", ["t2"], ["git_cli"]),
            ("t4", "Run PyTest Verification", "engineering", ["t3"], ["pytest"]),
            ("t5", "Author Safe PR Proposal", "engineering", ["t4"], ["git_cli"]),
        ]
    elif pipeline_type == "research" or "research" in title_lower or "paper" in title_lower:
        tasks = [
            ("t1", "Scout Academic and Web Sources", "research", [], ["web_search"]),
            ("t2", "Parse Documentation and Papers", "research", ["t1"], ["doc_parser"]),
            ("t3", "Extract Citations and Claims", "research", ["t2"], ["citation_extractor"]),
            ("t4", "Synthesize Deep Research Report", "research", ["t3"], ["deep_reasoner"]),
        ]
    elif pipeline_type == "security" or "security" in title_lower or "secret" in title_lower:
        tasks = [
            ("t1", "Audit Code Credentials and Secrets", "security", [], ["entropy_scanner"]),
            ("t2", "Scan Outbound Egress DLP", "security", ["t1"], ["dlp_scan"]),
            ("t3", "Verify Merkle Chain Integrity", "security", ["t2"], ["merkle_audit"]),
        ]
    else:
        # General intelligent decomposition
        tasks = [
            ("t1", "Strategic Problem Analysis", "research", [], ["deep_reasoner"]),
            ("t2", "Plan Architecture Solution", "engineering", ["t1"], ["decision_matrix"]),
            ("t3", "Execute Operations", "engineering", ["t2"], ["default_executor"]),
            ("t4", "Verification and Quality Gate", "engineering", ["t3"], ["pytest"]),
        ]

    for tid, name, dept, deps, tools in tasks:
        node = TaskNode(
            task_id=tid,
            name=name,
            description=f"Execution of {name} for {title}",
            department=dept,
            parent_goal=goal_id,
            dependencies=deps,
            tool_requirements=tools,
            priority=TaskPriority.HIGH,
        )
        graph.add_node(node)

    return graph


@router.post("/goals/execute")
async def execute_goal(req: GoalExecuteRequest):
    """
    Decomposes a high-level user goal into a topologically sorted TaskGraph DAG,
    stores it in the relational database, routes nodes to specialized department workers,
    and executes it parallel wave-by-wave with multi-stage QA verification and reflection.
    """
    goal_service = GoalService()
    db_goal = goal_service.create_goal(
        title=req.title,
        description=req.description,
        priority=req.priority,
        metadata={"pipeline_type": req.pipeline_type, **req.context},
    )
    goal_id_str = str(db_goal.id)

    # Decompose into TaskGraph DAG
    graph = _decompose_goal_to_dag(goal_id_str, req.title, req.description, req.pipeline_type)

    # Persist DAG in relational models
    try:
        goal_service.store_task_graph_dag(db_goal.id, graph)
    except Exception as e:
        logger.warning(f"Could not persist task graph DAG to database: {e}")

    # Execute DAG wave-by-wave
    executor = TaskExecutor()
    report = await executor.run(graph, timeout=60.0)

    # Complete goal
    try:
        goal_service.complete_goal(db_goal.id)
    except Exception as e:
        logger.warning(f"Goal completion event notice: {e}")

    return {
        "goal_id": goal_id_str,
        "title": req.title,
        "status": report.status.value,
        "total_tasks": report.total_tasks,
        "completed_tasks": report.completed_tasks,
        "failed_tasks": report.failed_tasks,
        "duration_seconds": report.duration_seconds,
        "task_results": report.task_results,
        "reflection": report.reflection.model_dump() if report.reflection else None,
    }


@router.post("/tasks")
async def create_task(req: CreateTaskRequest):
    """Creates, triages, and dispatches a new task through the central orchestrator."""
    task_id = f"tsk_{uuid.uuid4().hex[:10]}"
    result = await orchestrator.process_user_query(
        query=req.intent,
        task_id=task_id,
        context=req.context,
        sensitivity_level=req.sensitivity_level,
    )
    return result


@router.get("/tasks")
def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
):
    """Lists recent tasks with optional status filter."""
    raw_tasks = db_store.list_tasks(limit=limit)
    tasks = []
    for t in raw_tasks:
        item = dict(t)
        item["task_id"] = item.get("id")
        if not status or item.get("status") == status:
            tasks.append(item)
    return {"total": len(tasks), "tasks": tasks}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Retrieves full task details, current lifecycle state, and timestamps."""
    task = db_store.get_task(task_id)
    if not task:
        # Fall back to in-memory state machine if not yet flushed
        state = state_machine.get_task_state(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return {"task_id": task_id, "status": state}
    task_dict = dict(task)
    task_dict["task_id"] = task_dict.get("id")
    return task_dict


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, reason: str = "User requested cancellation"):
    """Transitions an active or queued task to CANCELLED state."""
    current_state = state_machine.get_task_state(task_id)
    if not current_state:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    if current_state in ("COMPLETED", "FAILED_TERMINAL", "CANCELLED"):
        return {
            "task_id": task_id,
            "status": current_state,
            "message": f"Task already in terminal state: {current_state}",
        }

    state_machine.transition(task_id, "CANCELLED", reason=reason)
    audit_ledger.record(
        actor="user",
        action="task_cancelled",
        target=task_id,
        payload={"reason": reason},
        result="CANCELLED",
        task_id=task_id,
    )
    return {"task_id": task_id, "status": "CANCELLED", "reason": reason}


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, req: TaskApprovalRequest):
    """Resolves human approval for high-privilege tasks awaiting authorization."""
    pending = policy_gate.pending_approvals.get(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"No pending approval found for task '{task_id}'")

    if not req.approved:
        policy_gate.pending_approvals.pop(task_id, None)
        state_machine.transition(task_id, "REJECTED", reason="User denied approval")
        audit_ledger.record(
            actor=req.user_id,
            action="approval_denied",
            target=task_id,
            payload={"notes": req.notes},
            result="DENIED",
            task_id=task_id,
        )
        return {"task_id": task_id, "status": "REJECTED", "message": "Approval denied by user."}

    token = pending["token"]
    audit_ledger.record(
        actor=req.user_id,
        action="approval_granted",
        target=task_id,
        payload={"notes": req.notes, "token": token[:16] + "..."},
        result="APPROVED",
        task_id=task_id,
    )
    return {
        "task_id": task_id,
        "status": "APPROVED",
        "approval_token": token,
        "expires_at": pending.get("expires_at"),
    }


@router.get("/tasks/{task_id}/logs")
def get_task_logs(task_id: str):
    """Retrieves all cryptographic audit logs and lifecycle events for a specific task."""
    entries = audit_ledger.get_recent_entries(limit=100)
    task_entries = [e for e in entries if e.get("task_id") == task_id]
    return {
        "task_id": task_id,
        "total_logs": len(task_entries),
        "logs": task_entries,
    }


@router.get("/tasks/{task_id}/artifacts")
def get_task_artifacts(task_id: str):
    """Retrieves visual screenshots, diffs, and research files generated for this task."""
    entries = audit_ledger.get_recent_entries(limit=100)
    artifacts = []
    for e in entries:
        if e.get("task_id") == task_id:
            outputs = e.get("outputs", {})
            if isinstance(outputs, dict):
                if "sha256" in outputs or "report_file" in outputs or "file" in outputs:
                    artifacts.append(
                        {
                            "event_type": e.get("event_type"),
                            "timestamp": e.get("timestamp"),
                            "artifact_metadata": outputs,
                        }
                    )
    return {
        "task_id": task_id,
        "total_artifacts": len(artifacts),
        "artifacts": artifacts,
    }
