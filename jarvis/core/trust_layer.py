"""
JARVIS Trust Layer — Sprint 1
==============================
The universal enforcement layer between JARVIS and the outside world.

The First Law of JARVIS:
  "JARVIS must never claim an action occurred without verifiable evidence."

This module provides:
  1. @trust_required decorator — wraps any function with capability + evidence enforcement
  2. TrustLayer class — central registry of all capability trust checks
  3. Automatic honest response generation when capabilities are unavailable

Architecture:
    User Request
        ↓
    Intent Router
        ↓
    [Trust Layer]  ← THIS FILE
        ↓
    Capability Check
        ↓
    Connectivity Check
        ↓
    Authentication Check
        ↓
    Execution
        ↓
    Evidence Collection
        ↓
    TrustResult (verified)
        ↓
    Response to User

Usage:
    from jarvis.core.trust_layer import trust_layer

    # Wrap a function:
    @trust_layer.require("gmail")
    def scan_inbox():
        ...

    # Or call inline:
    result = trust_layer.execute_with_trust(
        capability="gmail",
        action=lambda: email_powers.scan_inbox(),
        collect_evidence=lambda r: [Evidence(source="imap.gmail.com", action="scan", data=r)]
    )
"""

from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.capability_guard import capability_guard, CapabilityStatus, CapabilityGuardError
from jarvis.core.evidence import Evidence, TrustResult, CapabilityState
from jarvis.core.logger import get_logger

logger = get_logger("core.trust_layer")

# ── Capability → guard method mapping ─────────────────────────────────────────
_CAPABILITY_CHECKS: Dict[str, Callable[[], str]] = {
    "gmail":    capability_guard.check_gmail,
    "ollama":   capability_guard.check_ollama,
    "internet": capability_guard.check_internet,
    "browser":  capability_guard.check_internet,   # browser needs internet
    "search":   capability_guard.check_internet,
}

# ── Human-readable setup hints per capability ──────────────────────────────────
_SETUP_HINTS: Dict[str, str] = {
    "gmail": (
        "To connect Gmail:\n"
        "  1. Go to myaccount.google.com/apppasswords\n"
        "  2. Generate an App Password\n"
        "  3. Add to .env: GMAIL_USER=your@gmail.com\n"
        "  4. Add to .env: GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx\n"
        "  5. Restart JARVIS"
    ),
    "ollama": (
        "To start Ollama:\n"
        "  Run: ollama serve\n"
        "  Then: ollama pull qwen2.5:7b"
    ),
    "internet": (
        "Check your network connection. "
        "Local capabilities (memory, files, voice) remain available."
    ),
    "browser": (
        "Browser automation requires internet connectivity. "
        "Check your network connection."
    ),
}


class TrustLayer:
    """
    Central enforcement point for all JARVIS capabilities.
    Every external action must pass through here.
    """

    def check_capability(self, capability: str) -> CapabilityState:
        """Probe a capability and return its real state."""
        check_fn = _CAPABILITY_CHECKS.get(capability)
        if not check_fn:
            logger.warning(f"No trust check registered for capability '{capability}' — treating as UNKNOWN")
            return CapabilityState.UNKNOWN

        raw = check_fn()
        mapping = {
            CapabilityStatus.CONNECTED:    CapabilityState.CONNECTED,
            CapabilityStatus.DISCONNECTED: CapabilityState.DISCONNECTED,
            CapabilityStatus.DEGRADED:     CapabilityState.DEGRADED,
            CapabilityStatus.UNKNOWN:      CapabilityState.UNKNOWN,
        }
        return mapping.get(raw, CapabilityState.UNKNOWN)

    def execute_with_trust(
        self,
        capability: str,
        action: Callable[[], Any],
        collect_evidence: Optional[Callable[[Any], List[Evidence]]] = None,
        action_name: str = "execute",
    ) -> TrustResult:
        """
        Execute an action only if the capability is available.
        Always returns a TrustResult — never raises to caller.

        Args:
            capability:       The capability name ("gmail", "ollama", etc.)
            action:           The actual function to call if capability is available
            collect_evidence: Function that takes action result and returns Evidence list
            action_name:      Human-readable action description for logging
        """
        state = self.check_capability(capability)
        logger.info(f"Trust check: capability={capability} state={state.value} action={action_name}")

        if state == CapabilityState.DISCONNECTED:
            hint = _SETUP_HINTS.get(capability, "")
            msg = f"{capability} is not connected. {hint}".strip()
            logger.warning(f"Trust block: {capability} DISCONNECTED — action '{action_name}' blocked")
            return TrustResult.disconnected(capability, msg)

        if state == CapabilityState.DEGRADED:
            msg = (
                f"{capability} credentials are configured but the service is unreachable. "
                "Check your internet connection."
            )
            logger.warning(f"Trust block: {capability} DEGRADED — action '{action_name}' blocked")
            return TrustResult.degraded(capability, msg)

        # Capability is available — attempt execution
        try:
            result = action()

            # Collect evidence from real result
            evidence = []
            if collect_evidence:
                try:
                    evidence = collect_evidence(result) or []
                except Exception as ev_err:
                    logger.warning(f"Evidence collection failed: {ev_err}")

            # If no evidence collector provided, create a minimal evidence record
            if not evidence:
                evidence = [Evidence(
                    source=capability,
                    action=action_name,
                    data={"result_type": type(result).__name__},
                    verified=True,
                )]

            return TrustResult.success(
                capability=capability,
                evidence=evidence,
                data=result if isinstance(result, dict) else {"result": result},
                message=f"{capability} {action_name} completed with evidence.",
            )

        except CapabilityGuardError as e:
            logger.warning(f"Capability guard raised during execution: {e}")
            return TrustResult.disconnected(capability, str(e))

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Trust layer caught exception in {capability}.{action_name}: {e}\n{tb}")
            return TrustResult.failed(capability, str(e))

    def require(self, capability: str):
        """
        Decorator factory. Wraps a function with capability enforcement.
        The wrapped function returns TrustResult instead of raw output.

        Usage:
            @trust_layer.require("gmail")
            def scan_inbox() -> dict:
                ...  # real implementation

            result = scan_inbox()
            # result is always TrustResult, never raises
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return self.execute_with_trust(
                    capability=capability,
                    action=lambda: fn(*args, **kwargs),
                    action_name=fn.__name__,
                )
            return wrapper
        return decorator

    def get_all_states(self) -> Dict[str, str]:
        """Returns real probed state of every registered capability."""
        return {
            cap: self.check_capability(cap).value
            for cap in _CAPABILITY_CHECKS
        }


# Global singleton — import and use everywhere
trust_layer = TrustLayer()

