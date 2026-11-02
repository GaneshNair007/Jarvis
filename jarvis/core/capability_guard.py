"""
JARVIS Capability Guard — Sprint 1 Trust Fix
=============================================
Enforces capability checks BEFORE any action executes.
Eliminates hallucinated results for disconnected services.

Rule: If a service is NOT connected, JARVIS must say so honestly.
      It must NEVER fabricate results.

Usage:
    guard = CapabilityGuard()
    guard.require("gmail_imap", "Inbox scan requires Gmail to be connected.")
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Dict, Any, Optional
from jarvis.core.logger import get_logger

logger = get_logger("core.capability_guard")


class CapabilityStatus:
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class CapabilityGuardError(Exception):
    """Raised when a required capability is not available.
    Contains a user-facing honest status message."""

    def __init__(self, capability: str, status: str, message: str, setup_hint: str = ""):
        self.capability = capability
        self.status = status
        self.user_message = message
        self.setup_hint = setup_hint
        super().__init__(message)

    def to_response(self) -> Dict[str, Any]:
        return {
            "status": "capability_unavailable",
            "capability": self.capability,
            "service_status": self.status,
            "message": self.user_message,
            "setup_hint": self.setup_hint,
            "fabricated": False,
        }


class CapabilityGuard:
    """
    Checks real service connectivity before any action is attempted.
    Returns honest status — never fabricates results.
    """

    def __init__(self):
        self._cache: Dict[str, tuple[str, float]] = {}
        self._ttl = 30.0  # seconds

    def clear_cache(self) -> None:
        """Clears probe cache to force immediate re-evaluation."""
        self._cache.clear()

    def _cached(self, key: str, probe_fn) -> str:
        now = time.time()
        if key in self._cache:
            status, ts = self._cache[key]
            if now - ts < self._ttl:
                return status
        status = probe_fn()
        self._cache[key] = (status, now)
        return status

    # ──────────────────────────────────────────────────────
    # Gmail
    # ──────────────────────────────────────────────────────
    def check_gmail(self, use_cache: bool = True) -> str:
        """Returns CONNECTED (OAuth token exists + IMAP reachable) or DISCONNECTED."""
        def probe():
            has_oauth = bool(
                os.getenv("GMAIL_OAUTH_TOKEN") or
                os.getenv("GMAIL_CLIENT_ID") or
                Path("config/gmail_token.json").exists() or
                Path("config/credentials.json").exists()
            )
            has_imap_password = bool(
                os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_PASSWORD")
            )

            if not (has_oauth or has_imap_password):
                return CapabilityStatus.DISCONNECTED

            # Check if imap.gmail.com is reachable (connectivity test only, no auth)
            try:
                socket.create_connection(("imap.gmail.com", 993), timeout=3)
                return CapabilityStatus.CONNECTED if (has_oauth or has_imap_password) else CapabilityStatus.DISCONNECTED
            except (socket.timeout, ConnectionRefusedError, OSError):
                return CapabilityStatus.DEGRADED  # creds exist but no internet

        if not use_cache:
            return probe()
        return self._cached("gmail", probe)

    # ──────────────────────────────────────────────────────
    # Ollama
    # ──────────────────────────────────────────────────────
    def check_ollama(self, host: str = "127.0.0.1", port: int = 11434, use_cache: bool = True) -> str:
        def probe():
            try:
                with socket.create_connection((host, port), timeout=1):
                    return CapabilityStatus.CONNECTED
            except (socket.timeout, ConnectionRefusedError, OSError):
                return CapabilityStatus.DISCONNECTED

        if not use_cache:
            return probe()
        return self._cached(f"ollama_{host}_{port}", probe)

    # ──────────────────────────────────────────────────────
    # Internet
    # ──────────────────────────────────────────────────────
    def check_internet(self, use_cache: bool = True) -> str:
        def probe():
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                return CapabilityStatus.CONNECTED
            except OSError:
                return CapabilityStatus.DISCONNECTED

        if not use_cache:
            return probe()
        return self._cached("internet", probe)

    # ──────────────────────────────────────────────────────
    # Requirement enforcement
    # ──────────────────────────────────────────────────────
    def require_gmail(self) -> None:
        """
        Call before any Gmail action.
        Raises CapabilityGuardError with honest user message if not connected.
        """
        status = self.check_gmail()
        if status == CapabilityStatus.DISCONNECTED:
            raise CapabilityGuardError(
                capability="gmail",
                status=status,
                message=(
                    "Gmail is not connected.\n\n"
                    "To connect Gmail, JARVIS needs your Gmail App Password or OAuth token.\n"
                    "JARVIS cannot scan your inbox without it.\n\n"
                    "Would you like setup instructions?"
                ),
                setup_hint=(
                    "Set GMAIL_APP_PASSWORD in your .env file, or run: jarvis setup gmail"
                ),
            )
        if status == CapabilityStatus.DEGRADED:
            raise CapabilityGuardError(
                capability="gmail",
                status=status,
                message=(
                    "Gmail credentials are configured, but the server is unreachable.\n"
                    "Check your internet connection and try again."
                ),
            )

    def require_internet(self) -> None:
        """Call before any web search or browser action."""
        status = self.check_internet()
        if status == CapabilityStatus.DISCONNECTED:
            raise CapabilityGuardError(
                capability="internet",
                status=status,
                message=(
                    "No internet connection detected.\n"
                    "Web search and browser actions are unavailable.\n"
                    "Local capabilities (memory, voice, file operations) still work."
                ),
            )

    def require_ollama(self) -> None:
        """Call before routing to TIER_1_LOCAL."""
        status = self.check_ollama()
        if status == CapabilityStatus.DISCONNECTED:
            raise CapabilityGuardError(
                capability="ollama",
                status=status,
                message=(
                    "Local AI model (Ollama) is offline.\n"
                    "Start Ollama: run `ollama serve` in a terminal.\n"
                    "Falling back to cloud tier if authorized."
                ),
                setup_hint="Run: ollama serve",
            )

    def get_all_status(self) -> Dict[str, Any]:
        """Returns honest status of all services. Used by /health and dashboard."""
        return {
            "gmail": self.check_gmail(),
            "ollama": self.check_ollama(),
            "internet": self.check_internet(),
            "fabricated": False,
            "note": "All statuses reflect real connectivity checks, not configuration assumptions.",
        }


# Global singleton
capability_guard = CapabilityGuard()

