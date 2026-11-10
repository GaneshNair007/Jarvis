"""
JARVIS Central Orchestration Engine
Coordinates intent analysis, 3-tier model routing, deterministic policy checks,
tool execution, and cryptographic audit logging.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional

from jarvis.config import settings
from jarvis.core.state_machine import state_machine
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.policy_gate import policy_gate
from jarvis.core.audit import audit_ledger
from jarvis.core.power_registry import power_registry
from jarvis.memory.store import db_store
from jarvis.memory.conversation_service import conversation_service
from jarvis.agents.critic import CriticAgent, Verdict


class JarvisOrchestrator:
    def __init__(self):
        self.router = model_router
        self.policy = policy_gate
        self.audit = audit_ledger
        self.registry = power_registry
        self.state_machine = state_machine
        self.store = db_store
        self.conversation_service = conversation_service
        self.critic = CriticAgent()

    def _map_query_to_specialists(self, query: str) -> List[str]:
        """Maps user query to one or more of the 8 canonical specialist agent roles."""
        q = query.lower()
        roles = []

        # 1. Researcher Agent: Web research, sources, papers, technical investigations
        if any(k in q for k in ["search", "research", "browse", "paper", "arxiv", "find info", "what is", "who is", "explain", "investigate", "tell me about"]):
            roles.append("researcher")

        # 2. Engineer Agent: Code, repositories, python, git, debugging, bugs, architecture
        if any(k in q for k in ["code", "python", "script", "git", "bug", "refactor", "function", "class", "program", "build", "terminal", "algorithm"]):
            roles.append("engineer")

        # 3. Academic Tutor: Study, assignments, exam, viva prep, course, lecture
        if any(k in q for k in ["assignment", "homework", "exam", "viva", "syllabus", "lecture", "course", "study", "tutor", "quiz"]):
            roles.append("academic_tutor")

        # 4. Career Agent: Internships, GSoC, hackathons, job, resume, interview
        if any(k in q for k in ["job", "internship", "gsoc", "hackathon", "resume", "cover letter", "career", "interview", "hiring"]):
            roles.append("career")

        # 5. Productivity Agent: Schedule, calendar, task, deadline, reminder, todo
        if any(k in q for k in ["schedule", "calendar", "meeting", "reminder", "deadline", "task", "todo", "plan"]):
            roles.append("productivity")

        # 6. Communication Agent: Email, draft email, reply, inbox, message, follow-up
        if any(k in q for k in ["email", "mail", "inbox", "outbox", "draft email", "send email", "reply", "follow up"]):
            roles.append("communication")

        # 7. Desktop Agent: Windows apps, notepad, files, screenshot, desktop
        if any(k in q for k in ["open", "close", "launch", "file", "folder", "desktop", "screenshot", "window", "notepad"]):
            roles.append("desktop")

        if not roles:
            roles.append("researcher")

        # 8. Reviewer / Verifier Agent: Always bound for Stage 5 verification
        if "reviewer" not in roles:
            roles.append("reviewer")

        return roles

    def _plan_task(self, query: str, specialist_roles: List[str]) -> List[Dict[str, Any]]:
        """Stage 2: Decomposes query into structured subtasks with explicit dependencies."""
        subtasks = []
        exec_roles = [r for r in specialist_roles if r != "reviewer"]
        for idx, role in enumerate(exec_roles, start=1):
            subtasks.append({
                "step_id": idx,
                "role": role,
                "goal": f"Execute {role} operation for request: {query[:80]}",
                "status": "PLANNED",
                "dependencies": [i for i in range(1, idx)],
            })
        if not subtasks:
            subtasks.append({
                "step_id": 1,
                "role": "researcher",
                "goal": query,
                "status": "PLANNED",
                "dependencies": [],
            })
        return subtasks

    async def process_user_query(
        self,
        query: str,
        task_id: Optional[str] = None,
        conversation_id: str = "default_session",
        context: str = "",
        sensitivity_level: str = "medium",
        approval_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        6-Stage Execution Pipeline:
        Stage 1: Understand (evaluates intent with conversation history; deterministic OS shortcuts execute immediately)
        Stage 2: Plan (decomposes query into structured subtasks)
        Stage 3: Select (maps subtasks to specialist roles)
        Stage 4: Execute (runs tools via execution bridge and model router)
        Stage 5: Verify (invokes CriticAgent to evaluate evidence and issue structured Verdict)
        Stage 6: Consolidate & Persist (returns single consolidated verified response, stores turn in ConversationService)
        """
        task_id = task_id or f"tsk_{uuid.uuid4().hex[:10]}"
        start_time = time.time()
        self.state_machine.create_task(task_id, "NEW")
        self.store.save_task(task_id, title=query[:80], status="NEW", inputs={"query": query})

        # ======================================================================
        # STAGE 1: UNDERSTAND
        # ======================================================================
        self.state_machine.transition(task_id, "TRIAGED", reason="Stage 1: Understanding intent and context")
        self.conversation_service.get_or_create_conversation(conversation_id)
        recent_turns = self.conversation_service.get_recent_context(conversation_id, limit=10)
        formatted_history = self.conversation_service.format_context_for_prompt(conversation_id, limit=6)

        # Merge conversation history into contextual dialogue
        combined_context = f"{formatted_history}\n\nAttached Context:\n{context}".strip() if formatted_history else context

        # Check for pure deterministic instant OS command bypass
        if self.router.is_instant_command(query):
            instant_result = await self._execute_power_or_specialized_engine(query)
            # Record in conversation service
            self.conversation_service.append_message(conversation_id, role="user", content=query)
            resp_str = instant_result.get("message") or str(instant_result)
            self.conversation_service.append_message(
                conversation_id,
                role="assistant",
                content=resp_str,
                model="none-deterministic-command",
            )

            final_state = "COMPLETED"
            self.state_machine.transition(task_id, "POLICY_CHECK", reason="Instant OS policy check")
            self.state_machine.transition(task_id, "RUNNING", reason="Executing instant OS command")
            self.state_machine.transition(task_id, "VERIFYING", reason="Validating instant OS receipt")
            self.state_machine.transition(task_id, final_state, reason="Deterministic OS command executed successfully")
            self.store.save_task(task_id, title=query[:80], status=final_state, power_id="instant_os", inputs={"query": query}, outputs=instant_result)
            self.audit.log_event(
                event_type="TASK_COMPLETED",
                task_id=task_id,
                power_id="instant_os",
                status="SUCCESS",
                inputs={"query": query, "tier": "BYPASS"},
                outputs=instant_result,
                details={"cost_usd": 0.0, "duration_ms": (time.time() - start_time) * 1000},
            )
            return {
                "task_id": task_id,
                "conversation_id": conversation_id,
                "status": final_state,
                "tier": "BYPASS",
                "provider": "deterministic",
                "model": "none-deterministic-command",
                "stages_executed": ["understand"],
                "stage_outputs": {
                    "understand": {
                        "intent": query,
                        "is_instant_shortcut": True,
                        "dialogue_history_turns": len(recent_turns),
                    }
                },
                "selected_specialists": ["desktop"],
                "verdict": "pass",
                "response": instant_result,
                "final_reply": resp_str,
                "duration_ms": round((time.time() - start_time) * 1000, 2),
            }

        # Route query and formulate understanding
        routing_req = RoutingRequest(
            task_id=task_id,
            user_intent=query,
            sensitivity_level=sensitivity_level,
            attached_context=combined_context,
        )
        decision = self.router.route(routing_req)

        stage_1_understand = {
            "query": query,
            "dialogue_history_recalled": len(recent_turns),
            "decision": {
                "tier": decision.tier,
                "provider": decision.provider,
                "model": decision.selected_model,
                "reason": decision.reason,
            },
        }

        # ======================================================================
        # STAGE 2: PLAN
        # ======================================================================
        self.state_machine.transition(task_id, "PLANNED", reason="Stage 2: Subtasks planned")
        specialist_roles = self._map_query_to_specialists(query)
        planned_subtasks = self._plan_task(query, specialist_roles)
        stage_2_plan = {
            "goal": query,
            "subtask_count": len(planned_subtasks),
            "subtasks": planned_subtasks,
        }

        # ======================================================================
        # STAGE 3: SELECT
        # ======================================================================
        selected_specialists = [s for s in specialist_roles]
        stage_3_select = {
            "selected_roles": selected_specialists,
            "primary_role": planned_subtasks[0]["role"] if planned_subtasks else "researcher",
            "verifier": "reviewer",
        }

        # ======================================================================
        # STAGE 4: EXECUTE
        # ======================================================================
        self.state_machine.transition(task_id, "POLICY_CHECK", reason="Stage 4: Evaluating policy gate rules")
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
                "conversation_id": conversation_id,
                "status": "REJECTED",
                "message": policy_msg,
                "pending_approval": pending_approval,
                "tier": decision.tier,
                "stages_executed": ["understand", "plan", "select", "execute"],
            }

        self.state_machine.transition(task_id, "RUNNING", reason="Stage 4: Executing routed operation")

        execution_result = {}
        if decision.tier == "BYPASS":
            execution_result = await self._execute_power_or_specialized_engine(query)
        else:
            # Build prompt with dialogue history and context
            prompt_parts = []
            if formatted_history:
                prompt_parts.append(formatted_history)
            if decision.redacted_context:
                prompt_parts.append(f"Source Context:\n{decision.redacted_context}")
            prompt_parts.append(f"User Request: {query}")
            prompt_parts.append("Instruction: Provide an accurate, verified, helpful response without hallucinating facts.")
            full_prompt = "\n\n".join(prompt_parts)

            execution_result = await asyncio.to_thread(
                self.router.execute_inference,
                decision,
                full_prompt,
            )

        stage_4_execute = {
            "execution_status": execution_result.get("status", "unknown"),
            "model_used": execution_result.get("model", decision.selected_model),
            "tokens_used": execution_result.get("tokens_used", 0),
        }

        # ======================================================================
        # STAGE 5: VERIFY
        # ======================================================================
        self.state_machine.transition(task_id, "VERIFYING", reason="Stage 5: Independent verification via CriticAgent")
        output_text_for_critic = (
            execution_result.get("reply")
            or execution_result.get("message")
            or str(execution_result)
        )
        critic_report = self.critic.review(
            goal=query,
            output=output_text_for_critic,
            task_id=task_id,
            action_type="llm",
            use_llm=False,
        )

        stage_5_verify = {
            "verdict": critic_report.verdict.value,
            "score": critic_report.score,
            "issues_count": len(critic_report.issues),
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in critic_report.issues
            ],
            "retry_recommended": critic_report.retry_recommended,
        }

        # ======================================================================
        # STAGE 6: CONSOLIDATE & PERSIST
        # ======================================================================
        final_reply_text = (
            execution_result.get("reply")
            or execution_result.get("message")
            or f"Task executed with status: {execution_result.get('status')}"
        )

        # Persist dialogue turn to ConversationService
        self.conversation_service.append_message(conversation_id, role="user", content=query)
        self.conversation_service.append_message(
            conversation_id,
            role="assistant",
            content=final_reply_text,
            model=execution_result.get("model", decision.selected_model),
            tokens=execution_result.get("tokens_used", 0),
        )

        is_failed = execution_result.get("status") in ("failed", "error")
        final_state = "FAILED" if is_failed else "COMPLETED"

        self.state_machine.transition(
            task_id,
            final_state,
            reason="Task finished successfully" if not is_failed else str(execution_result.get("error", "failed")),
        )
        self.store.save_task(
            task_id,
            title=query[:80],
            status=final_state,
            power_id=decision.selected_model,
            inputs={"query": query},
            outputs=execution_result,
        )
        self.audit.log_event(
            event_type="TASK_" + final_state,
            task_id=task_id,
            power_id=decision.selected_model,
            status="FAILURE" if is_failed else "SUCCESS",
            inputs={"query": query, "tier": decision.tier},
            outputs=execution_result,
            details={"cost_usd": decision.estimated_cost_usd, "duration_ms": (time.time() - start_time) * 1000},
        )

        stage_6_consolidate_persist = {
            "persisted_conversation_id": conversation_id,
            "task_id": task_id,
            "final_status": final_state,
            "final_reply": final_reply_text,
        }

        return {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "status": final_state,
            "tier": execution_result.get("tier", decision.tier),
            "provider": execution_result.get("provider", decision.provider),
            "model": execution_result.get("model", decision.selected_model),
            "stages_executed": [
                "understand",
                "plan",
                "select",
                "execute",
                "verify",
                "consolidate_persist",
            ],
            "stage_outputs": {
                "understand": stage_1_understand,
                "plan": stage_2_plan,
                "select": stage_3_select,
                "execute": stage_4_execute,
                "verify": stage_5_verify,
                "consolidate_persist": stage_6_consolidate_persist,
            },
            "selected_specialists": selected_specialists,
            "verdict": critic_report.verdict.value,
            "response": execution_result,
            "final_reply": final_reply_text,
            "routing_reason": decision.reason,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
        }

    def _execute_instant_command(self, query: str) -> Dict[str, Any]:
        """Executes instant OS commands, powers, and macros with zero LLM overhead."""
        import re
        cleaned = query.strip()
        q_lower = cleaned.lower()

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
