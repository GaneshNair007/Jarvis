"""
JARVIS Production FastAPI Server
Exposes:
  1. Policy-Aware Model Router APIs (/model/route, /model/configure, /model/status, /model/usage, /model/costs, /model/approve-expensive-call)
  2. Orchestration & Chat APIs (/api/v1/chat, /api/v1/tasks, /api/v1/approvals)
  3. Power Registry & Telemetry APIs (/api/v1/powers, /api/v1/system/health, /api/v1/audit)
  4. Full-Duplex WebSocket (/ws/stream) for Live HUD Visualizer
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.constants import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from jarvis.core.model_router import model_router, RoutingRequest, RoutingDecision
from jarvis.core.cost_governor import cost_governor
from jarvis.core.orchestrator import orchestrator
from jarvis.core.policy_gate import policy_gate
from jarvis.core.power_registry import power_registry
from jarvis.core.audit import audit_ledger
from jarvis.memory.store import db_store
from jarvis.powers.it_admin_powers import it_admin_powers
from jarvis.api.routes_voice import router as voice_router
from jarvis.api.routes_browser import router as browser_router
from jarvis.api.routes_tasks import router as tasks_router
from jarvis.api.routes_memory import router as memory_router
from jarvis.api.routes_desktop import router as desktop_router
from jarvis.api.routes_integrations import router as integrations_router
from jarvis.api.routes_search import router as search_router
import uuid
from graph.jarvis_graph import jarvis_graph

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Subsystem Routers
app.include_router(voice_router)
app.include_router(browser_router)
app.include_router(tasks_router)
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(memory_router)
app.include_router(memory_router, prefix="/api/v1")
app.include_router(desktop_router)
app.include_router(integrations_router)
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(search_router)
app.include_router(search_router, prefix="/api/v1")

DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"

@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    """Serves the interactive Iron Man glassmorphic HUD dashboard."""
    if not DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="Dashboard UI file not found")
    return FileResponse(DASHBOARD_HTML)

# ══════════════════════════════════════════════════════════════════════════════
# MODEL ROUTER SPECIFIC APIS (Prompt Mandate)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/model/route", response_model=RoutingDecision)
async def route_model_request(req: RoutingRequest):
    """
    Evaluates sensitivity, complexity, latency, and budget to route
    between Bypass, Tier 1 Local, Tier 2 Private GPU, or Tier 3 Cloud.
    """
    return model_router.route(req)

@app.post("/model/configure")
async def configure_models(config: Dict[str, Any] = Body(...)):
    """Updates active model provider settings or default model names."""
    if "ollama_default_model" in config:
        settings.ollama_default_model = config["ollama_default_model"]
    if "vllm_default_model" in config:
        settings.vllm_default_model = config["vllm_default_model"]
    if "daily_budget_limit" in config:
        settings.daily_budget_limit = float(config["daily_budget_limit"])
        cost_governor.daily_budget_limit = float(config["daily_budget_limit"])
    return {"status": "updated", "config": config}

@app.get("/model/status")
async def get_model_status():
    """Returns the operational status of all 3 tiers + circuit breakers."""
    return model_router.get_status()

@app.get("/model/usage")
async def get_model_usage():
    """Returns token and usage statistics per model."""
    return cost_governor.model_stats

@app.get("/model/costs")
async def get_model_costs():
    """Returns daily and monthly cost expenditures versus budget caps."""
    return cost_governor.get_summary()

class ExpensiveCallApproval(BaseModel):
    task_id: str
    target_model: str
    approved: bool
    user_signature: str = Field(default_factory=lambda: settings.jarvis_user_id)

@app.post("/model/approve-expensive-call")
async def approve_expensive_call(approval: ExpensiveCallApproval):
    """Authorizes an inference call that exceeds default per-task limits."""
    if not approval.approved:
        return {"status": "rejected", "task_id": approval.task_id}
    return {
        "status": "approved",
        "task_id": approval.task_id,
        "token": f"exp_app_{int(time.time())}"
    }

# ══════════════════════════════════════════════════════════════════════════════
# CORE JARVIS CHAT & ORCHESTRATION APIS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    query: str
    context: str = ""
    sensitivity_level: str = "medium"
    approval_token: Optional[str] = None

@app.post("/api/v1/chat")
async def chat_endpoint(req: ChatRequest):
    """Central natural language entry point."""
    result = await orchestrator.process_user_query(
        query=req.query,
        context=req.context,
        sensitivity_level=req.sensitivity_level,
        approval_token=req.approval_token
    )
    return result

# ══════════════════════════════════════════════════════════════════════════════
# JARVIS 355 POWER CATALOG & ECOSYSTEM (JARVIS = a + b + c ... n)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/powers/ecosystem")
async def get_ecosystem():
    """Returns the multi-repo composition formula: JARVIS = a + b + c ... n."""
    repos = power_registry.list_ecosystem_repos()
    breakdown = {}
    for r in repos:
        pwrs = power_registry.get_powers_by_repo(r)
        breakdown[r] = {
            "power_count": len(pwrs),
            "sample_powers": [p.get("power_id") for p in pwrs[:5]],
            "local_path": f"repos/{r}"
        }
    return {
        "formula": power_registry.get_ecosystem_formula(),
        "total_powers": power_registry.total_count(),
        "total_repositories": len(repos),
        "repositories": breakdown
    }

@app.get("/api/v1/powers")
async def list_powers(category: Optional[str] = None, repo: Optional[str] = None, q: Optional[str] = None, search: Optional[str] = None):
    """Lists JARVIS powers with optional filtering by category, contributing repo, or keyword search."""
    search_term = q or search
    if search_term:
        return {"query": search_term, "results": power_registry.search_powers(search_term)}
    if repo:
        powers = power_registry.get_powers_by_repo(repo)
        return {"repo": repo, "total": len(powers), "powers": powers}
    if category:
        powers = power_registry.get_powers_by_category(category)
        return {"category": category, "total": len(powers), "powers": powers}
    
    all_powers = power_registry.list_all_powers()
    return {
        "total_powers": len(all_powers),
        "total_categories": len(power_registry.list_categories()),
        "ecosystem_formula": power_registry.get_ecosystem_formula(),
        "powers": all_powers
    }

@app.get("/api/v1/powers/{power_id}")
async def get_power_detail(power_id: str):
    """Retrieves complete 31-field definition of a specific JARVIS power."""
    power = power_registry.get_power(power_id)
    if not power:
        raise HTTPException(status_code=404, detail=f"Power '{power_id}' not found")
    return power

@app.get("/api/v1/system/health")
async def system_health():
    """Live host telemetry."""
    return it_admin_powers.system_health_report()

@app.get("/api/v1/tasks")
async def list_tasks(limit: int = 50):
    """Inspects recent task state machine executions."""
    return db_store.list_tasks(limit=limit)

class ApprovalResolution(BaseModel):
    task_id: str
    approved: bool
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)

@app.post("/api/v1/approvals/{task_id}/resolve")
async def resolve_approval(task_id: str, resolution: ApprovalResolution):
    """Submits human-in-the-loop decision for pending high-privilege actions."""
    pending = policy_gate.pending_approvals.get(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending approval found for this task")

    if not resolution.approved:
        policy_gate.pending_approvals.pop(task_id, None)
        return {"task_id": task_id, "status": "REJECTED"}

    token = pending["token"]
    return {
        "task_id": task_id,
        "status": "APPROVED",
        "approval_token": token
    }

class RootChatPayload(BaseModel):
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)
    message: Optional[str] = None
    query: Optional[str] = None
    context: Optional[str] = ""
    task_type: Optional[str] = "chat"
    approval_token: Optional[str] = None

@app.post("/chat")
async def chat_root(req: RootChatPayload):
    """
    Primary LangGraph cognitive entrypoint:
    START -> memory_retrieval -> policy_check -> model_router -> memory_update -> END
    """
    user_input = req.message or req.query or ""
    if not user_input.strip():
        raise HTTPException(status_code=400, detail="Either 'message' or 'query' must be provided.")

    task_id = f"tsk_{uuid.uuid4().hex[:10]}"
    initial_state = {
        "task_id": task_id,
        "user_id": req.user_id,
        "messages": [{"role": "user", "content": user_input}],
        "user_input": user_input,
        "retrieved_memories": [],
        "task_type": req.task_type or "chat",
        "risk_level": "low",
        "approval_required": False,
        "approval_id": req.approval_token,
        "selected_tools": [],
        "selected_agents": [],
        "model_route": "",
        "tool_results": [],
        "final_response": "",
        "evidence": []
    }

    final_state = jarvis_graph.invoke(initial_state)

    audit_ledger.record(
        actor=req.user_id,
        action="CHAT_REQUEST",
        target=final_state.get("model_route", "local"),
        payload={"task_id": task_id, "user_input": user_input},
        result="SUCCESS",
        task_id=task_id
    )

    return {
        "task_id": final_state["task_id"],
        "user_id": final_state["user_id"],
        "response": final_state["final_response"],
        "reply": final_state["final_response"],
        "retrieved_memories": final_state["retrieved_memories"],
        "model_route": final_state["model_route"],
        "risk_level": final_state["risk_level"],
        "approval_required": final_state["approval_required"]
    }

@app.get("/health")
async def health_root():
    """Health check endpoint confirming Jarvis core services."""
    return {
        "status": "healthy",
        "service": "jarvis-core",
        "version": "1.0.0",
        "timestamp": time.time()
    }

class RootKillSwitchPayload(BaseModel):
    active: bool = True
    reason: str = "API trigger"

@app.post("/kill-switch")
@app.post("/api/v1/kill-switch")
async def toggle_kill_switch(payload: Optional[RootKillSwitchPayload] = None, active: bool = True, reason: str = "API trigger"):
    """Emergency software kill switch."""
    is_active = payload.active if payload else active
    switch_reason = payload.reason if payload else reason
    if is_active:
        policy_gate.trigger_kill_switch(reason=switch_reason)
    else:
        policy_gate.reset_kill_switch()
    return {
        "kill_switch_active": policy_gate.kill_switch_active,
        "status": "ACTIVATED" if policy_gate.kill_switch_active else "DEACTIVATED",
        "reason": switch_reason
    }

@app.get("/powers")
async def list_powers_root(category: Optional[str] = None, search: Optional[str] = None):
    """Lists operational capabilities from initial powers and catalog."""
    if search:
        return power_registry.search_powers(search)
    if category:
        return power_registry.get_powers_by_category(category)
    return {
        "total_powers": power_registry.total_count(),
        "powers": power_registry.list_powers(),
        "categories": power_registry.list_categories()
    }

@app.post("/powers/{power_id}/enable")
async def enable_power_root(power_id: str):
    success = power_registry.enable_power(power_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Power '{power_id}' not found")
    return {"power_id": power_id, "enabled": True}

@app.post("/powers/{power_id}/disable")
async def disable_power_root(power_id: str):
    success = power_registry.disable_power(power_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Power '{power_id}' not found")
    return {"power_id": power_id, "enabled": False}

@app.get("/audit")
@app.get("/api/v1/audit")
async def inspect_audit(limit: int = 50, verify_chain: bool = False):
    """Retrieves recent audit events and optionally verifies SHA-256 chain integrity."""
    entries = audit_ledger.get_recent_entries(limit=limit)
    chain_status = {}
    if verify_chain:
        valid, count, msg = audit_ledger.verify_integrity()
        chain_status = {"valid": valid, "verified_records": count, "message": msg}
    return {
        "total": len(entries),
        "entries": entries,
        "chain_integrity": chain_status
    }

# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET STREAM FOR IRON MAN HUD
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/stream")
async def hud_websocket_stream(websocket: WebSocket):
    """Streams real-time CPU/RAM telemetry, active agents, and live logs to HUD."""
    await websocket.accept()
    try:
        while True:
            # Send live metrics every 1.5 seconds
            health = it_admin_powers.system_health_report()
            payload = {
                "type": "telemetry_pulse",
                "cpu_percent": health["cpu"]["percent"],
                "ram_percent": health["memory"]["percent"],
                "disk_percent": health["disk"]["percent"],
                "kill_switch_active": policy_gate.kill_switch_active,
                "timestamp": time.time()
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
