"""Daemon → HUD state bridge (pure JSON, no GUI imports).

Written by VoiceDaemon at every state transition; polled by the overlay
process. Deliberately tiny and side-effect-safe:
- writes are atomic-ish (tmp + os.replace) so the reader never sees a
  half-written file;
- anything unparseable or stale (>30 s) is treated as "hide".
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
HUD_STATE_PATH = REPO_ROOT / "data" / "logs" / "daemon_state.json"
STALE_SECONDS = 30.0

_VISIBLE_STATES = {"CAPTURING_COMMAND", "PROCESSING", "SPEAKING"}


def write_hud_state(data: Dict[str, Any]) -> None:
    """Persists one HUD snapshot. Fail-closed: never raises."""
    try:
        HUD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(data)
        payload["ts"] = time.time()
        tmp = HUD_STATE_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
        os.replace(tmp, HUD_STATE_PATH)
    except Exception:
        pass  # HUD is cosmetic; the voice pipeline must never die for it


def read_hud_state() -> Dict[str, Any]:
    """Returns the last snapshot, or {} when missing/invalid/stale."""
    try:
        with open(HUD_STATE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    try:
        ts = float(data.get("ts") or 0.0)
    except Exception:
        return {}
    if time.time() - ts > STALE_SECONDS:
        return {}
    return data


def should_show(state: Optional[str]) -> bool:
    """HUD pops while capturing/processing/speaking only."""
    return str(state or "").upper() in _VISIBLE_STATES


def is_stale(data: Dict[str, Any], now: Optional[float] = None) -> bool:
    try:
        ts = float((data or {}).get("ts") or 0.0)
    except Exception:
        return True
    return (time.time() if now is None else now) - ts > STALE_SECONDS
