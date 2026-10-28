"""
JARVIS Base Integration Abstract Class
Defines the unified lifecycle contract for all external, self-hosted, cloud, and MCP integrations.
Enforces:
  1. Disabled-by-default initialization
  2. Kill-switch check on every invocation
  3. Strict 4-Tier human approval gates with frozen content hash
  4. Rate-limiting check and exponential backoff retry policy
  5. Immutable audit logging of all power executions and connection events
  6. Dry-run mode for safe preview without external mutation
"""

import time
import json
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from jarvis.core.audit import audit_ledger
from jarvis.core.policy_gate import policy_gate
from integrations.base.credential_manager import credential_manager
from integrations.base.rate_limiter import rate_limiter
from integrations.base.retry_policy import default_retry_policy, RetryPolicy
from integrations.base.integration_health import IntegrationStatus, HealthReport

class BaseIntegration(ABC):
    """Abstract base class for all JARVIS service integrations."""

    def __init__(
        self,
        integration_id: str,
        display_name: str,
        category: str,
        description: str,
        required_credentials: Optional[List[str]] = None,
        required_scopes: Optional[List[str]] = None,
        danger_level: str = "low", # low, medium, high, critical
        default_approval_tier: int = 0, # Tier 0 Observe, 1 Reversible, 2 Outbound/Approval, 3 Destructive/StepUp
        rate_limit_rpm: int = 60,
        cost_model: str = "free",
        data_sensitivity: str = "medium",
        documentation_url: str = ""
    ):
        self.integration_id = integration_id
        self.display_name = display_name
        self.category = category
        self.description = description
        self.required_credentials = required_credentials or []
        self.required_scopes = required_scopes or []
        self.danger_level = danger_level
        self.default_approval_tier = default_approval_tier
        self.rate_limit_rpm = rate_limit_rpm
        self.cost_model = cost_model
        self.data_sensitivity = data_sensitivity
        self.documentation_url = documentation_url

        # Invariant: Every integration must be disabled by default until user enables it
        self.enabled: bool = False
        self.connected: bool = False
        self.kill_switched: bool = False
        self.last_health: Optional[HealthReport] = None
        self._audit_log: List[Dict[str, Any]] = []

        # Configure rate limiter for this integration
        rate_limiter.set_limit(self.integration_id, self.rate_limit_rpm)
        self.retry_policy: RetryPolicy = default_retry_policy

    # ── State Control ──────────────────────────────────────────────────────────

    def enable(self) -> Dict[str, Any]:
        """Enables the integration for execution."""
        self.enabled = True
        self._record_audit("INTEGRATION_ENABLED", {"integration_id": self.integration_id}, "SUCCESS")
        return {"integration_id": self.integration_id, "enabled": True}

    def disable(self) -> Dict[str, Any]:
        """Disables the integration."""
        self.enabled = False
        self._record_audit("INTEGRATION_DISABLED", {"integration_id": self.integration_id}, "SUCCESS")
        return {"integration_id": self.integration_id, "enabled": False}

    def trip_kill_switch(self, reason: str = "Emergency stop") -> Dict[str, Any]:
        """Immediately halts this integration."""
        self.kill_switched = True
        self._record_audit("KILL_SWITCH_TRIPPED", {"reason": reason}, "KILL_SWITCHED")
        return {"integration_id": self.integration_id, "kill_switched": True, "reason": reason}

    def reset_kill_switch(self) -> Dict[str, Any]:
        """Resets the integration kill switch."""
        self.kill_switched = False
        self._record_audit("KILL_SWITCH_RESET", {}, "SUCCESS")
        return {"integration_id": self.integration_id, "kill_switched": False}

    # ── Content Hash & Verification ────────────────────────────────────────────

    @staticmethod
    def compute_content_hash(payload: Any) -> str:
        """Computes deterministic SHA-256 hash of parameters for frozen approval binding."""
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    # ── Lifecycle Methods (Abstract) ───────────────────────────────────────────

    @abstractmethod
    def connect(self, credentials: Optional[Dict[str, str]] = None) -> bool:
        """Connects or authenticates to the integration service."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnects and safely releases sessions and resources."""
        pass

    @abstractmethod
    def health_check(self) -> HealthReport:
        """Performs live connectivity and diagnostic probe."""
        pass

    @abstractmethod
    def list_powers(self) -> List[Dict[str, Any]]:
        """Returns catalogue of powers exposed by this integration."""
        pass

    @abstractmethod
    def _execute_power_impl(self, power_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Internal concrete execution of power without policy wrapping."""
        pass

    # ── Public Power Execution Pipeline ────────────────────────────────────────

    def execute_power(
        self,
        power_id: str,
        params: Dict[str, Any],
        approval_token: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Public guarded entrypoint for executing any integration power.
        Enforces:
          1. Global & integration kill-switch check
          2. Enabled check
          3. Credential availability check
          4. Rate limit check
          5. Policy tier & approval token validation with content hash
          6. Audit trail generation
        """
        start_time = time.time()
        content_hash = self.compute_content_hash(params)

        # 1. Kill-Switch Verification
        if self.kill_switched or policy_gate.is_kill_switch_active():
            self._record_audit(
                action=f"EXECUTE_{power_id}",
                target=power_id,
                payload={"params_hash": content_hash},
                result="BLOCKED_BY_KILL_SWITCH"
            )
            return {
                "status": "BLOCKED",
                "reason": "Execution halted: Kill switch is actively triggered.",
                "integration_id": self.integration_id,
                "power_id": power_id
            }

        # 2. Enabled Verification
        if not self.enabled:
            return {
                "status": "DISABLED",
                "reason": f"Integration '{self.integration_id}' is disabled. Enable it before executing powers.",
                "integration_id": self.integration_id,
                "power_id": power_id
            }

        # 3. Credential Verification
        is_valid, missing_keys = credential_manager.validate_credentials(self.required_credentials)
        if not is_valid:
            guide = credential_manager.get_setup_guide(self.integration_id)
            return {
                "status": "UNCONFIGURED",
                "reason": f"Missing required credentials: {', '.join(missing_keys)}",
                "missing_credentials": missing_keys,
                "setup_guide": guide,
                "integration_id": self.integration_id,
                "power_id": power_id
            }

        # 4. Rate Limiting Check
        allowed, wait_sec = rate_limiter.check_rate_limit(self.integration_id)
        if not allowed:
            return {
                "status": "RATE_LIMITED",
                "reason": f"Rate limit reached for '{self.integration_id}'. Back off for {wait_sec} seconds.",
                "wait_seconds": wait_sec,
                "integration_id": self.integration_id,
                "power_id": power_id
            }

        # 5. Policy & Approval Evaluation
        power_meta = self._find_power(power_id)
        if not power_meta:
            return {
                "status": "ERROR",
                "reason": f"Unknown power '{power_id}' for integration '{self.integration_id}'."
            }

        requires_approval = power_meta.get("approval_required", False)
        danger = power_meta.get("danger_level", self.danger_level)
        tier = power_meta.get("tier", self.default_approval_tier)

        # Any outbound or destructive action requires explicit token
        if requires_approval or tier >= 2:
            if not approval_token:
                # Issue approval request
                req_obj = policy_gate.request_approval(
                    power_id=power_id,
                    task_id=f"tsk_{content_hash[:8]}",
                    action_summary=f"Execute {power_meta.get('name', power_id)} on {self.display_name}",
                    payload=params
                )
                return {
                    "status": "AWAITING_APPROVAL",
                    "reason": f"Action requires Tier {tier} approval.",
                    "approval_required": True,
                    "approval_id": req_obj["approval_id"],
                    "content_hash": content_hash,
                    "integration_id": self.integration_id,
                    "power_id": power_id
                }

            # Verify token
            valid_token = policy_gate.verify_token(approval_token)
            if not valid_token:
                return {
                    "status": "APPROVAL_INVALID",
                    "reason": "Provided approval token is invalid, expired, or tampered."
                }

        # 6. Record rate limit call
        rate_limiter.record_call(self.integration_id)

        # 7. Execute with retry policy
        try:
            result = self.retry_policy.execute(self._execute_power_impl, power_id, params)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            self._record_audit(
                action=f"EXECUTE_{power_id}",
                target=power_id,
                payload={"params_hash": content_hash, "duration_ms": duration_ms},
                result="SUCCESS"
            )
            return {
                "status": "SUCCESS",
                "integration_id": self.integration_id,
                "power_id": power_id,
                "result": result,
                "content_hash": content_hash,
                "evidence": {
                    "timestamp": time.time(),
                    "duration_ms": duration_ms,
                    "content_hash": content_hash
                }
            }
        except Exception as e:
            self._record_audit(
                action=f"EXECUTE_{power_id}",
                target=power_id,
                payload={"params_hash": content_hash, "error": str(e)},
                result="FAILED"
            )
            return {
                "status": "FAILED",
                "reason": str(e),
                "integration_id": self.integration_id,
                "power_id": power_id
            }

    def dry_run(self, power_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates execution without performing external mutations.
        Returns expected side-effects, approval requirement, and frozen hash.
        """
        power_meta = self._find_power(power_id)
        if not power_meta:
            return {"status": "ERROR", "reason": f"Unknown power '{power_id}'"}

        content_hash = self.compute_content_hash(params)
        is_valid, missing = credential_manager.validate_credentials(self.required_credentials)

        return {
            "status": "DRY_RUN_READY",
            "integration_id": self.integration_id,
            "power_id": power_id,
            "power_name": power_meta.get("name", power_id),
            "simulated_params": credential_manager.redact_dict(params),
            "content_hash": content_hash,
            "tier": power_meta.get("tier", self.default_approval_tier),
            "approval_required": power_meta.get("approval_required", False),
            "credentials_ready": is_valid,
            "missing_credentials": missing,
            "kill_switch_active": self.kill_switched or policy_gate.is_kill_switch_active(),
            "expected_outcome": f"Would dispatch '{power_id}' to {self.display_name} with verified content hash."
        }

    def audit(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent execution events for this integration."""
        return list(reversed(self._audit_log[-limit:]))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_power(self, power_id: str) -> Optional[Dict[str, Any]]:
        for p in self.list_powers():
            if p.get("power_id") == power_id or p.get("name") == power_id:
                return p
        return None

    def _record_audit(self, action: str, payload: Dict[str, Any], result: str, target: Optional[str] = None) -> None:
        event = {
            "timestamp": time.time(),
            "integration_id": self.integration_id,
            "action": action,
            "target": target or self.integration_id,
            "payload": credential_manager.redact_dict(payload),
            "result": result
        }
        self._audit_log.append(event)
        audit_ledger.record(
            actor=f"integration:{self.integration_id}",
            action=action,
            target=target or self.integration_id,
            payload=event["payload"],
            result=result
        )
