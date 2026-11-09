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
from contextlib import asynccontextmanager
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
from jarvis.ops.process_registry import process_registry
from jarvis.powers.it_admin_powers import it_admin_powers
from jarvis.api.routes_voice import router as voice_router
from jarvis.api.routes_relay import router as relay_router
from jarvis.api.routes_browser import router as browser_router
from jarvis.api.routes_tasks import router as tasks_router
from jarvis.api.routes_memory import router as memory_router
from jarvis.api.routes_desktop import router as desktop_router
from jarvis.api.routes_integrations import router as integrations_router
from jarvis.api.routes_google import router as google_router
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
import uuid
from graph.jarvis_graph import get_jarvis_graph
from jarvis.powers.developer_powers import developer_powers
from jarvis.powers.productivity_powers import productivity_powers
from jarvis.powers.communication_powers import communication_powers
from jarvis.integrations.career_ops import career_ops_integration


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Register this API process in the validated lifecycle registry."""
    process_registry.register_current("api_server")
    try:
        yield
    finally:
        process_registry.release("api_server")


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
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
app.include_router(relay_router)
app.include_router(browser_router)
app.include_router(tasks_router)
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(memory_router)
app.include_router(memory_router, prefix="/api/v1")
app.include_router(desktop_router)
app.include_router(integrations_router)
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(google_router)
app.include_router(search_router)
app.include_router(search_router, prefix="/api/v1")
app.include_router(career_router)
app.include_router(assistants_router)
app.include_router(smart_home_router)
app.include_router(ops_router)
app.include_router(grok_router)
app.include_router(workforce_router)
app.include_router(workforce_router, prefix="/api/v1")
app.include_router(reflections_router)
app.include_router(ventures_router)
app.include_router(ventures_router, prefix="/api/v1")
app.include_router(gsoc_router)
app.include_router(gsoc_router, prefix="/api/v1")


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
async def approve_expensive_call(approval: ExpensiveCallApproval):
    """Authorizes an inference call that exceeds default per-task limits."""
    if not approval.approved:
        return {"status": "rejected", "task_id": approval.task_id}
    return {"status": "approved", "task_id": approval.task_id, "token": f"exp_app_{int(time.time())}"}


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
    """Live host telemetry."""
    return it_admin_powers.system_health_report()


@app.get("/api/v1/system/processes")
async def system_processes():
    """Validated lifecycle health for the API server, voice daemon and HUD.

    Status is derived from live OS process identity (PID + creation time +
    command line), not from configuration files or optimistic flags.
    """
    return process_registry.health()


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
    """Health check endpoint confirming Jarvis core services.

    ``processes`` reports the actual state of the API server, voice daemon and
    HUD so callers can distinguish "this HTTP endpoint answered" from "the
    whole local system is running".
    """
    return {
        "status": "healthy",
        "service": "jarvis-core",
        "version": "1.0.0",
        "timestamp": time.time(),
        "processes": process_registry.summary(),
    }


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


# ══════════════════════════════════════════════════════════════════════════════
# BLUEPRINT SECTION 22, 25 & PART B: PRODUCTIVITY, DEV, COMM & CAREER-OPS
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/v1/productivity/briefing")
async def get_daily_briefing():
    """PWR-009 / PWR-185: Morning and Daily briefing generation."""
    return productivity_powers.daily_briefing()


@app.get("/api/v1/productivity/tasks")
async def get_productivity_tasks():
    """PWR-010: Task manager - lists tracked tasks."""
    return productivity_powers.task_manager(action="list")


@app.post("/api/v1/productivity/tasks")
async def add_productivity_task(payload: Dict[str, Any] = Body(...)):
    """PWR-010: Task manager - creates new priority task."""
    title = payload.get("title", "")
    priority = payload.get("priority", "P1")
    return productivity_powers.task_manager(action="add", title=title, priority=priority)


@app.get("/api/v1/productivity/reminders")
async def get_productivity_reminders():
    """PWR-011: Reminder engine - lists active reminders."""
    return productivity_powers.reminder_engine(action="list")


@app.post("/api/v1/productivity/reminders")
async def add_productivity_reminder(payload: Dict[str, Any] = Body(...)):
    """PWR-011: Reminder engine - creates reminder."""
    text = payload.get("text", "")
    due = payload.get("due")
    return productivity_powers.reminder_engine(action="add", text=text, due=due)


@app.get("/api/v1/productivity/calendar")
async def get_productivity_calendar():
    """PWR-012: Calendar integration - lists upcoming schedule."""
    return productivity_powers.calendar_power(action="list")


@app.get("/api/v1/developer/explain")
async def explain_codebase(target_dir: str = "."):
    """PWR-162: Scans and explains repository code structure."""
    return developer_powers.explain_codebase(target_dir=target_dir)


@app.get("/api/v1/developer/git")
async def run_git_op(action: str = "status"):
    """PWR-173: Executes safe Git status, log, branch, or diff queries."""
    return developer_powers.git_operations(action=action)


@app.post("/api/v1/developer/diagnose")
async def diagnose_error(payload: Dict[str, Any] = Body(...)):
    """PWR-164: Parses stack trace and returns root cause triage."""
    trace = payload.get("stack_trace", "")
    return developer_powers.diagnose_bug(stack_trace=trace)


@app.get("/api/v1/developer/cicd")
async def get_cicd_status():
    """PWR-177: Inspects CI/CD workflows and verification status."""
    return developer_powers.ci_cd_monitoring()


@app.post("/api/v1/communication/draft")
async def draft_comm_message(payload: Dict[str, Any] = Body(...)):
    """PWR-209: Message drafting with frozen hash-bound approval."""
    channel = payload.get("channel", "email")
    recipient = payload.get("recipient", "")
    content = payload.get("content", "")
    subject = payload.get("subject")
    return communication_powers.draft_message(channel=channel, recipient=recipient, content=content, subject=subject)


@app.post("/api/v1/communication/telegram/alert")
async def send_telegram_alert(payload: Dict[str, Any] = Body(...)):
    """PWR-203: Telegram notifications and alerts."""
    text = payload.get("text", "")
    priority = payload.get("priority", "normal")
    return communication_powers.telegram_alert(text=text, priority=priority)


@app.post("/api/v1/communication/discord/notify")
async def send_discord_notify(payload: Dict[str, Any] = Body(...)):
    """PWR-204: Discord webhook notifications."""
    title = payload.get("title", "")
    desc = payload.get("description", "")
    return communication_powers.discord_notification(title=title, description=desc)


@app.post("/api/v1/career-ops/scan")
async def career_ops_scan(payload: Dict[str, Any] = Body(...)):
    """PWR-329: Career-Ops /job-scan <URL> with SSRF protection."""
    url = payload.get("job_url", "")
    return career_ops_integration.scan_job(job_url=url)


@app.post("/api/v1/career-ops/generate-resume")
async def career_ops_resume(payload: Dict[str, Any] = Body(...)):
    """PWR-330: Career-Ops /generate-resume <job-url> ATS-friendly PDF."""
    url = payload.get("job_url", "")
    return career_ops_integration.generate_resume(job_url=url)


@app.post("/api/v1/career-ops/generate-cover")
async def career_ops_cover(payload: Dict[str, Any] = Body(...)):
    """PWR-331: Career-Ops /generate-cover <job-url>."""
    url = payload.get("job_url", "")
    return career_ops_integration.generate_cover_letter(job_url=url)


@app.get("/api/v1/career-ops/company-research")
async def career_ops_company(company: str):
    """PWR-332: Career-Ops /company-research <company>."""
    return career_ops_integration.company_research(company=company)


@app.get("/api/v1/career-ops/find-contact")
async def career_ops_contact(company: str, role: str = "Recruiter"):
    """PWR-333: Career-Ops /find-contact <company> [role]."""
    return career_ops_integration.find_contact(company=company, role=role)


@app.get("/api/v1/career-ops/analyze-applications")
async def career_ops_analytics():
    """PWR-335: Career-Ops /analyze-applications."""
    return career_ops_integration.analyze_applications()


@app.post("/api/v1/career-ops/interview-prep")
async def career_ops_interview(payload: Dict[str, Any] = Body(...)):
    """PWR-336: Career-Ops /interview-prep [question]."""
    question = payload.get("question")
    return career_ops_integration.interview_prep(question=question)


@app.post("/api/v1/career-ops/analyze-offer")
async def career_ops_offer(payload: Dict[str, Any] = Body(...)):
    """PWR-337: Career-Ops /analyze-offer."""
    offer_text = payload.get("offer_text", "")
    target = payload.get("target_salary")
    return career_ops_integration.analyze_offer(offer_text=offer_text, target_salary=target)


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
