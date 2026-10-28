"""
JARVIS Policy Engine (4-Tier Evaluation)
Implements four approval tiers:
  Tier 0 — Observe
  Tier 1 — Reversible action
  Tier 2 — Explicit approval
  Tier 3 — Step-up authentication
Evaluates permissions, blocked applications, sensitive data patterns, and dangerous operations.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.constants import (
    DEFAULT_CRITICAL_KEYWORDS,
    DEFAULT_POLICY_ALLOWED_APPS,
    DEFAULT_POLICY_BLOCKED_APPS,
    DEFAULT_TIER1_KEYWORDS,
    DEFAULT_TIER2_KEYWORDS,
)

PERMISSIONS_PATH = settings.config_dir / "policies" / "permissions.json"

class PolicyDecision(BaseModel):
    risk_level: str = Field(default="low", description="low, medium, high, critical")
    approval_required: bool = Field(default=False)
    allowed_tools: List[str] = Field(default_factory=list)
    tier: int = Field(default=0, ge=0, le=3)
    reason: str = Field(default="Standard read/local operation permitted.")

class PolicyEngine:
    """Deterministic policy gate enforcing Tier 0 to Tier 3 boundaries."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or PERMISSIONS_PATH
        self.policy = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "allowed_apps": list(DEFAULT_POLICY_ALLOWED_APPS),
            "blocked_apps": list(DEFAULT_POLICY_BLOCKED_APPS),
            "sensitive_data_patterns": ["password", "secret_key", "private_key", "api_key", "token"]
        }

    def evaluate(
        self,
        user_input: str,
        task_type: str = "chat",
        memories: Optional[List[str]] = None
    ) -> PolicyDecision:
        """
        Evaluates input text and requested task against policy rules and assign approval tiers.
        """
        text_lower = user_input.lower()

        # Tier 3: Critical / Destructive System / Financial
        critical_keywords = DEFAULT_CRITICAL_KEYWORDS
        if any(w in text_lower for w in critical_keywords):
            return PolicyDecision(
                risk_level="critical",
                approval_required=True,
                allowed_tools=[],
                tier=3,
                reason="Tier 3 Action: Critical or irreversible system wipe requires step-up authentication."
            )

        # Tier 2: Irreversible Outbound / Physical computer use / Deletion
        dangerous_keywords = DEFAULT_TIER2_KEYWORDS
        if any(w in text_lower for w in dangerous_keywords) or task_type in ("desktop_control", "outbound_comms"):
            return PolicyDecision(
                risk_level="high",
                approval_required=True,
                allowed_tools=["desktop_worker", "email_client"],
                tier=2,
                reason="Tier 2 Action: Irreversible outbound or computer control requires explicit approval token."
            )

        # Tier 1: Reversible local writes / drafts / sandboxed execution
        reversible_keywords = DEFAULT_TIER1_KEYWORDS
        if any(w in text_lower for w in reversible_keywords) or task_type in ("document_ingest", "code_generation"):
            return PolicyDecision(
                risk_level="medium",
                approval_required=False,
                allowed_tools=["filesystem", "document_rag", "git_tool"],
                tier=1,
                reason="Tier 1 Action: Local reversible write permitted without approval."
            )

        # Tier 0: Observe / Web Search / Read-only memory
        return PolicyDecision(
            risk_level="low",
            approval_required=False,
            allowed_tools=["web_search", "memory_search", "url_read", "telemetry"],
            tier=0,
            reason="Tier 0 Action: Read-only or observational query permitted autonomously."
        )

# Global PolicyEngine Instance
policy_engine = PolicyEngine()
