"""
JARVIS Desktop Worker REST API Routes
Implements Part 11 Desktop Computer Use endpoints:
  POST /desktop/task
  POST /desktop/approve
  POST /desktop/cancel
  GET /desktop/status
  GET /desktop/history
"""

import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.computer.desktop_worker import desktop_worker
from jarvis.core.policy_gate import policy_gate

router = APIRouter(prefix="/api/v1", tags=["Desktop Worker"])

# Pydantic Schemas
class DesktopTaskRequest(BaseModel):
    action: str = Field(..., description="Action type: click, move, type, press, hotkey, focus, wait, screenshot")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action arguments (e.g., x, y, text, title, keys)")
    task_id: Optional[str] = Field(default=None, description="Optional associated task ID")
    require_approval: bool = Field(default=False, description="Explicitly require Tier 2 approval token")
    approval_token: Optional[str] = Field(default=None, description="HMAC approval token if previously issued")

class DesktopApproveRequest(BaseModel):
    task_id: str = Field(..., description="Task ID awaiting execution")
    token: str = Field(..., description="HMAC approval token signed by PolicyGate")
    action: str = Field(..., description="Action to execute upon approval")
    params: Dict[str, Any] = Field(default_factory=dict)

# Endpoints
@router.post("/desktop/task")
def execute_desktop_task(req: DesktopTaskRequest) -> Dict[str, Any]:
    """
    Submits a desktop action to the See-Act-Verify operator.
    Enforces policy approval if action involves high-risk parameters.
    """
    task_id = req.task_id or f"desk_{uuid.uuid4().hex[:12]}"

    # Check emergency kill switch
    if policy_gate.is_kill_switch_active():
        raise HTTPException(status_code=403, detail="CRITICAL: Global kill switch is ACTIVE. Desktop actions are halted.")

    # High-risk approval gate check
    if req.require_approval:
        if not req.approval_token:
            # Generate pending approval token
            approval_res = policy_gate.request_approval(
                power_id="PWR-020",
                task_id=task_id,
                action_summary=f"Desktop Action: {req.action} with params {req.params}",
                payload=req.params
            )
            return {
                "status": "AWAITING_APPROVAL",
                "task_id": task_id,
                "approval_id": approval_res["approval_id"],
                "token": approval_res["token"],
                "message": "Dangerous or consequential desktop action requires explicit approval."
            }
        else:
            # Verify provided token
            if not policy_gate.verify_token(req.approval_token):
                raise HTTPException(status_code=403, detail="Invalid or expired approval token.")

    # Execute action
    result = desktop_worker.see_act_verify(
        action=req.action,
        params=req.params,
        task_id=task_id
    )

    if result.get("status") == "POLICY_BLOCKED":
        raise HTTPException(status_code=403, detail=result.get("reason"))

    return result

@router.post("/desktop/approve")
def approve_desktop_task(req: DesktopApproveRequest) -> Dict[str, Any]:
    """Approves and executes a held desktop task using a valid approval token."""
    if not policy_gate.verify_token(req.token):
        raise HTTPException(status_code=403, detail="Invalid or expired approval token.")

    result = desktop_worker.see_act_verify(
        action=req.action,
        params=req.params,
        task_id=req.task_id
    )
    return result

@router.post("/desktop/cancel")
def cancel_desktop_task() -> Dict[str, Any]:
    """Cancels active desktop control and releases input locks."""
    desktop_worker.is_controlling_screen = False
    return {"status": "CANCELLED", "message": "Desktop control released."}

@router.get("/desktop/status")
def get_desktop_status() -> Dict[str, Any]:
    """Retrieves screen resolution, active foreground window, and safety lock status."""
    return desktop_worker.get_status()

@router.get("/desktop/history")
def get_desktop_history(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    """Returns recent desktop execution traces with pre- and post-action screenshot hashes."""
    history = desktop_worker.task_history[-limit:]
    return {"history": list(reversed(history)), "count": len(history)}
