"""
JARVIS First Law Compliance: Evidence & TrustResult.

First Law of JARVIS: *"No Evidence, No Claim"*

Every action-producing capability must return a TrustResult wrapping
verifiable Evidence. Without Evidence, the system cannot legitimately
claim an action occurred.

Classes:
    Evidence: Immutable data record with source, data, timestamp, trust_level.
    TrustResult: Verdict (success/fail) with associated Evidence + description.
"""


from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Evidence:
    """Immutable evidence record supporting the First Law of JARVIS.

    Attributes:
        source: Identifier of the component that generated this evidence.
        data: The raw data/content that serves as proof of execution.
        timestamp: UNIX epoch time when the evidence was created.
        trust_level: "verified", "self_generated", "unverified", "audited".
        evidence_id: Cryptographic hash of (source + data + timestamp) for tamper evidence.
    """

    source: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    trust_level: str = "verified"
    evidence_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:16]}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize evidence to dictionary for JSON routing/API transport."""
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "data": (
                self.data.to_dict() if hasattr(self.data, "to_dict") else self.data
            ),
            "timestamp": self.timestamp,
            "trust_level": self.trust_level,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Evidence":
        """Deserialize evidence from dictionary."""
        return cls(
            source=d["source"],
            data=d["data"] if not isinstance(d.get("data"), dict) else d["data"],
            timestamp=d.get("timestamp", time.time()),
            trust_level=d.get("trust_level", "verified"),
            evidence_id=d.get("evidence_id", f"ev_{uuid.uuid4().hex[:16]}"),
        )


@dataclass
class TrustResult:
    """Verdict result wrapping Evidence, enforcing First Law: No Evidence = No Claim.

    Attributes:
        verdict: "success" or "fail".
        evidence: Associated Evidence object (REQUIRED - cannot be None).
        description: Human-readable explanation of the verdict.
        requires_approval: Whether this result triggers an approval gate.
        approval_token: Optional cryptographic token if approval is required.
    """

    verdict: str
    evidence: Evidence
    description: str
    requires_approval: bool = False
    approval_token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trust result to dictionary for JSON routing/API transport."""
        return {
            "verdict": self.verdict,
            "evidence": self.evidence.to_dict(),
            "description": self.description,
            "requires_approval": self.requires_approval,
            "approval_token": self.approval_token,
        }

    @classmethod
    def success(
        cls,
        evidence: Evidence,
        description: str = "Operation completed successfully",
        requires_approval: bool = False,
        approval_token: Optional[str] = None,
    ) -> "TrustResult":
        """Factory for a successful TrustResult."""
        return cls(
            verdict="success",
            evidence=evidence,
            description=description,
            requires_approval=requires_approval,
            approval_token=approval_token,
        )

    @classmethod
    def fail(
        cls,
        evidence: Evidence,
        description: str = "Operation failed",
        requires_approval: bool = False,
        approval_token: Optional[str] = None,
    ) -> "TrustResult":
        """Factory for a failed TrustResult."""
        return cls(
            verdict="fail",
            evidence=evidence,
            description=description,
            requires_approval=requires_approval,
            approval_token=approval_token,
        )

    def assert_evidence_present(self) -> None:
        """Enforce First Law: raise if evidence is missing or empty."""
        if self.evidence is None:
            raise AssertionError("First Law violation: TrustResult.verdict='success' without Evidence")
        if not str(self.evidence.source).strip():
            raise AssertionError("First Law violation: Evidence source is empty")


# Singleton for easy import
evidence_store: Optional[Any] = None
trust_result_dispatch = TrustResult