"""
JARVIS Audit Logger
Provides append-only cryptographic event logging across tasks, tools, policy decisions, and models.
"""

import time
import uuid
import hashlib
from typing import Dict, Any, Optional
from jarvis.core.audit import audit_ledger

class AuditLogger:
    """High-level audit logger for recording system events with input/output hashes."""

    def __init__(self):
        self.ledger = audit_ledger

    def _hash(self, data: Any) -> str:
        if data is None:
            return ""
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()

    def log(
        self,
        action: str,
        task_id: str = "general",
        user_id: str = "ganesh",
        actor: str = "system",
        tool: Optional[str] = None,
        model: Optional[str] = None,
        inputs: Any = None,
        outputs: Any = None,
        policy_decision: Optional[str] = None,
        approval_id: Optional[str] = None,
        cost: float = 0.0,
        latency: float = 0.0,
        result: str = "SUCCESS",
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends a structured, hash-chained audit record."""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        record = self.ledger.log_event(
            event_type=action,
            task_id=task_id,
            power_id=tool or "system",
            status=result,
            inputs={"raw": inputs, "input_hash": self._hash(inputs)},
            outputs={"raw": outputs, "output_hash": self._hash(outputs)},
            user_id=user_id,
            details={
                "event_id": event_id,
                "actor": actor,
                "tool": tool,
                "model": model,
                "policy_decision": policy_decision,
                "approval_id": approval_id,
                "cost": cost,
                "latency": latency,
                "error": error
            }
        )
        return record

    def list_logs(self, limit: int = 50):
        return self.ledger.get_recent_entries(limit=limit)

    def verify(self):
        return self.ledger.verify_integrity()

audit_logger = AuditLogger()
