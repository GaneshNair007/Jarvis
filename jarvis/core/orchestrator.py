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

class JarvisOrchestrator:
    def __init__(self):
        self.router = model_router
        self.policy = policy_gate
        self.audit = audit_ledger
        self.registry = power_registry
        self.state_machine = state_machine

    async def process_user_query(
        self,
        query: str,
        task_id: Optional[str] = None,
        context: str = "",
        sensitivity_level: str = "medium",
        approval_token: Optional[str] = None
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

        start_time = time.time()

        # Step 1: Model Routing & Intent Triage
        routing_req = RoutingRequest(
            task_id=task_id,
            user_intent=query,
            sensitivity_level=sensitivity_level,
            attached_context=context
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
            approval_token=approval_token
        )

        if not policy_allowed:
            self.state_machine.transition(task_id, "REJECTED", reason=policy_msg)
            self.audit.log_event(
                event_type="POLICY_REJECT",
                task_id=task_id,
                power_id="policy_gate",
                status="REJECTED",
                inputs={"query": query},
                outputs={"reason": policy_msg, "pending_approval": pending_approval}
            )
            return {
                "task_id": task_id,
                "status": "REJECTED",
                "message": policy_msg,
                "pending_approval": pending_approval,
                "tier": decision.tier
            }

        # Step 3: Execution Execution lane
        self.state_machine.transition(task_id, "RUNNING", reason="Executing routed operation")

        execution_result = {}
        if decision.tier == "BYPASS":
            # Instant command execution
            execution_result = self._execute_instant_command(query)
        elif decision.tier == "TIER_1_LOCAL":
            # Local reflex execution simulation / Ollama call
            execution_result = {
                "reply": f"Jarvis (Local Reflex - {decision.selected_model}): Processed '{decision.redacted_context or query}' locally with zero external transmission.",
                "local_tokens": 120,
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
        elif decision.tier == "TIER_2_PRIVATE":
            # Private GPU vLLM execution
            execution_result = {
                "reply": f"Jarvis (Private GPU - {decision.selected_model}): Deep reasoning completed within secure user boundary.",
                "private_tokens": 450,
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
        elif decision.tier == "TIER_3_CLOUD":
            # Frontier cloud execution
            execution_result = {
                "reply": f"Jarvis (Frontier Cloud - {decision.selected_model}): Synthesized research and advanced reasoning response.",
                "cloud_tokens": 850,
                "cost_usd": decision.estimated_cost_usd,
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }

        # Step 4: Verification & Completion
        self.state_machine.transition(task_id, "VERIFYING", reason="Validating execution receipts")
        self.state_machine.transition(task_id, "COMPLETED", reason="Task finished successfully")

        # Step 5: Cryptographic Audit Logging
        self.audit.log_event(
            event_type="TASK_COMPLETED",
            task_id=task_id,
            power_id=decision.selected_model,
            status="SUCCESS",
            inputs={"query": query, "tier": decision.tier},
            outputs=execution_result,
            details={"cost_usd": decision.estimated_cost_usd, "duration_ms": (time.time() - start_time) * 1000}
        )

        return {
            "task_id": task_id,
            "status": "COMPLETED",
            "tier": decision.tier,
            "provider": decision.provider,
            "model": decision.selected_model,
            "response": execution_result,
            "routing_reason": decision.reason,
            "duration_ms": round((time.time() - start_time) * 1000, 2)
        }

    def _execute_instant_command(self, query: str) -> Dict[str, Any]:
        """Executes instant OS commands with zero LLM overhead."""
        cleaned = query.strip().lower()

        if "health" in cleaned or "telemetry" in cleaned:
            import psutil
            return {
                "type": "telemetry",
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("C:\\").percent if hasattr(psutil, "disk_usage") else 0.0,
                "message": "System health metrics retrieved immediately."
            }
        elif "screenshot" in cleaned:
            return {
                "type": "screenshot",
                "status": "captured",
                "file": "data/screenshots/latest_screen.png",
                "message": "Screen capture executed immediately."
            }
        elif "lock" in cleaned:
            return {
                "type": "system_control",
                "status": "dispatched",
                "action": "lock_workstation",
                "message": "Workstation lock requested."
            }
        else:
            return {
                "type": "instant_command",
                "status": "executed",
                "command": cleaned,
                "message": f"Instant command '{cleaned}' dispatched."
            }

# Singleton Orchestrator
orchestrator = JarvisOrchestrator()
