"""
JARVIS Brain Error Taxonomy and Recovery Classification
Defines the 6-tier cognitive error hierarchy, structured exception classes,
and deterministic classify_error() routing for self-correcting cognitive loops.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, Optional, Union

from jarvis.brain.state import CognitiveError


class CognitiveErrorCode(str, Enum):
    """Authoritative 6-tier cognitive error codes."""

    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    POLICY_DENIED = "POLICY_DENIED"
    AI_USAGE_LIMIT = "AI_USAGE_LIMIT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


# ── Structured Cognitive Exceptions ───────────────────────────────────────────


class CognitiveBaseException(Exception):
    """Base exception for all cognitive loop failures."""

    code: CognitiveErrorCode = CognitiveErrorCode.PERMANENT_FAILURE
    recoverable: bool = False

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TransientNetworkError(CognitiveBaseException):
    """Temporary network timeouts, HTTP 502/503/504, or Ollama warmup latency."""

    code = CognitiveErrorCode.TRANSIENT_NETWORK
    recoverable = True


class SessionExpiredError(CognitiveBaseException):
    """Expired HMAC approval token (>15m) or invalid session context."""

    code = CognitiveErrorCode.SESSION_EXPIRED
    recoverable = True


class PolicyDeniedError(CognitiveBaseException):
    """Deterministic security gate halt, active kill switch, or forbidden action."""

    code = CognitiveErrorCode.POLICY_DENIED
    recoverable = False


class AIUsageLimitError(CognitiveBaseException):
    """Budget cap hit or cost governor circuit breaker tripped."""

    code = CognitiveErrorCode.AI_USAGE_LIMIT
    recoverable = False


class InsufficientEvidenceError(CognitiveBaseException):
    """Verifier detected missing evidence, empty recall, or unverified claims."""

    code = CognitiveErrorCode.INSUFFICIENT_EVIDENCE
    recoverable = True


class PermanentFailureError(CognitiveBaseException):
    """Irrecoverable syntax, malformed parameter, or system tool failure."""

    code = CognitiveErrorCode.PERMANENT_FAILURE
    recoverable = False


# ── Classification Logic ──────────────────────────────────────────────────────


def classify_error(
    exc: Union[Exception, str],
    context: Optional[Dict[str, Any]] = None,
) -> CognitiveError:
    """
    Deterministically maps an arbitrary runtime exception or failure description
    into the 6-tier CognitiveError model with recovery strategy.

    Args:
        exc: Exception instance or error description string.
        context: Optional diagnostic dictionary (retry_count, node_name, etc.)

    Returns:
        Structured CognitiveError object.
    """
    ctx = context or {}
    retry_count = ctx.get("retry_count", 0)

    # 1. Direct structured match
    if isinstance(exc, CognitiveBaseException):
        return CognitiveError(
            code=exc.code.value,
            message=exc.message,
            recoverable=exc.recoverable,
            retry_count=retry_count,
            timestamp=time.time(),
            details={**exc.details, **ctx},
        )

    # 2. String pattern analysis
    err_str = str(exc).lower()

    if any(k in err_str for k in ("kill switch", "kill_switch", "policy denied", "halted", "forbidden", "tier 3")):
        code = CognitiveErrorCode.POLICY_DENIED
        recoverable = False
    elif any(k in err_str for k in ("token expired", "session expired", "stale token", "expired approval")):
        code = CognitiveErrorCode.SESSION_EXPIRED
        recoverable = True
    elif any(k in err_str for k in ("budget", "usage limit", "circuit breaker", "max cost", "rate limit exceeded")):
        code = CognitiveErrorCode.AI_USAGE_LIMIT
        recoverable = False
    elif any(
        k in err_str
        for k in ("insufficient evidence", "missing evidence", "unverified", "no memories found", "empty search")
    ):
        code = CognitiveErrorCode.INSUFFICIENT_EVIDENCE
        recoverable = True
    elif any(
        k in err_str
        for k in (
            "timeout",
            "timed out",
            "connection refused",
            "connect error",
            "network unreachable",
            "502",
            "503",
            "504",
            "warming up",
            "econnrefused",
        )
    ):
        code = CognitiveErrorCode.TRANSIENT_NETWORK
        recoverable = True
    else:
        code = CognitiveErrorCode.PERMANENT_FAILURE
        recoverable = False

    return CognitiveError(
        code=code.value,
        message=str(exc),
        recoverable=recoverable,
        retry_count=retry_count,
        timestamp=time.time(),
        details=ctx,
    )


def get_remediation_strategy(error: CognitiveError) -> Dict[str, Any]:
    """
    Returns the remediation routing and backoff configuration for a CognitiveError.
    """
    code = error.code
    if code == CognitiveErrorCode.TRANSIENT_NETWORK.value:
        backoff_sec = min(2**error.retry_count, 8)
        return {
            "action": "retry_act",
            "target_node": "act",
            "backoff_sec": backoff_sec,
            "max_retries": 3,
            "can_retry": error.retry_count < 3,
        }
    if code == CognitiveErrorCode.SESSION_EXPIRED.value:
        return {
            "action": "reissue_approval",
            "target_node": "policy",
            "backoff_sec": 0,
            "max_retries": 1,
            "can_retry": error.retry_count < 1,
        }
    if code == CognitiveErrorCode.INSUFFICIENT_EVIDENCE.value:
        return {
            "action": "replan_query",
            "target_node": "plan",
            "backoff_sec": 0,
            "max_retries": 2,
            "can_retry": error.retry_count < 2,
        }
    if code == CognitiveErrorCode.AI_USAGE_LIMIT.value:
        return {
            "action": "downgrade_to_local",
            "target_node": "plan",
            "backoff_sec": 0,
            "max_retries": 1,
            "can_retry": error.retry_count < 1,
        }
    return {
        "action": "halt_to_remember",
        "target_node": "remember",
        "backoff_sec": 0,
        "max_retries": 0,
        "can_retry": False,
    }


__all__ = [
    "CognitiveErrorCode",
    "CognitiveBaseException",
    "TransientNetworkError",
    "SessionExpiredError",
    "PolicyDeniedError",
    "AIUsageLimitError",
    "InsufficientEvidenceError",
    "PermanentFailureError",
    "classify_error",
    "get_remediation_strategy",
]
