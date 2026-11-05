"""
JARVIS Cross-Device Relay (phone <-> laptop).

Lets a phone (or any second device) send commands to this machine and get
answers back over authenticated HTTP:

    laptop:  POST /api/v1/relay/pair         -> {code}          (6-digit, short TTL)
    phone:   POST /api/v1/relay/exchange     {code, device}     -> {token}
    phone:   POST /api/v1/relay/command      Bearer <token>     -> {reply, trust}
    phone:   GET  /api/v1/relay/status       Bearer <token>     -> host + voice health

Security model:
  - Pairing codes are 6 random digits, single-use, TTL-bound.
  - Device tokens are 32-byte secrets, constant-time compared.
  - Failed exchanges are rate limited per relay instance.
  - Every command is wrapped in a TrustResult (First Law: No Evidence, No Claim).
"""

from __future__ import annotations

import asyncio
import secrets
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.evidence import Evidence, TrustResult
from jarvis.core.logger import get_logger

logger = get_logger("relay")

PAIRING_CODE_TTL_SEC = 300
MAX_FAILED_EXCHANGES = 8
FAILED_WINDOW_SEC = 60.0


class RelayAuthError(Exception):
    """Raised when a relay token or pairing code is invalid/expired."""


class DeviceRelay:
    """Pairing + authenticated command relay between laptop and phone."""

    def __init__(self, orchestrator: Any = None, clock: Optional[Callable[[], float]] = None):
        self._orchestrator = orchestrator
        self._clock = clock or time.time
        self._lock = threading.RLock()  # re-entrant: _record() is called while holding it
        self._pairing: Dict[str, Dict[str, Any]] = {}   # code -> {expires_at, device_hint}
        self._tokens: Dict[str, Dict[str, Any]] = {}    # token -> {device_id, device_name, created_at}
        self._failed_exchanges: List[float] = []
        self.command_count = 0
        self.evidence_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    #  Evidence                                                           #
    # ------------------------------------------------------------------ #

    def _record(self, source: str, data: Dict[str, Any]) -> Evidence:
        ev = Evidence(source=source, data=data, timestamp=self._clock(), trust_level="verified")
        with self._lock:
            self.evidence_log.append(ev.to_dict())
            if len(self.evidence_log) > 500:
                self.evidence_log.pop(0)
        return ev

    # ------------------------------------------------------------------ #
    #  Pairing                                                            #
    # ------------------------------------------------------------------ #

    def create_pairing_code(self, ttl_sec: int = PAIRING_CODE_TTL_SEC) -> Dict[str, Any]:
        """Generates a fresh single-use pairing code for the laptop screen."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = self._clock() + ttl_sec
        with self._lock:
            # Drop expired codes so the table stays bounded.
            now = self._clock()
            self._pairing = {c: v for c, v in self._pairing.items() if v["expires_at"] > now}
            self._pairing[code] = {"expires_at": expires_at, "created_at": now}
        self._record("relay.pair", {"code_length": len(code), "ttl_sec": ttl_sec})
        logger.info("Relay pairing code issued (ttl=%ss)", ttl_sec)
        return {"code": code, "expires_in": ttl_sec, "expires_at": expires_at}

    def exchange_code(self, code: str, device_name: str = "phone") -> Dict[str, Any]:
        """Trades a valid pairing code for a persistent device token."""
        now = self._clock()
        with self._lock:
            # Rate limit failed attempts.
            self._failed_exchanges = [t for t in self._failed_exchanges if now - t < FAILED_WINDOW_SEC]
            if len(self._failed_exchanges) >= MAX_FAILED_EXCHANGES:
                raise RelayAuthError("too many failed pairing attempts, retry later")

            entry = self._pairing.get(str(code).strip())
            if entry is None or entry["expires_at"] <= now:
                self._failed_exchanges.append(now)
                self._record(
                    "relay.exchange",
                    {"status": "rejected", "reason": "invalid_or_expired_code"},
                )
                raise RelayAuthError("invalid or expired pairing code")

            del self._pairing[str(code).strip()]
            token = secrets.token_urlsafe(32)
            device_id = f"dev_{secrets.token_hex(4)}"
            self._tokens[token] = {
                "device_id": device_id,
                "device_name": (device_name or "phone")[:64],
                "created_at": now,
                "last_seen": now,
            }

        self._record(
            "relay.exchange",
            {"status": "accepted", "device_id": device_id, "device_name": device_name[:64]},
        )
        logger.info("Relay device paired: %s", device_name)
        return {"token": token, "device_id": device_id, "device_name": device_name[:64]}

    def authenticate(self, token: Optional[str]) -> Dict[str, Any]:
        """Validates a bearer token and refreshes last_seen. Raises RelayAuthError."""
        if not token:
            raise RelayAuthError("missing token")
        now = self._clock()
        with self._lock:
            for known, meta in self._tokens.items():
                if secrets.compare_digest(known, token):
                    meta["last_seen"] = now
                    return dict(meta)
        raise RelayAuthError("invalid token")

    def revoke_device(self, token: str) -> bool:
        with self._lock:
            for known in list(self._tokens):
                if secrets.compare_digest(known, token):
                    del self._tokens[known]
                    self._record("relay.revoke", {"revoked": True})
                    return True
        return False

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._tokens.values()]

    # ------------------------------------------------------------------ #
    #  Command execution                                                  #
    # ------------------------------------------------------------------ #

    async def execute_command(self, token: Optional[str], command: str) -> TrustResult:
        """Authenticates the device and routes the command through the orchestrator.

        Always returns a TrustResult: success carries command evidence, failure
        carries rejection/error evidence. Never claims success without proof.
        """
        command = (command or "").strip()
        try:
            device = self.authenticate(token)
        except RelayAuthError as exc:
            ev = self._record(
                "relay.command",
                {"status": "rejected", "reason": str(exc), "command_preview": command[:80]},
            )
            return TrustResult.fail(evidence=ev, description=f"relay auth rejected: {exc}")

        if not command:
            ev = self._record(
                "relay.command",
                {"status": "rejected", "reason": "empty_command", "device_id": device["device_id"]},
            )
            return TrustResult.fail(evidence=ev, description="empty command")

        started = self._clock()
        try:
            orch = self._orchestrator
            if orch is None:
                from jarvis.core.orchestrator import orchestrator as global_orch

                orch = global_orch
            result = await orch.process_user_query(command)
        except Exception as exc:
            ev = self._record(
                "relay.command",
                {
                    "status": "error",
                    "device_id": device["device_id"],
                    "command": command,
                    "error": str(exc),
                },
            )
            return TrustResult.fail(evidence=ev, description=f"command failed: {exc}")

        reply_data = result.get("response", {})
        if isinstance(reply_data, dict):
            reply = reply_data.get("message") or reply_data.get("reply") or str(reply_data)
        else:
            reply = str(reply_data)

        duration_ms = round((self._clock() - started) * 1000, 2)
        with self._lock:
            self.command_count += 1
        ev = self._record(
            "relay.command",
            {
                "status": "executed",
                "device_id": device["device_id"],
                "device_name": device["device_name"],
                "command": command,
                "task_id": result.get("task_id"),
                "orchestrator_status": result.get("status"),
                "reply": reply[:2000],
                "reply_preview": reply[:200],
                "duration_ms": duration_ms,
            },
        )
        trust = TrustResult.success(
            evidence=ev,
            description=f"command executed for {device['device_name']} in {duration_ms} ms",
        )
        trust.result = {"reply": reply, "task_id": result.get("task_id"), "status": result.get("status")}
        return trust

    # ------------------------------------------------------------------ #
    #  Status                                                             #
    # ------------------------------------------------------------------ #

    def status(self) -> Dict[str, Any]:
        voice_health: Dict[str, Any] = {}
        try:
            from jarvis.voice.daemon import voice_daemon

            voice_health = voice_daemon.health()
        except Exception as exc:  # pragma: no cover - voice stack optional
            voice_health = {"error": str(exc)}
        with self._lock:
            return {
                "paired_devices": len(self._tokens),
                "commands_relayed": self.command_count,
                "pending_pairing_codes": len(self._pairing),
                "evidence_count": len(self.evidence_log),
                "voice": voice_health,
                "timestamp": self._clock(),
            }


# Singleton used by the API routes
device_relay = DeviceRelay()
