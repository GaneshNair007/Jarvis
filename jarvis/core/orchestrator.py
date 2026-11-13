"""
JARVIS Central Orchestration Engine
Coordinates intent analysis, 3-tier model routing, deterministic policy checks,
tool execution, and cryptographic audit logging.
"""

import time
import uuid
from typing import Dict, Any, Optional

from jarvis.config import settings
from jarvis.core.state_machine import state_machine
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.policy_gate import policy_gate
from jarvis.core.audit import audit_ledger
from jarvis.core.power_registry import power_registry
from jarvis.memory.store import db_store


class JarvisOrchestrator:
    def __init__(self):
        self.router = model_router
        self.policy = policy_gate
        self.audit = audit_ledger
        self.registry = power_registry
        self.state_machine = state_machine
        self.store = db_store

    async def process_user_query(
        self,
        query: str,
        task_id: Optional[str] = None,
        context: str = "",
        sensitivity_level: str = "medium",
        approval_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        End-to-End Orchestration Loop:
        1. Initialize Task State (NEW)
        2. Triage & Route via 3-Tier Model Router (TRIAGED)
        3. Deterministic Policy Check (POLICY_CHECK)
        4. Execute Worker / LLM Reasoning (RUNNING)
        5. Verify Outcome (VERIFYING)
        6. Cryptographic Audit Log & State Completion (COMPLETED)
        """
        task_id = task_id or f"tsk_{uuid.uuid4().hex[:10]}"
        self.state_machine.create_task(task_id, "NEW")
        self.store.save_task(task_id, title=query[:80], status="NEW", inputs={"query": query})

        start_time = time.time()

        # Step 1: Model Routing & Intent Triage
        routing_req = RoutingRequest(
            task_id=task_id, user_intent=query, sensitivity_level=sensitivity_level, attached_context=context
        )
        decision = self.router.route(routing_req)
        self.state_machine.transition(task_id, "TRIAGED", reason=f"Routed to {decision.tier} ({decision.provider})")

        # Step 2: Policy & Approval Gate
        self.state_machine.transition(task_id, "POLICY_CHECK", reason="Evaluating policy gate rules")
        privilege_level = 0 if decision.tier == "BYPASS" else (1 if decision.tier == "TIER_1_LOCAL" else 2)
        policy_allowed, policy_msg, pending_approval = self.policy.evaluate_execution(
            task_id=task_id,
            power_id=decision.selected_model,
            privilege_level=privilege_level,
            payload={"query": query, "model": decision.selected_model},
            approval_token=approval_token,
        )

        if not policy_allowed:
            self.state_machine.transition(task_id, "REJECTED", reason=policy_msg)
            self.store.save_task(
                task_id,
                title=query[:80],
                status="REJECTED",
                power_id="policy_gate",
                inputs={"query": query},
                outputs={"reason": policy_msg},
            )
            self.audit.log_event(
                event_type="POLICY_REJECT",
                task_id=task_id,
                power_id="policy_gate",
                status="REJECTED",
                inputs={"query": query},
                outputs={"reason": policy_msg, "pending_approval": pending_approval},
            )
            return {
                "task_id": task_id,
                "status": "REJECTED",
                "message": policy_msg,
                "pending_approval": pending_approval,
                "tier": decision.tier,
            }

        # Step 3: Execution Execution lane
        self.state_machine.transition(task_id, "RUNNING", reason="Executing routed operation")

        execution_result = {}

        # Code and self-improvement tasks dispatch through the multi-agent swarm
        # (checked before LLM tiers so /code and /upgrade always reach subagents).
        lowered_query = query.strip().lower()
        if lowered_query.startswith("/code") or lowered_query.startswith(
            ("write code", "generate code", "implement code", "create code")
        ):
            from jarvis.powers.multiagent_powers import multiagent_powers

            execution_result = multiagent_powers.orchestrator_dispatch(f"Code: {query}")
        elif lowered_query.startswith("/upgrade") or lowered_query.startswith("self improve"):
            from jarvis.powers.multiagent_powers import multiagent_powers

            execution_result = multiagent_powers.self_upgrade_pipeline()
        elif decision.tier == "BYPASS":
            # Instant command execution
            execution_result = self._execute_instant_command(query)
        elif decision.tier in ("TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD"):
            # Unified LiteLLM inference execution across local and cloud tiers
            full_prompt = (
                f"Source Context:\n{decision.redacted_context}\n\nUser Question: {query}\n"
                "Instruction: Answer strictly based on the source context provided. "
                "Identify the source file. If information is not in the source, state so honestly without inventing facts."
                if decision.redacted_context
                else query
            )
            execution_result = self.router.execute_inference(
                decision=decision,
                prompt=full_prompt,
            )
        else:
            execution_result = {"note": "No matching execution path, returning empty result"}

        # Step 4: Verification & Completion (Honest State)
        if not isinstance(execution_result, dict):
            execution_result = {
                "status": "error",
                "error": "INVALID_EXECUTION_RECEIPT",
                "message": "The execution handler returned a non-object result.",
            }
        execution_status = str(execution_result.get("status", "")).strip().lower()
        failure_states = {
            "unavailable",
            "error",
            "failed",
            "unhandled",
            "unrecognized",
            "rejected",
            "dispatched",
            "not_sent",
            "not_configured",
            "failed_verification",
        }
        is_failed = execution_status in failure_states or bool(execution_result.get("error"))
        final_state = "FAILED" if is_failed else "COMPLETED"

        self.state_machine.transition(task_id, "VERIFYING", reason="Validating execution receipts")
        self.state_machine.transition(
            task_id,
            final_state,
            reason="Execution failed: " + str(execution_result.get("error", "unavailable"))
            if is_failed
            else "Task finished successfully",
        )
        self.store.save_task(
            task_id,
            title=query[:80],
            status=final_state,
            power_id=decision.selected_model,
            inputs={"query": query},
            outputs=execution_result,
        )

        # Step 5: Cryptographic Audit Logging
        self.audit.log_event(
            event_type="TASK_" + final_state,
            task_id=task_id,
            power_id=decision.selected_model,
            status="FAILURE" if is_failed else "SUCCESS",
            inputs={"query": query, "tier": decision.tier},
            outputs=execution_result,
            details={"cost_usd": decision.estimated_cost_usd, "duration_ms": (time.time() - start_time) * 1000},
        )

        return {
            "task_id": task_id,
            "status": final_state,
            "tier": decision.tier,
            "provider": decision.provider,
            "model": decision.selected_model,
            "response": execution_result,
            "routing_reason": decision.reason,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
        }

    def _execute_instant_command(self, query: str) -> Dict[str, Any]:
        """Executes instant OS commands with zero LLM overhead."""
        cleaned = query.strip().lower()

        if cleaned in {"/brief", "/due", "/quest"}:
            from jarvis.workspace.service import workspace_service

            briefing = workspace_service.daily_briefing(horizon_days=365 if cleaned == "/due" else 7)
            if cleaned == "/brief":
                summary = briefing["summary"]
                message = (
                    f"You have {summary['open_tasks']} open tasks, "
                    f"{summary['open_assignments']} open assignments, "
                    f"{summary['overdue_items']} overdue items, and "
                    f"{summary['due_today']} items due today."
                )
                return {
                    "type": "workspace_briefing",
                    "status": "completed",
                    "message": message,
                    "details": briefing,
                }
            if cleaned == "/due":
                due_items = [item for item in briefing["next_actions"] if item.get("due_at")]
                return {
                    "type": "workspace_deadlines",
                    "status": "completed",
                    "message": f"Found {len(due_items)} stored items with deadlines in the selected horizon.",
                    "items": due_items,
                    "horizon_days": 365,
                }
            return {
                "type": "workspace_quest",
                "status": "completed",
                "message": "Today's focus is ranked from your saved deadlines and priorities.",
                "quests": briefing["next_actions"][:3],
                "active_goals": briefing["active_goals"],
            }
        elif cleaned.startswith("/capture"):
            from jarvis.workspace.service import workspace_service

            parts = query.strip().split(None, 2)
            if len(parts) != 3:
                return {
                    "type": "workspace_capture",
                    "status": "error",
                    "error": "CAPTURE_USAGE",
                    "message": "Usage: /capture note|fact|idea|task <content>",
                }
            capture = workspace_service.create_capture(
                kind=parts[1].lower(),
                content=parts[2],
                source="chat",
            )
            return {
                "type": "workspace_capture",
                "status": "completed",
                "capture_status": "pending_review",
                "message": "Capture saved to your review inbox. It has not been added to memory yet.",
                "capture": capture,
            }
        elif "health" in cleaned or "telemetry" in cleaned:
            import psutil

            return {
                "type": "telemetry",
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage(settings.disk_mount_path).percent
                if hasattr(psutil, "disk_usage")
                else 0.0,
                "message": "System health metrics retrieved immediately.",
            }
        elif "screenshot" in cleaned:
            from jarvis.powers.screen_powers import screen_powers

            capture = screen_powers.capture_region()
            if capture.get("status") != "success":
                return {
                    "type": "screenshot",
                    "status": capture.get("status", "unavailable"),
                    "error": capture.get("message", "Screen capture did not return a success receipt."),
                    "details": capture,
                }
            return {
                "type": "screenshot",
                "status": "success",
                "file": capture.get("path"),
                "sha256": capture.get("sha256"),
                "message": "Screenshot captured and verified on disk.",
                "details": capture,
            }
        elif "lock" in cleaned:
            import ctypes
            import os

            if os.name != "nt":
                return {
                    "type": "system_control",
                    "status": "unavailable",
                    "error": "UNSUPPORTED_PLATFORM",
                    "message": "Workstation locking is only implemented on Windows.",
                }
            try:
                locked = bool(ctypes.windll.user32.LockWorkStation())
            except (AttributeError, OSError) as exc:
                return {
                    "type": "system_control",
                    "status": "error",
                    "error": str(exc),
                    "message": "Windows did not accept the workstation lock request.",
                }
            if not locked:
                return {
                    "type": "system_control",
                    "status": "error",
                    "error": "LOCK_REQUEST_REJECTED",
                    "message": "Windows rejected the workstation lock request.",
                }
            return {
                "type": "system_control",
                "status": "success",
                "action": "lock_workstation",
                "message": "Windows accepted the workstation lock request.",
            }
        elif (
            "ac" in cleaned.split()
            or any(
                phrase in cleaned
                for phrase in [
                    "air condition",
                    "air conditioning",
                    "air conditioner",
                    "aircon",
                    "movie night",
                    "work mode",
                    "sleep mode",
                    "morning wake",
                ]
            )
            or bool({"projector", "tv", "television", "geyser", "light", "lights", "lamp"} & set(cleaned.split()))
        ):
            # SmartHomePowers currently maintains an in-memory demo state, not a
            # verified physical BroadLink/Home Assistant adapter.
            return {
                "type": "smart_home",
                "status": "unavailable",
                "error": "NO_VERIFIED_DEVICE_CONTROLLER",
                "message": (
                    "No verified physical smart-home controller is connected. "
                    "The local demo device-state store was not used; no device was changed."
                ),
            }
        elif "opportunity radar" in cleaned or "career radar" in cleaned or "leads" in cleaned:
            from jarvis.routines.ops_workflows import opportunity_radar

            return opportunity_radar.run()
        elif "daily pulse" in cleaned or "system pulse" in cleaned:
            from jarvis.routines.ops_workflows import daily_system_pulse

            return daily_system_pulse.run()
        elif "weekly sweep" in cleaned:
            from jarvis.routines.ops_workflows import weekly_ops_sweep

            return weekly_ops_sweep.run()
        elif any(k in cleaned for k in ["gmail", "email", "inbox", "check mail", "check emails", "missed mail"]):
            from jarvis.powers.email_powers import email_powers

            res = email_powers.scan_inbox_for_opportunities()
            live_sync = bool(res.get("live_sync_active"))
            if live_sync:
                source_note = "Connected Gmail inbox scanned through OAuth 2.0."
                execution_scope = "gmail_oauth"
            else:
                source_note = (
                    "Gmail is not connected. Only the local data/inbox/*.eml folder was checked; "
                    "no Gmail messages were fetched. " + str(res.get("setup_note", ""))
                )
                execution_scope = "local_inbox_only"
            summary_lines = [
                source_note,
                f"Found {res['opportunities_found']} locally available opportunities ({res['urgent_count']} urgent):",
            ]
            for idx, item in enumerate(res["opportunities"], 1):
                summary_lines.append(f"{idx}. [{item['category']}] {item['subject']} ({item['from']})")
                summary_lines.append(f"   Action: {item['recommended_action']}")

            return {
                "type": "email_triage",
                "power_id": "PWR-191",
                "status": "completed" if live_sync else "completed_local_only",
                "execution_scope": execution_scope,
                "live_sync_active": live_sync,
                "source": res.get("source"),
                "message": "\n".join(summary_lines),
                "details": res,
            }
        elif cleaned.startswith("read file ") or cleaned.startswith("cat "):
            from jarvis.powers.file_powers import file_powers

            fp = cleaned.replace("read file", "").replace("cat", "").strip()
            return file_powers.read_file(fp)
        elif cleaned.startswith("pwr-"):
            # Direct power invocation
            parts = cleaned.split()
            pid = parts[0].upper()
            return self.registry.execute_power(pid)
        elif cleaned.startswith("ping "):
            from jarvis.powers.networking_powers import networking_powers

            host = cleaned.replace("ping", "").strip() or "127.0.0.1"
            return networking_powers.ping(host)
        elif cleaned.startswith("speedtest") or "speed test" in cleaned:
            from jarvis.powers.networking_powers import networking_powers

            return networking_powers.speed_test_estimate()
        elif cleaned.startswith("check internet"):
            from jarvis.powers.networking_powers import networking_powers

            return networking_powers.check_internet()
        elif cleaned.startswith("stock ") or "stock quote" in cleaned:
            from jarvis.powers.finance_powers import finance_powers

            sym = cleaned.replace("stock quote", "").replace("stock", "").strip() or "NVDA"
            return finance_powers.pwr_215_stock_watchlist(sym)
        elif "market briefing" in cleaned:
            from jarvis.powers.finance_powers import finance_powers

            return finance_powers.pwr_222_market_briefing()
        elif "portfolio" in cleaned:
            from jarvis.powers.finance_powers import finance_powers

            return finance_powers.pwr_224_portfolio_journal()
        elif "hud" in cleaned or "mission control" in cleaned:
            from jarvis.powers.ironman_powers import ironman_powers

            return ironman_powers.mission_control_hud()
        elif "threat assessment" in cleaned:
            from jarvis.powers.ironman_powers import ironman_powers

            return ironman_powers.threat_assessment()
        elif "security posture" in cleaned or "security scan" in cleaned:
            from jarvis.powers.security_powers import security_powers

            return security_powers.security_posture_report()
        elif cleaned.startswith("youtube script ") or cleaned.startswith("video script "):
            from jarvis.powers.youtube_powers import youtube_powers

            topic = cleaned.replace("youtube script", "").replace("video script", "").strip() or "AI OS"
            return youtube_powers.generate_video_script(topic)
        elif any(w in cleaned for w in ["who are you", "what can you do", "help"]):
            from jarvis.core.model_router import model_router

            return {
                "type": "assistant_info",
                "message": model_router._generate_heuristic_response(query),
            }
        elif (
            any(action in cleaned for action in ["find ", "search ", "look for", "get me", "give me", "show me", "looking for"])
            and any(topic in cleaned for topic in ["opportunit", "internship", "hackathon", " job", "jobs", "scholarship"])
        ):
            from jarvis.powers.browser_powers import browser_powers

            result = browser_powers.search_web(query, max_results=8)
            if result.get("status") != "completed":
                return {
                    "type": "opportunity_search",
                    "status": "unavailable",
                    "error": "LIVE_SEARCH_UNAVAILABLE",
                    "message": (
                        "Live web search returned no usable sources. No openings were inferred from "
                        "the local saved-pipeline data."
                    ),
                    "details": result,
                }
            return {
                "type": "opportunity_search",
                "status": "completed",
                "source": "live_duckduckgo_search",
                "message": (
                    f"Live search returned {result['results_count']} source links. "
                    "These are discovery results, not verified openings or confirmed deadlines."
                ),
                "query": query,
                "results": result["results"],
            }
        elif cleaned.startswith("search ") or "web search" in cleaned:
            from jarvis.powers.browser_powers import browser_powers

            q = cleaned.replace("web search", "").replace("search", "").strip()
            return browser_powers.search_web(q or query)
        elif cleaned.startswith("research ") or "deep research" in cleaned:
            from jarvis.powers.browser_powers import browser_powers

            topic = cleaned.replace("deep research", "").replace("research", "").strip()
            return browser_powers.deep_research(topic or query)
        elif cleaned.startswith("read url ") or (cleaned.startswith("http://") or cleaned.startswith("https://")):
            from jarvis.powers.browser_powers import browser_powers

            url = query.replace("read url", "").strip()
            return browser_powers.read_url(url)
        elif cleaned.startswith("/job-scan") or cleaned.startswith("/career scan"):
            from jarvis.powers.career_powers import career_powers

            parts = query.replace("/job-scan", "").replace("/career scan", "").strip()
            title = parts or "Principal AI Systems Architect"
            company = "Target Enterprise"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.scan_job_listing(
                job_title=title.strip(),
                company_name=company.strip(),
                description=f"Seeking {title} experienced in distributed systems, async python, and search engines.",
            )
        elif cleaned.startswith("/generate-resume") or cleaned.startswith("/career resume"):
            from jarvis.powers.career_powers import career_powers

            parts = query.replace("/generate-resume", "").replace("/career resume", "").strip()
            title = parts or "Principal Systems Architect"
            company = "Target Tech"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.generate_tailored_resume(job_title=title.strip(), company_name=company.strip())
        elif cleaned.startswith("/generate-cover") or cleaned.startswith("/career cover"):
            from jarvis.powers.career_powers import career_powers

            parts = query.replace("/generate-cover", "").replace("/career cover", "").strip()
            title = parts or "Lead Engineer"
            company = "Target Tech"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.generate_cover_letter(job_title=title.strip(), company_name=company.strip())
        elif cleaned.startswith("/company-research"):
            from jarvis.powers.career_powers import career_powers

            company = query.replace("/company-research", "").strip() or "Google"
            return career_powers.research_company_brief(company_name=company)
        elif cleaned.startswith("/find-contact"):
            from jarvis.powers.career_powers import career_powers

            company = query.replace("/find-contact", "").strip() or "OpenAI"
            return career_powers.find_company_contacts(company_name=company)
        elif cleaned.startswith("/draft-email"):
            from jarvis.powers.career_powers import career_powers

            parts = query.replace("/draft-email", "").strip()
            return career_powers.draft_application_email(
                recipient_name="Hiring Team",
                company_name=parts or "Acme Corp",
                role_title="Principal Systems Architect",
            )
        elif cleaned.startswith("/analyze-applications") or cleaned.startswith("/pipeline"):
            from jarvis.powers.career_powers import career_powers

            return career_powers.analyze_application_pipeline()
        elif cleaned.startswith("/interview-prep"):
            from jarvis.powers.career_powers import career_powers

            parts = query.replace("/interview-prep", "").strip() or "Principal AI Architect at TechCorp"
            title, company = parts, "TechCorp"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.interview_prep_and_red_flags(role_title=title.strip(), company_name=company.strip())
        elif cleaned.startswith("/red-flags"):
            from jarvis.powers.career_powers import career_powers

            company = query.replace("/red-flags", "").strip() or "Startup Inc"
            return career_powers.interview_prep_and_red_flags(
                role_title="Engineer",
                company_name=company,
                job_description="Fast-paced environment wearing many hats, rockstar required.",
            )
        elif cleaned.startswith("/analyze-offer"):
            from jarvis.powers.career_powers import career_powers

            return career_powers.analyze_offer_and_salary_gap(
                company_name="InnovateAI",
                role_title="Principal AI Architect",
                base_salary=240000.0,
                bonus=35000.0,
                equity_annual_val=80000.0,
            )
        elif cleaned.startswith("/career"):
            from jarvis.powers.career_powers import career_powers

            return career_powers.get_service_status()
        else:
            return {
                "type": "instant_command",
                "status": "unavailable",
                "error": "NO_HANDLER",
                "command": cleaned,
                "message": (
                    f"No execution handler is registered for '{cleaned}'. "
                    "No action was run; JARVIS will not report a dispatch as success."
                ),
            }


# Singleton Orchestrator
orchestrator = JarvisOrchestrator()
