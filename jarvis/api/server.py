"""
JARVIS Production FastAPI Server
Exposes:
  1. Policy-Aware Model Router APIs (/model/route, /model/configure, /model/status, /model/usage, /model/costs, /model/approve-expensive-call)
  2. Orchestration & Chat APIs (/api/v1/chat, /api/v1/tasks, /api/v1/approvals)
  3. Power Registry & Telemetry APIs (/api/v1/powers, /api/v1/system/health, /api/v1/audit)
  4. Full-Duplex WebSocket (/ws/stream) for Live HUD Visualizer
"""

import asyncio
import datetime
import time
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.constants import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from jarvis.core.logger import get_logger

logger = get_logger("api.server")
from jarvis.core.model_router import model_router, RoutingRequest, RoutingDecision
from jarvis.core.cost_governor import cost_governor
from jarvis.core.orchestrator import orchestrator
from jarvis.core.policy_gate import policy_gate
from jarvis.core.power_registry import power_registry
from jarvis.core.audit import audit_ledger
from jarvis.core.capability_guard import capability_guard
from jarvis.memory.store import db_store
from jarvis.powers.it_admin_powers import it_admin_powers

admin_token_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_admin_user(
    token_header: Optional[str] = Depends(admin_token_header),
    bearer_auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    user_id_header: Optional[str] = Header(None, alias="X-Jarvis-User-Id"),
) -> str:
    """
    Fail-closed administrator authentication dependency.
    Validates that the caller holds the administrative secret key
    and matches the configured authorized user ID.
    """
    candidate_token = None
    if bearer_auth and bearer_auth.credentials:
        candidate_token = bearer_auth.credentials
    elif token_header:
        candidate_token = token_header

    if not candidate_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing admin bearer token or X-Admin-Token header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_secret = settings.jarvis_secret_key
    if not hmac.compare_digest(candidate_token.strip(), expected_secret.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization failed: Invalid administrator secret token.",
        )

    if user_id_header and user_id_header.strip() != settings.jarvis_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authorization failed: User '{user_id_header}' is not authorized as administrator.",
        )

    return settings.jarvis_user_id


