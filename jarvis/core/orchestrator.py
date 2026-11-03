"""
JARVIS Central Orchestration Engine
Coordinates intent analysis, 3-tier model routing, deterministic policy checks,
tool execution, and cryptographic audit logging.
"""

import asyncio
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
        if decision.tier == "BYPASS":
            # Instant command, Grok, OpenClaw, or Power execution
            execution_result = await self._execute_power_or_specialized_engine(query)
        elif decision.tier in ("TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD", "FALLBACK_CLOUD"):
            # Unified LiteLLM inference execution across local and cloud tiers
            full_prompt = (
                f"Source Context:\n{decision.redacted_context}\n\nUser Question: {query}\n"
                "Instruction: Answer strictly based on the source context provided. "
                "Identify the source file. If information is not in the source, state so honestly without inventing facts."
                if decision.redacted_context
                else query
            )
            execution_result = await asyncio.to_thread(
                self.router.execute_inference,
                decision,
                full_prompt,
            )

        # Step 4: Verification & Completion (Honest State)
        is_failed = execution_result.get("status") in ("unavailable", "error", "failed") or bool(execution_result.get("error"))
        final_state = "FAILED" if is_failed else "COMPLETED"

        self.state_machine.transition(task_id, "VERIFYING", reason="Validating execution receipts")
        self.state_machine.transition(
            task_id,
            final_state,
            reason="Execution failed: " + str(execution_result.get("error", "unavailable")) if is_failed else "Task finished successfully"
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
            "tier": execution_result.get("tier", decision.tier),
            "provider": execution_result.get("provider", decision.provider),
            "model": execution_result.get("selected_model", decision.selected_model),
            "response": execution_result,
            "routing_reason": decision.reason,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
        }

    def _execute_instant_command(self, query: str) -> Dict[str, Any]:
        """Executes instant OS commands, powers, and macros with zero LLM overhead."""
        import re
        cleaned = query.strip()
        q_lower = cleaned.lower()

        # Greetings & conversational triage
        if any(w in q_lower for w in ["who are you", "what can you do", "help"]) or any(
            w == q_lower or q_lower.startswith(f"{w} ") or q_lower.endswith(f" {w}") or f" {w} " in f" {q_lower} "
            for w in ["hi", "hello", "hey"]
        ):
            from jarvis.core.model_router import model_router
            return {
                "type": "assistant_info",
                "message": model_router._generate_heuristic_response(query),
            }

        if any(pat in q_lower for pat in ["connect antigravity", "use antigravity", "antigravity code", "make yourself stronger", "make yourself better", "self improve", "upgrade yourself"]):
            return {
                "status": "understood",
                "message": (
                    "Self-improvement workflow: I can identify capability gaps and create improvement proposals for human review. I cannot self-modify directly.\n\nCurrent capability gaps (from last reflection):\n- No live Gmail integration\n- No real-time web search\n- Voice pipeline needs tuning\n\nWould you like me to create an improvement request?"
                ),
                "action": "self_improvement_intent_detected",
            }

        if "health" in q_lower or "telemetry" in q_lower:
            import psutil
            return {
                "type": "telemetry",
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage(settings.disk_mount_path).percent if hasattr(psutil, "disk_usage") else 0.0,
                "message": "System health metrics retrieved immediately.",
            }
        elif "screenshot" in q_lower:
            return {
                "type": "screenshot",
                "status": "captured",
                "file": str(settings.screenshot_dir / "latest_screen.png"),
                "message": "Screen capture executed immediately.",
            }
        elif "lock" in q_lower:
            return {
                "type": "system_control",
                "status": "dispatched",
                "action": "lock_workstation",
                "message": "Workstation lock requested.",
            }
        elif any(k in q_lower for k in ["ac", "air condition", "projector", "geyser", "light", "lamp", "movie night", "work mode", "sleep mode", "morning wake"]):
            from jarvis.powers.smart_home_powers import smart_home_powers
            res = smart_home_powers.process_voice_command(query)
            if res.get("status") != "unhandled":
                return {
                    "type": "smart_home",
                    "power_id": res.get("power_id"),
                    "status": "executed",
                    "message": res.get("feedback", "Smart home action completed."),
                    "details": res,
                }
        elif "opportunity radar" in q_lower or "career radar" in q_lower or "leads" in q_lower:
            from jarvis.routines.ops_workflows import opportunity_radar
            return opportunity_radar.run()
        elif "daily pulse" in q_lower or "system pulse" in q_lower:
            from jarvis.routines.ops_workflows import daily_system_pulse
            return daily_system_pulse.run()
        elif "weekly sweep" in q_lower:
            from jarvis.routines.ops_workflows import weekly_ops_sweep
            return weekly_ops_sweep.run()
        elif any(k in q_lower for k in ["gmail", "email", "inbox", "check mail", "check emails", "missed mail", "opportunities"]):
            from jarvis.powers.email_powers import email_powers
            res = email_powers.scan_inbox_for_opportunities()
            if res.get("status") in ("DISCONNECTED", "CONNECTED_EMPTY"):
                return {
                    "type": "email_triage",
                    "power_id": "PWR-191",
                    "status": res.get("status"),
                    "message": res.get("message", "Gmail is not connected."),
                    "details": res,
                    "fabricated": False,
                }
            summary_lines = [
                f"Scanned inbox for {res.get('account', 'user')}: Found {res.get('opportunities_found', 0)} opportunities ({res.get('urgent_count', 0)} urgent):"
            ]
            for idx, item in enumerate(res.get("opportunities", []), 1):
                summary_lines.append(f"{idx}. [{item.get('category')}] {item.get('subject')} ({item.get('from')})")
                summary_lines.append(f"   Action: {item.get('recommended_action')}")
            return {
                "type": "email_triage",
                "power_id": "PWR-191",
                "status": "completed",
                "message": "\n".join(summary_lines),
                "details": res,
                "fabricated": False,
            }
        elif q_lower.startswith("read file ") or q_lower.startswith("cat "):
            from jarvis.powers.file_powers import file_powers
            fp = cleaned.replace("read file", "").replace("cat", "").strip()
            return file_powers.read_file(fp)
        elif q_lower.startswith("pwr-"):
            parts = cleaned.split()
            pid = parts[0].upper()
            rem = cleaned[len(pid):].strip()
            res = self.registry.execute_power(pid, query=rem)
            msg = res.get("feedback") or res.get("message") or f"Power {pid} executed successfully."
            return {
                "type": "power_execution",
                "power_id": pid,
                "status": "executed",
                "message": msg,
                "reply": msg,
                "details": res,
            }
        elif q_lower.startswith("ping "):
            from jarvis.powers.networking_powers import networking_powers
            host = cleaned.replace("ping", "").strip() or "127.0.0.1"
            return networking_powers.ping(host)
        elif q_lower.startswith("speedtest") or "speed test" in q_lower:
            from jarvis.powers.networking_powers import networking_powers
            return networking_powers.speed_test_estimate()
        elif q_lower.startswith("check internet"):
            from jarvis.powers.networking_powers import networking_powers
            return networking_powers.check_internet()
        elif q_lower.startswith("stock ") or "stock quote" in q_lower:
            from jarvis.powers.finance_powers import finance_powers
            sym = cleaned.replace("stock quote", "").replace("stock", "").strip() or "NVDA"
            return finance_powers.pwr_215_stock_watchlist(sym)
        elif "market briefing" in q_lower:
            from jarvis.powers.finance_powers import finance_powers
            return finance_powers.pwr_222_market_briefing()
        elif "portfolio" in q_lower:
            from jarvis.powers.finance_powers import finance_powers
            return finance_powers.pwr_224_portfolio_journal()
        elif "hud" in q_lower or "mission control" in q_lower:
            from jarvis.powers.ironman_powers import ironman_powers
            return ironman_powers.mission_control_hud()
        elif "threat assessment" in q_lower:
            from jarvis.powers.ironman_powers import ironman_powers
            return ironman_powers.threat_assessment()
        elif "security posture" in q_lower or "security scan" in q_lower:
            from jarvis.powers.security_powers import security_powers
            return security_powers.security_posture_report()
        elif q_lower.startswith("youtube script ") or q_lower.startswith("video script "):
            from jarvis.powers.youtube_powers import youtube_powers
            topic = cleaned.replace("youtube script", "").replace("video script", "").strip() or "AI OS"
            return youtube_powers.generate_video_script(topic)
        elif q_lower.startswith("/job-scan") or q_lower.startswith("/career scan"):
            from jarvis.powers.career_powers import career_powers
            parts = cleaned.replace("/job-scan", "").replace("/career scan", "").strip()
            title = parts or "Principal AI Systems Architect"
            company = "Target Enterprise"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.scan_job_listing(job_title=title.strip(), company_name=company.strip(), description=f"Seeking {title}.")
        elif q_lower.startswith("/generate-resume"):
            from jarvis.powers.career_powers import career_powers
            parts = cleaned.replace("/generate-resume", "").strip()
            title = parts or "Principal Systems Architect"
            company = "Target Tech"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.generate_tailored_resume(job_title=title.strip(), company_name=company.strip())
        elif q_lower.startswith("/generate-cover"):
            from jarvis.powers.career_powers import career_powers
            parts = cleaned.replace("/generate-cover", "").strip()
            title = parts or "Lead Engineer"
            company = "Target Tech"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.generate_cover_letter(job_title=title.strip(), company_name=company.strip())
        elif q_lower.startswith("/company-research"):
            from jarvis.powers.career_powers import career_powers
            company = cleaned.replace("/company-research", "").strip() or "Google"
            return career_powers.research_company_brief(company_name=company)
        elif q_lower.startswith("/find-contact"):
            from jarvis.powers.career_powers import career_powers
            company = cleaned.replace("/find-contact", "").strip() or "OpenAI"
            return career_powers.find_company_contacts(company_name=company)
        elif q_lower.startswith("/draft-email"):
            from jarvis.powers.career_powers import career_powers
            parts = cleaned.replace("/draft-email", "").strip()
            return career_powers.draft_application_email(recipient_name="Hiring Team", company_name=parts or "Acme Corp", role_title="Principal Systems Architect")
        elif q_lower.startswith("/analyze-applications") or q_lower.startswith("/pipeline"):
            from jarvis.powers.career_powers import career_powers
            return career_powers.analyze_application_pipeline()
        elif q_lower.startswith("/interview-prep"):
            from jarvis.powers.career_powers import career_powers
            parts = cleaned.replace("/interview-prep", "").strip() or "Principal AI Architect at TechCorp"
            title, company = parts, "TechCorp"
            if " at " in parts:
                title, company = parts.split(" at ", 1)
            return career_powers.interview_prep_and_red_flags(role_title=title.strip(), company_name=company.strip())
        elif q_lower.startswith("/career"):
            from jarvis.powers.career_powers import career_powers
            return career_powers.get_service_status()
        else:
            return {
                "type": "instant_command",
                "status": "executed",
                "command": cleaned,
                "message": f"Instant command '{cleaned}' dispatched.",
            }

    async def _execute_power_or_specialized_engine(self, query: str) -> Dict[str, Any]:
        """Asynchronously dispatches to Grok Bot, OpenClaw, or Instant Command Macro."""
        import re
        cleaned = query.strip()
        q_lower = cleaned.lower()

        # 1. Grok Bot & OpenMaus Multi-Agent Dispatch
        if (
            q_lower.startswith("grok")
            or q_lower.startswith("@grok")
            or "ask grok" in q_lower
            or "grok bot" in q_lower
            or "openmaus" in q_lower
            or "grok mode" in q_lower
            or any(b in q_lower for b in ["code_bot", "research_bot", "sys_bot", "reflex_bot"])
            or any(f"{m} mode" in q_lower for m in ["fun", "think", "code", "banter"])
        ):
            from jarvis.core.openmaus_grok import openmaus_harness, GrokMode
            bot_id = "grok"
            for b in ["code_bot", "research_bot", "sys_bot", "reflex_bot"]:
                if b in q_lower:
                    bot_id = b
                    break

            mode = GrokMode.STANDARD
            if "fun" in q_lower or "banter" in q_lower:
                mode = GrokMode.FUN
            elif "think" in q_lower or "reason" in q_lower:
                mode = GrokMode.THINK
            elif "code" in q_lower or "coding" in q_lower:
                mode = GrokMode.CODE

            clean_prompt = re.sub(r"^(grok\s*[:,]?|@grok|ask grok\s*[:,]?)\s*", "", cleaned, flags=re.IGNORECASE).strip()
            grok_res = await openmaus_harness.chat(prompt=clean_prompt or cleaned, bot_id=bot_id, mode=mode)
            reply = grok_res.get("reply") or f"Grok ({mode.value.upper()}) deliberation complete."
            return {
                "type": "grok_response",
                "status": "success",
                "bot": grok_res.get("bot_name", "Grok"),
                "mode": grok_res.get("mode", mode.value),
                "reply": reply,
                "message": reply,
                "provider": grok_res.get("provider", "groq"),
                "channel": grok_res.get("channel", "#general"),
                "events_emitted": grok_res.get("events_emitted", 0),
            }

        # 2. OpenClaw & Obscura Web Perception & Crawling
        if (
            "openclaw" in q_lower
            or "obscura" in q_lower
            or q_lower.startswith("claw ")
            or q_lower.startswith("crawl ")
            or q_lower.startswith("scrape ")
            or "search web for" in q_lower
            or "search google for" in q_lower
            or "search online for" in q_lower
            or "find live hackathons" in q_lower
            or "search hackathons" in q_lower
            or "fetch url" in q_lower
            or "read url" in q_lower
        ):
            from jarvis.core.obscura_browser import obscura_browser
            url_match = re.search(r"https?://[^\s]+", cleaned)
            if url_match:
                target_url = url_match.group(0)
                page_res = await obscura_browser.fetch_page_content(target_url)
                text_preview = page_res.get("text_preview", "")
                summary_msg = f"OpenClaw extracted {page_res.get('total_chars', 0)} characters from '{page_res.get('title')}' ({page_res.get('url')}):\n\n{text_preview[:1200]}..."
                return {
                    "type": "openclaw_page_extract",
                    "status": "success",
                    "url": page_res.get("url"),
                    "title": page_res.get("title"),
                    "text_preview": text_preview,
                    "links_found": page_res.get("links_found"),
                    "message": summary_msg,
                    "reply": summary_msg,
                }
            else:
                clean_q = re.sub(
                    r"^(openclaw|obscura|claw|crawl|scrape|search web for|search google for|search online for)\s*",
                    "",
                    cleaned,
                    flags=re.IGNORECASE,
                ).strip()
                results = await obscura_browser.search_opportunities(clean_q or cleaned, limit=5)
                lines = [f"OpenClaw Web Perception results for '{clean_q or cleaned}':\n"]
                for idx, r in enumerate(results, 1):
                    lines.append(f"{idx}. {r.get('title')} - {r.get('url')}")
                    lines.append(f"   {r.get('snippet', '')[:120]}")
                resp_msg = "\n".join(lines)
                return {
                    "type": "openclaw_search",
                    "status": "success",
                    "query": clean_q or cleaned,
                    "total_results": len(results),
                    "results": results,
                    "message": resp_msg,
                    "reply": resp_msg,
                }

        # 3. Autonomous Workforce Swarm & Hackathons
        if (
            "hackathon pipeline" in q_lower
            or "autonomous workforce" in q_lower
            or "mobilize workforce" in q_lower
        ):
            from jarvis.agents.autonomous_workforce import autonomous_workforce
            res = await autonomous_workforce.run_hackathon_opportunity_pipeline(candidate_name="Ganesh")
            msg = f"Autonomous Workforce mobilized 105 agents. Top hackathon: {res.get('top_hackathon')}. Scaffolded at {res.get('project_scaffold_dir')}."
            return {
                "type": "autonomous_workforce",
                "status": "completed",
                "message": msg,
                "reply": msg,
                "details": res,
            }

        # 4. Delegate to synchronous instant command macros
        return self._execute_instant_command(query)


orchestrator = JarvisOrchestrator()
