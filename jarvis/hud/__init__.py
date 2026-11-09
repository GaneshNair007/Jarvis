"""JARVIS Iron Man HUD overlay + the daemon→HUD state bridge.

The daemon never imports tkinter (its own event loop must stay GUI-free);
instead it drops a tiny JSON state file (``data/logs/daemon_state.json``) and
this package's overlay process polls it. Missing/stale/invalid files mean
"hide the HUD" — every failure is fail-closed to a quiet machine.
"""

from jarvis.hud.state import (
    HUD_STATE_PATH,
    read_hud_state,
    write_hud_state,
    is_stale,
)

__all__ = ["HUD_STATE_PATH", "read_hud_state", "write_hud_state", "is_stale"]
