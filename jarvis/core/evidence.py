"""
JARVIS Evidence Layer — Sprint 1
=================================
Every action JARVIS takes must produce verifiable evidence.
Without evidence, no claim is made.

This is the First Law of JARVIS:
  "JARVIS must never claim an action occurred without verifiable evidence."

Usage:
    evidence = Evidence.collect(
        capability="gmail",
        action="scan_inbox",
        source="imap.gmail.com",
        data={"message_count": 3, "message_ids": ["1a2b", "3c4d"]}
    )

    result = TrustResult.success(
        capability="gmail",
        evidence=[evidence],
        data={"opportunities": [...]}
    )

    # Or for failures:
    result = TrustResult.disconnected("gmail", "Gmail OAuth not configured.")
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class CapabilityState(str, Enum):
    CONNECTED       = "connected"
    DISCONNECTED    = "disconnected"
    DEGRADED        = "degraded"       # Creds exist but service unreachable
    UNAUTHORIZED    = "unauthorized"   # Creds rejected
    RATE_LIMITED    = "rate_limited"
    UNKNOWN         = "unknown"


@dataclass
class Evidence:
    """
    A single verifiable piece of evidence for an action.

    Rule: Only create Evidence when you have REAL data from a REAL source.
          Never construct Evidence from hardcoded or assumed data.
    """
    source: str                          # e.g. "imap.gmail.com", "ollama:11434", "data/inbox/msg1.eml"
    action: str                          # e.g. "imap_login", "fetch_message", "socket_connect"
    timestamp: float = field(default_factory=time.time)
    evidence_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    data: Dict[str, Any] = field(default_factory=dict)
    verified: bool = True               # False = attempted but could not verify

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "action": self.action,
            "timestamp": self.timestamp,
            "verified": self.verified,
            "data": self.data,
        }


@dataclass
class TrustResult:
    """
    Standard result envelope for every JARVIS action.

    Fields:
        success      — True only when the action completed with real evidence
        capability   — Which capability was used (e.g. "gmail", "ollama", "browser")
        status       — Current state of that capability
        evidence     — List of Evidence objects proving what happened
        data         — The actual result payload (empty if success=False)
        message      — Human-readable status. Honest always.
        fabricated   — Always False. If True, something is very wrong.
    """
    success: bool
    capability: str
    status: CapabilityState
    evidence: List[Evidence]
    data: Dict[str, Any]
    message: str
    fabricated: bool = False            # Hard invariant: always False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "capability": self.capability,
            "status": self.status.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "evidence_count": len(self.evidence),
            "data": self.data,
            "message": self.message,
            "fabricated": self.fabricated,  # Always False — proof of honesty
        }

    # ── Factory methods ────────────────────────────────────────────────────────

    @classmethod
    def success(
        cls,
        capability: str,
        evidence: List[Evidence],
        data: Dict[str, Any],
        message: str = "",
    ) -> "TrustResult":
        """Call only when real evidence exists for a completed action."""
        assert evidence, "Cannot claim success without at least one Evidence object."
        return cls(
            success=True,
            capability=capability,
            status=CapabilityState.CONNECTED,
            evidence=evidence,
            data=data,
            message=message or f"{capability} action completed with {len(evidence)} evidence item(s).",
            fabricated=False,
        )

    @classmethod
    def disconnected(cls, capability: str, message: str = "") -> "TrustResult":
        """Use when the service is not connected. Returns empty data, no claims."""
        return cls(
            success=False,
            capability=capability,
            status=CapabilityState.DISCONNECTED,
            evidence=[],
            data={},
            message=message or f"{capability} is not connected. Configure credentials to enable this capability.",
            fabricated=False,
        )

    @classmethod
    def degraded(cls, capability: str, message: str = "") -> "TrustResult":
        """Use when credentials exist but service is unreachable."""
        return cls(
            success=False,
            capability=capability,
            status=CapabilityState.DEGRADED,
            evidence=[],
            data={},
            message=message or f"{capability} credentials configured but service is unreachable. Check connectivity.",
            fabricated=False,
        )

    @classmethod
    def unauthorized(cls, capability: str, message: str = "") -> "TrustResult":
        """Use when authentication is rejected."""
        return cls(
            success=False,
            capability=capability,
            status=CapabilityState.UNAUTHORIZED,
            evidence=[],
            data={},
            message=message or f"{capability} authentication failed. Check credentials.",
            fabricated=False,
        )

    @classmethod
    def failed(cls, capability: str, error: str, evidence: Optional[List[Evidence]] = None) -> "TrustResult":
        """Use when the action was attempted but failed mid-execution."""
        return cls(
            success=False,
            capability=capability,
            status=CapabilityState.UNKNOWN,
            evidence=evidence or [],
            data={"error": error},
            message=f"{capability} action failed: {error}",
            fabricated=False,
        )

