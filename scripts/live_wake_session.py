"""ALWAYS-ON LISTENING SESSION: 120 s of the real wake pipeline, evidence to JSON.

Wake word path is FULLY REAL:
  Realtek mic array -> openWakeWord (hey jarvis) -> faster-whisper ->
  real orchestrator (NVIDIA NIM) -> SAPI spoken reply.

Run this, then SAY "Hey Jarvis" out loud. Everything the daemon hears,
scores, and decides is written to evidence file - honesty by construction.
"""

import json
import sys
import time
from datetime import datetime

sys.path.insert(0, "D:/jarvis")
from dotenv import load_dotenv

load_dotenv("D:/jarvis/.env")

EVIDENCE_PATH = r"D:\jarvis\data\logs\acoustic_wake_session.json"

from jarvis.voice.daemon import VoiceDaemon

# REAL orchestrator (routes through NVIDIA/groq/local per its router):
from jarvis.core.orchestrator import orchestrator as real_orch


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
    daemon = VoiceDaemon(
        orchestrator=real_orch,
        speak_replies=True,  # REAL SAPI voice answers rompts
        probe_devices=True,
    )

    gate_scores: list = []
    orig_run_gate = daemon._run_gate
    started = time.time()

    def logged_gate(block):
        ev = orig_run_gate(block)
        if ev is not None and float(ev.get("score") or 0.0) > 0.1:
            gate_scores.append({"t": round(time.time() - started, 1), "score": ev.get("score"), "wake": ev.get("wake")})
        return ev

    daemon._run_gate = logged_gate

    init = daemon.start(use_microphone=True)
    print("=== JARVIS ALWAYS-ON LISTENING (%.0fs) ===" % duration, flush=True)
    print(
        "MIC:",
        init.get("mic_device_name"),
        "| rate:",
        init.get("mic_capture_rate"),
        "| mic_live:",
        init.get("mic_live"),
        flush=True,
    )
    print("SAY IT NOW: 'Hey Jarvis' - I will reply out loud when I hear you.", flush=True)

    end = time.time() + duration
    last_cmd_count = 0
    while time.time() < end:
        time.sleep(2)
        h = daemon.health()
        line = "t=%4.0fs state=%s score>0.1=%d wakes=%d cmds=%d last=%r" % (
            time.time() - started,
            h["state"],
            len(gate_scores),
            h["wake_count"],
            h["command_count"],
            h["last_command"][:40],
        )
        print(line, flush=True)

    daemon.stop()
    h = daemon.health()

    report = {
        "session_utc": datetime.utcnow().isoformat(),
        "duration_sec": duration,
        "mic_device": init.get("mic_device_name"),
        "mic_rate": init.get("mic_capture_rate"),
        "mic_live": init.get("mic_live"),
        "acoustic_engine": h.get("acoustic_gate_engine"),
        "acoustic_model": h.get("acoustic_gate_model"),
        "acoustic_threshold": h.get("acoustic_gate_threshold"),
        "wake_count": h["wake_count"],
        "acoustic_wake_count": h["acoustic_wake_count"],
        "command_count": h["command_count"],
        "gated_utterance_count": h["gated_utterance_count"],
        "error_count": h["error_count"],
        "last_transcript": h["last_transcript"],
        "last_command": h["last_command"],
        "last_reply": h["last_reply"],
        "gate_scores_above_0.1": gate_scores[:80],
        "wake_evidence": [
            {"source": e.get("source"), "data": e.get("data")}
            for e in daemon.evidence_log
            if "wake" in str(e.get("source", ""))
        ],
    }
    import os

    os.makedirs(os.path.dirname(EVIDENCE_PATH), exist_ok=True)
    with open(EVIDENCE_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(
        "SESSION DONE:",
        json.dumps(
            {
                k: report[k]
                for k in ("wake_count", "acoustic_wake_count", "command_count", "last_transcript", "last_reply")
            },
            default=str,
        )[:400],
        flush=True,
    )
    print("EVIDENCE:", EVIDENCE_PATH, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
