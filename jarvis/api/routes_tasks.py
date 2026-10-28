"""Task Engine API Endpoints.

Implements the central task lifecycle routes conforming to the Part 2 specification:
- POST /tasks
- POST /tasks/{id}/cancel
- POST /tasks/{id}/approve
- GET /tasks
- GET /tasks/{id}
- GET /tasks/{id}/logs
- GET /tasks/{id}/artifacts
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.state_machine import state_machine
from jarvis.core.orchestrator import orchestrator
from jarvis.core.policy_gate import policy_gate
from jarvis.core.audit import audit_ledger
from jarvis.memory.store import db_store

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
        return {"task_id": task_id, "status": current_state, "message": f"Task already in terminal state: {current_state}"}

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
                    artifacts.append({
                        "event_type": e.get("event_type"),
                        "timestamp": e.get("timestamp"),
                        "artifact_metadata": outputs,
                    })
    return {
        "task_id": task_id,
        "total_artifacts": len(artifacts),
        "artifacts": artifacts,
    }