def generate_expensive_call_token(
    task_id: str,
    target_model: str,
    user_id: str,
    ttl_minutes: Optional[int] = None,
) -> Tuple[str, int]:
    """Generates cryptographic HMAC-SHA256 token authorizing expensive model inference."""
    ttl = ttl_minutes or settings.approval_token_expiry_minutes
    expiry = int(time.time() + (ttl * 60))
    message = f"expensive:{user_id}:{task_id}:{target_model}:{expiry}".encode("utf-8")
    sig = hmac.new(settings.jarvis_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    token = f"exp_hmac_{sig}.{expiry}"
    return token, expiry


def verify_expensive_call_token(
    token: str,
    task_id: str,
    target_model: str,
    user_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Validates signature, expiration, and payload binding of expensive call token."""
    if not token or not isinstance(token, str):
        return False, "Expensive call token is missing or empty"
    if not token.startswith("exp_hmac_"):
        return False, "Invalid token format: missing exp_hmac_ prefix"

    raw = token[len("exp_hmac_"):]
    try:
        sig, expiry_str = raw.split(".")
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False, "Expensive call token has expired"

        expected_user = user_id or settings.jarvis_user_id
        message = f"expensive:{expected_user}:{task_id}:{target_model}:{expiry}".encode("utf-8")
        expected_sig = hmac.new(settings.jarvis_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()

        if hmac.compare_digest(sig, expected_sig):
            return True, "Expensive call token valid and verified"
        return False, "Invalid cryptographic signature on expensive call token"
    except Exception as e:
        return False, f"Malformed expensive call token: {e}"
from jarvis.api.routes_voice import router as voice_router
from jarvis.api.routes_browser import router as browser_router
from jarvis.api.routes_tasks import router as tasks_router
from jarvis.api.routes_memory import router as memory_router
from jarvis.api.routes_desktop import router as desktop_router
from jarvis.api.routes_integrations import router as integrations_router
from jarvis.api.routes_search import router as search_router
from jarvis.api.routes_career import router as career_router
from jarvis.api.routes_assistants import router as assistants_router
from jarvis.api.routes_smart_home import router as smart_home_router
from jarvis.api.routes_ops import router as ops_router
from jarvis.api.routes_grok import router as grok_router
from jarvis.api.routes_workforce import router as workforce_router
from jarvis.api.routes.reflections import router as reflections_router
from jarvis.api.routes_ventures import router as ventures_router
from jarvis.api.routes_gsoc import router as gsoc_router
from jarvis.api.routes_opportunities import router as opportunities_router
from jarvis.api.routes_autonomous import router as autonomous_router
import uuid
from graph.jarvis_graph import get_jarvis_graph

app = FastAPI(title=APP_TITLE, version=APP_VERSION, description=APP_DESCRIPTION)

def print_honest_startup_banner() -> str:
    """Sprint 1 Trust Fix: Honest Capability Status Banner."""
    from jarvis.core.capability_guard import capability_guard, CapabilityStatus
    caps = capability_guard.get_all_status()
    ollama_str = "ONLINE" if caps.get("ollama") == CapabilityStatus.CONNECTED else "OFFLINE"
    gmail_str = "CONNECTED" if caps.get("gmail") == CapabilityStatus.CONNECTED else "DISCONNECTED"
    internet_str = "AVAILABLE" if caps.get("internet") == CapabilityStatus.CONNECTED else "UNAVAILABLE"

    banner = (
        "\n======================================================================\n"
        "  JARVIS SYSTEM CAPABILITIES STATUS (Honest Pre-Flight)\n"
        f"  Ollama:   {ollama_str}\n"
        f"  Gmail:    {gmail_str}\n"
        f"  Internet: {internet_str}\n"
        "======================================================================\n"
    )
    print(banner)
    return banner


@app.on_event("startup")
async def startup_event():
    print_honest_startup_banner()
    try:
        from jarvis.core.scheduler import proactive_scheduler
        proactive_scheduler.start()
    except Exception as e:
        logger.warning(f"Could not auto-start proactive scheduler on boot: {e}")
    try:
        from jarvis.services.full_autonomy import full_autonomy
        await full_autonomy.start()
    except Exception as e:
        logger.warning(f"Could not auto-start full autonomy service on boot: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from jarvis.core.scheduler import proactive_scheduler
        proactive_scheduler.stop()
    except Exception as e:
        logger.warning(f"Scheduler shutdown warning: {e}")

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
app.include_router(career_router)
app.include_router(assistants_router)
app.include_router(smart_home_router)
app.include_router(ops_router)
app.include_router(grok_router)
app.include_router(workforce_router)
app.include_router(workforce_router, prefix='/api/v1')
app.include_router(reflections_router)
app.include_router(ventures_router)
app.include_router(ventures_router, prefix="/api/v1")
app.include_router(gsoc_router)
app.include_router(gsoc_router, prefix="/api/v1")
app.include_router(opportunities_router)
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(autonomous_router)
app.include_router(autonomous_router, prefix="/api/v1")


@app.get("/scheduler/status", tags=["Autonomous Scheduler"])
def get_scheduler_status():
    from jarvis.core.scheduler import proactive_scheduler
    return proactive_scheduler.get_status()


@app.post("/scheduler/trigger/{job_id}", tags=["Autonomous Scheduler"])
async def trigger_scheduled_job(job_id: str):
    from jarvis.core.scheduler import proactive_scheduler
    try:
        res = await proactive_scheduler.trigger_job(job_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    """Serves the interactive Iron Man glassmorphic HUD dashboard."""
    if not DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="Dashboard UI file not found")
    return FileResponse(DASHBOARD_HTML)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MODEL ROUTER SPECIFIC APIS (Prompt Mandate)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


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
async def approve_expensive_call(
    approval: ExpensiveCallApproval,
    admin_user: str = Depends(verify_admin_user),
):
    """Authorizes an inference call that exceeds default per-task limits."""
    if not approval.approved:
        return {"status": "rejected", "task_id": approval.task_id}
    token, expiry = generate_expensive_call_token(
        task_id=approval.task_id,
        target_model=approval.target_model,
        user_id=admin_user,
    )
    return {
        "status": "approved",
        "task_id": approval.task_id,
        "target_model": approval.target_model,
        "authorized_by": admin_user,
        "token": token,
        "expires_at": expiry,
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CORE JARVIS CHAT & ORCHESTRATION APIS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class ChatRequest(BaseModel):
    query: str
    context: str = ""
    sensitivity_level: str = "medium"
    approval_token: Optional[str] = None


@app.post("/api/v1/chat")
async def chat_endpoint(req: ChatRequest):
    """Central natural language entry point."""
    result = await orchestrator.process_user_query(
        query=req.query, context=req.context, sensitivity_level=req.sensitivity_level, approval_token=req.approval_token
    )
    return result


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# JARVIS 355 POWER CATALOG & ECOSYSTEM (JARVIS = a + b + c ... n)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


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
            "local_path": f"repos/{r}",
        }
    return {
        "formula": power_registry.get_ecosystem_formula(),
        "total_powers": power_registry.total_count(),
        "total_repositories": len(repos),
        "repositories": breakdown,
    }


@app.get("/api/v1/powers")
async def list_powers(
    category: Optional[str] = None,
    repo: Optional[str] = None,
    q: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    """Lists JARVIS powers with optional filtering by category, contributing repo, or keyword search."""
    search_term = q or search
    if search_term:
        results = power_registry.search_powers(search_term, limit=limit or 50)
        return {"query": search_term, "total_matches": len(results), "powers": results}
    if repo:
        powers = power_registry.get_powers_by_repo(repo)
        paginated = powers[offset : offset + limit] if limit and limit > 0 else powers[offset:]
        return {
            "repo": repo,
            "total_powers": len(powers),
            "offset": offset,
            "limit": limit or len(powers),
            "powers": paginated,
        }
    if category:
        powers = power_registry.get_powers_by_category(category)
        paginated = powers[offset : offset + limit] if limit and limit > 0 else powers[offset:]
        return {
            "category": category,
            "total_powers": len(powers),
            "offset": offset,
            "limit": limit or len(powers),
            "powers": paginated,
        }

    all_powers = power_registry.list_all_powers()
    paginated = all_powers[offset : offset + limit] if limit and limit > 0 else all_powers[offset:]
    return {
        "total_powers": len(all_powers),
        "total_categories": len(power_registry.list_categories()),
        "ecosystem_formula": power_registry.get_ecosystem_formula(),
        "offset": offset,
        "limit": limit or len(all_powers),
        "powers": paginated,
    }


@app.get("/api/v1/powers/{power_id}")
async def get_power_detail(power_id: str):
    """Retrieves complete definition of a specific JARVIS power by ID or slug."""
    power = power_registry.get_power(power_id)
    if not power:
        raise HTTPException(status_code=404, detail=f"Power '{power_id}' not found")
    return power


@app.get("/api/v1/system/health")
async def system_health():
    """Authoritative, evidence-backed system health and host telemetry."""
    evidence_health = capability_guard.get_evidence_health_report()
    default_boot_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        host_metrics = it_admin_powers.system_health_report()
        boot_time = (
            host_metrics.get("boot_time")
            or host_metrics.get("system", {}).get("boot_time")
            or default_boot_time
        )
        evidence_health.update({
            "cpu": host_metrics.get("cpu", {}),
            "memory": host_metrics.get("memory", {}),
            "disk": host_metrics.get("disk", {}),
            "boot_time": boot_time,
            "host_status": host_metrics.get("status", "healthy"),
        })
        if host_metrics.get("status") == "critical":
            evidence_health["status"] = "critical"
        elif host_metrics.get("status") == "warning" and evidence_health.get("status") == "healthy":
            evidence_health["status"] = "degraded"
    except Exception as e:
        logger.warning(f"Could not gather host performance telemetry: {e}")
        evidence_health["boot_time"] = default_boot_time
        evidence_health["host_status"] = "degraded"
        evidence_health.setdefault("cpu", {})
        evidence_health.setdefault("memory", {})
        evidence_health.setdefault("disk", {})
    return evidence_health


@app.get("/api/v1/tasks")
async def list_tasks(limit: int = 50):
    """Inspects recent task state machine executions."""
    return db_store.list_tasks(limit=limit)


class ApprovalResolution(BaseModel):
    task_id: str
    approved: bool
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)


@app.post("/api/v1/approvals/{task_id}/resolve")
async def resolve_approval(
    task_id: str,
    resolution: ApprovalResolution,
    admin_user: str = Depends(verify_admin_user),
):
    """Submits authenticated human-in-the-loop decision for pending high-privilege actions."""
    if resolution.user_id and resolution.user_id.strip() != admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authorization failed: Resolution user '{resolution.user_id}' does not match authenticated admin '{admin_user}'",
        )

    pending = policy_gate.pending_approvals.get(task_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending approval found for this task")

    if not resolution.approved:
        policy_gate.pending_approvals.pop(task_id, None)
        return {"task_id": task_id, "status": "REJECTED"}

    token = pending.get("token")
    if not token:
        token, expiry = policy_gate.generate_approval_token(
            task_id=task_id,
            power_id=pending["power_id"],
            payload_hash=pending["payload_hash"],
            user_id=admin_user,
        )
        pending["token"] = token
        pending["expires_at"] = expiry

    pending["status"] = "APPROVED"
    pending["user_id"] = admin_user
    return {"task_id": task_id, "status": "APPROVED", "approval_token": token}


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
        "evidence": [],
    }

    final_state = get_jarvis_graph().invoke(
        initial_state,
        config={"configurable": {"thread_id": task_id}},
    )

    audit_ledger.record(
        actor=req.user_id,
        action="CHAT_REQUEST",
        target=final_state.get("model_route", "local"),
        payload={"task_id": task_id, "user_input": user_input},
        result="SUCCESS",
        task_id=task_id,
    )

    return {
        "task_id": final_state["task_id"],
        "user_id": final_state["user_id"],
        "response": final_state["final_response"],
        "reply": final_state["final_response"],
        "retrieved_memories": final_state["retrieved_memories"],
        "model_route": final_state["model_route"],
        "risk_level": final_state["risk_level"],
        "approval_required": final_state["approval_required"],
    }


@app.get("/health")
async def health_root():
    """Health check endpoint confirming Jarvis core services."""
    return {"status": "healthy", "service": "jarvis-core", "version": "1.0.0", "timestamp": time.time()}


class RootKillSwitchPayload(BaseModel):
    active: bool = True
    reason: str = "API trigger"


@app.post("/kill-switch")
@app.post("/api/v1/kill-switch")
async def toggle_kill_switch(
    payload: Optional[RootKillSwitchPayload] = None, active: bool = True, reason: str = "API trigger"
):
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
        "reason": switch_reason,
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
        "categories": power_registry.list_categories(),
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
    return {"total": len(entries), "entries": entries, "chain_integrity": chain_status}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# WEBSOCKET STREAM FOR IRON MAN HUD
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


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
                "timestamp": time.time(),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
