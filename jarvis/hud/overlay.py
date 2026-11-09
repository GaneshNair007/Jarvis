"""JARVIS Iron Man HUD — the arc reactor that pops on wake.

Frameless, always-on-top, bottom-center overlay. Polls data/logs/
daemon_state.json (written by VoiceDaemon) every 300 ms:

  state == CAPTURING_COMMAND  ->  "LISTENING"  cyan arc-reactor pulse
  state == PROCESSING         ->  "THINKING"   amber rotation
  state == SPEAKING           ->  "DONE"       green settle
  anything else / stale file  ->  hidden

Fail-closed: any error hides the HUD. Never steals focus, never activates
the window, never blocks input. Run: `python -m jarvis.hud.overlay`.
"""
from jarvis.hud.state import read_hud_state

import math
import time

TRANSPARENT = "#020203"      # chroma-keyed out on Windows
CYAN = "#00d4ff"
CYAN_DIM = "#034b5e"
AMBER = "#ffb300"
AMBER_DIM = "#5e4103"
GREEN = "#00ff9d"
GREEN_DIM = "#035e3d"
GREY = "#1a2129"
RING_W = 320
RING_H = 300

try:
    import tkinter as tk
except Exception as exc:  # pragma: no cover - host dependent
    raise SystemExit(f"tkinter required for the HUD overlay: {exc}")


class JarvisHUD:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("JARVIS HUD")
        self.root.overrideredirect(True)                 # frameless
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass                                        # non-Windows: plain dark
        self.root.configure(bg=TRANSPARENT)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{RING_W}x{RING_H}+{(sw - RING_W) // 2}+{sh - RING_H - 96}")

        self.canvas = tk.Canvas(
            self.root, width=RING_W, height=RING_H,
            bg=TRANSPARENT, highlightthickness=0,
        )
        self.canvas.pack()

        self.visible = False
        self.mode = "LISTENING"
        self.phase = 0.0
        self.dismiss_at = None          # float epoch or None
        self._last_wake_seen = 0.0

        self.root.withdraw()
        self._tick()

    # ------------------------------------------------------------------
    def run(self):
        self.root.mainloop()

    # ------------------------------------------------------------------
    def _tick(self):
        try:
            self._update()
        except Exception:
            self._hide()
        self.root.after(300, self._tick)

    def _update(self):
        data = read_hud_state()
        state = str(data.get("state") or "").upper()
        wake_at = data.get("wake_at") or 0.0

        # Done-dismiss window after the active phase ends.
        if self.dismiss_at and time.time() >= self.dismiss_at:
            self._hide()
            self.dismiss_at = None

        if state == "CAPTURING_COMMAND":
            self.mode, self.phase = "LISTENING", self.phase + 0.18
            self._show()
        elif state == "PROCESSING":
            self.mode, self.phase = "THINKING", self.phase + 0.30
            self._show()
        elif state == "SPEAKING":
            self.mode, self.phase = "DONE", self.phase + 0.06
            self._show()
            if not self.dismiss_at:
                self.dismiss_at = time.time() + 3.2
        else:
            if self.visible and wake_at and wake_at != self._last_wake_seen:
                self._last_wake_seen = wake_at
                self.dismiss_at = time.time() + 2.0     # brief "wake acknowledged" flash
                self.mode = "DONE"
            if not self.dismiss_at:
                self._hide()
            else:
                self._redraw()
            return

        if wake_at:
            self._last_wake_seen = wake_at
        self._redraw()

    # ------------------------------------------------------------------
    def _show(self):
        if not self.visible:
            self.visible = True
            self.root.deiconify()
            self.root.lift()
            # keep topmost even over fullscreen apps, without activating
            try:
                self.root.attributes("-topmost", True)
            except tk.TclError:
                pass

    def _hide(self):
        if self.visible:
            self.visible = False
            self.root.withdraw()

    # ------------------------------------------------------------------
    def _redraw(self):
        if not self.visible:
            return
        c = self.canvas
        c.delete("all")
        cx, cy = RING_W // 2, 132
        colors = {"LISTENING": CYAN, "THINKING": AMBER, "DONE": GREEN}
        dims = {"LISTENING": CYAN_DIM, "THINKING": AMBER_DIM, "DONE": GREEN_DIM}
        accent = colors.get(self.mode, CYAN)
        dim = dims.get(self.mode, CYAN_DIM)

        pulse = 1.0 + 0.055 * math.sin(self.phase * 2.2)
        r_out = int(112 * pulse)

        # Outer halo rings (dim -> accent)
        c.create_oval(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                      outline=dim, width=2)
        r_mid = int(88 * pulse)
        c.create_oval(cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid,
                      outline=accent, width=3)

        # Rotating arc segments — the "working" glow.
        rotation = self.phase * 0.9
        for i in range(3):
            start = math.degrees(rotation + i * (2 * math.pi / 3))
            c.create_arc(cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid,
                         start=start, extent=70, style="arc",
                         outline="#e6fbff" if self.mode == "LISTENING" else
                                 (AMBER if self.mode == "THINKING" else GREEN),
                         width=5)

        # Inner fill + core
        r_core = int(42 * (1.0 + 0.16 * math.sin(self.phase * 3.0)))
        c.create_oval(cx - 58, cy - 58, cx + 58, cy + 58, fill=GREY, outline=accent, width=1)
        c.create_oval(cx - r_core, cy - r_core, cx + r_core, cy + r_core,
                      fill=accent, outline="")

        # Ticks
        for i in range(12):
            ang = math.radians(i * 30)
            r1, r2 = 66, 74 if i % 3 else 82
            c.create_line(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang),
                          cx + r2 * math.cos(ang), cy + r2 * math.sin(ang),
                          fill=dim, width=2)

        # Label
        label = {"LISTENING": "LISTENING", "THINKING": "THINKING", "DONE": "READY"}.get(self.mode, "LISTENING")
        c.create_text(cx, RING_H - 34, text="J A R V I S", fill=accent,
                      font=("Segoe UI Semibold", 17, "bold"))
        c.create_text(cx, RING_H - 12, text=label, fill=accent,
                      font=("Segoe UI", 10))


def main() -> None:
    JarvisHUD().run()


if __name__ == "__main__":
    main()
