"""
JARVIS Continuous Always-On Audio Daemon & Supervisor (R1 & PWR-001)
Monitors host-native speech recognition stream from PowerShell bridge, manages two-stage
wake/capture and compound utterances, routes commands to JarvisOrchestrator, and provides
simulation hooks for automated testing.
"""

import os
import sys
import time
import json
import asyncio
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from jarvis.config import settings
from jarvis.core.logger import logger
from jarvis.core.orchestrator import orchestrator
from jarvis.voice.wake import wake_detector
from jarvis.voice.tts import tts_engine
from jarvis.core.process_manager import process_manager


class AudioListenerDaemon:
    """
    Supervisor daemon for Windows native speech recognition.
    Supervises scripts/jarvis_speech_listener.ps1, monitors JSON-line events,
    handles wake-word state transitions, and dispatches commands to orchestrator.
    """

    WAKE_PHRASES = ["hey jarvis", "jarvis", "ok jarvis", "hey jervis", "jervis"]

    def __init__(
        self,
        script_path: Optional[Path] = None,
        command_timeout_sec: float = 7.0,
        enable_tts_feedback: bool = True,
        orchestrator_instance: Any = None,
    ):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.script_path = script_path or (base_dir / "scripts" / "jarvis_speech_listener.ps1")
        self.command_timeout_sec = command_timeout_sec
        self.enable_tts_feedback = enable_tts_feedback
        self.orchestrator = orchestrator_instance or orchestrator

        self.is_running = False
        self.current_state = "IDLE"  # IDLE, WOKE, CAPTURING, PROCESSING, SPEAKING
        self._wake_time = 0.0
        self._last_heartbeat = 0.0

        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._processed_commands: List[str] = []
        self._last_orchestrator_result: Optional[Dict[str, Any]] = None

    def register_event_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers listener for raw daemon events."""
        self._callbacks.append(callback)

    def _emit_event(self, event: Dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error in daemon event callback: {e}")

    # ─── Daemon Lifecycle ───────────────────────────────────────────────────

    def start(self, mode: str = "mic", wave_file: str = "") -> bool:
        """
        Starts the supervisor and launches the PowerShell listener bridge.
        Enforces single instance via ProcessManager.
        """
        if self.is_running:
            logger.info("AudioListenerDaemon is already running.")
            return True

        if not process_manager.acquire_pid("audio_daemon", os.getpid(), {"mode": mode}):
            logger.warning("Another audio daemon instance is already active.")
            return False

        self.is_running = True
        self.current_state = "IDLE"

        # Launch bridge process
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script_path),
            "-Mode",
            mode,
        ]
        if wave_file:
            cmd.extend(["-WaveFile", wave_file])

        logger.info(f"Starting PowerShell speech listener bridge: {' '.join(cmd)}")
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.error(f"Failed to launch PowerShell speech listener: {e}")
            self.is_running = False
            process_manager.release_pid("audio_daemon")
            return False

        # Start stdout reader thread
        self._reader_thread = threading.Thread(target=self._monitor_stream, daemon=True)
        self._reader_thread.start()
        process_manager.update_health("audio_daemon", "LISTENING", {"mode": mode})
        logger.info("AudioListenerDaemon successfully started.")
        return True

    def stop(self) -> None:
        """Cleanly stops bridge process and releases PID."""
        self.is_running = False
        self.current_state = "IDLE"

        if self._proc is not None:
            try:
                if self._proc.stdin and not self._proc.stdin.closed:
                    self._proc.stdin.write("quit\n")
                    self._proc.stdin.flush()
                self._proc.wait(timeout=3.0)
            except Exception:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=2.0)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
            self._proc = None

        process_manager.release_pid("audio_daemon")
        logger.info("AudioListenerDaemon stopped.")

    # ─── Stream Monitoring & Watchdog ──────────────────────────────────────

    def _monitor_stream(self) -> None:
        """Reads JSON lines emitted by PowerShell bridge."""
        if not self._proc or not self._proc.stdout:
            return

        while self.is_running and self._proc.poll() is None:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue

                try:
                    event = json.loads(line)
                    self._handle_bridge_event(event)
                except json.JSONDecodeError:
                    continue
            except Exception as e:
                logger.error(f"Error reading listener stream: {e}")
                break

        if self.is_running:
            logger.warning("PowerShell listener bridge terminated unexpectedly.")
            process_manager.log_telemetry("audio_daemon_unexpected_exit", {"code": self._proc.poll() if self._proc else None})

    # ─── Event Handling & State Machine ───────────────────────────────────

    def _handle_bridge_event(self, event: Dict[str, Any]) -> None:
        """Processes structured recognition event."""
        self._emit_event(event)
        ev_type = (event.get("event") or event.get("type", "")).upper()

        if ev_type == "HEARTBEAT":
            self._last_heartbeat = event.get("timestamp", time.time())
            process_manager.update_health("audio_daemon", "HEALTHY", {"last_heartbeat": self._last_heartbeat})
            # Check for command timeout if stuck in WOKE state
            if self.current_state == "WOKE" and (time.time() - self._wake_time > self.command_timeout_sec):
                logger.info("Command capture timed out in WOKE state. Returning to IDLE.")
                self.current_state = "IDLE"

        elif ev_type == "WAKE":
            phrase = event.get("phrase", "")
            full_text = event.get("full_text", "")
            logger.info(f"Wake word detected: '{phrase}' (full_text: '{full_text}')")
            wake_detector.trigger_push_to_talk(source="acoustic_wake_word")
            self._wake_time = time.time()

            # Check if this was a compound utterance (wake + command)
            cmd_suffix = ""
            if full_text:
                lower_full = full_text.lower().strip()
                for wp in self.WAKE_PHRASES:
                    if lower_full.startswith(wp):
                        cmd_suffix = full_text[len(wp):].strip(" ,.:;!")
                        break

            if cmd_suffix:
                logger.info(f"Compound utterance detected: command='{cmd_suffix}'")
                self._dispatch_command(cmd_suffix)
            else:
                self.current_state = "WOKE"
                if self.enable_tts_feedback:
                    tts_engine.speak_live("Yes?", async_mode=True)

        elif ev_type == "SPEECH":
            text = (event.get("text") or "").strip()
            if not text:
                return

            lower = text.lower()
            # Check if wake phrase is present in speech event
            matched_wake = None
            for wp in self.WAKE_PHRASES:
                if wp in lower:
                    matched_wake = wp
                    break

            if matched_wake:
                wake_detector.trigger_push_to_talk(source="acoustic_wake_word")
                self._wake_time = time.time()
                idx = lower.find(matched_wake) + len(matched_wake)
                cmd_suffix = text[idx:].strip(" ,.:;!")
                if cmd_suffix:
                    self._dispatch_command(cmd_suffix)
                else:
                    self.current_state = "WOKE"
                    if self.enable_tts_feedback:
                        tts_engine.speak_live("Yes?", async_mode=True)
            elif self.current_state == "WOKE":
                # User spoke command during capture window
                if time.time() - self._wake_time <= self.command_timeout_sec:
                    self._dispatch_command(text)
                else:
                    self.current_state = "IDLE"

        elif ev_type == "ERROR":
            err_msg = event.get("message", "Unknown audio error")
            logger.error(f"Listener bridge reported error: {err_msg}")
            process_manager.update_health("audio_daemon", "ERROR", {"error": err_msg})

    def _dispatch_command(self, command: str) -> None:
        """Dispatches recognized command to JarvisOrchestrator."""
        self.current_state = "PROCESSING"
        self._processed_commands.append(command)
        logger.info(f"Dispatching spoken command to orchestrator: '{command}'")

        async def _execute():
            try:
                res = await self.orchestrator.process_user_query(command)
                self._last_orchestrator_result = res
                reply = res.get("response", {})
                if isinstance(reply, dict):
                    msg = reply.get("message") or reply.get("reply") or str(reply)
                else:
                    msg = str(reply)

                self.current_state = "SPEAKING"
                if self.enable_tts_feedback and msg:
                    tts_engine.speak_live(msg, async_mode=True)
            except Exception as e:
                logger.error(f"Failed to orchestrate spoken command: {e}")
            finally:
                self.current_state = "IDLE"

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_execute())
        except RuntimeError:
            threading.Thread(target=lambda: asyncio.run(_execute()), daemon=True).start()

    # ─── Simulation API for Automated Testing ────────────────────────────────

    def simulate_speech_input(self, text: str, confidence: float = 0.95) -> None:
        """
        Simulates speech recognition input directly into the daemon.
        Used for automated unit and integration tests.
        """
        lower = text.lower().strip()
        is_wake = any(wp in lower for wp in self.WAKE_PHRASES)

        event = {
            "event": "WAKE" if is_wake and lower in self.WAKE_PHRASES else "SPEECH",
            "type": "WAKE" if is_wake and lower in self.WAKE_PHRASES else "SPEECH",
            "text": text,
            "phrase": text if is_wake and lower in self.WAKE_PHRASES else "",
            "confidence": confidence,
            "timestamp": time.time(),
        }
        self._handle_bridge_event(event)

    def simulate_event(self, event: Dict[str, Any]) -> None:
        """Injects a structured event directly into the listener."""
        self._handle_bridge_event(event)

    def get_status(self) -> Dict[str, Any]:
        """Returns listener daemon status metrics."""
        return {
            "running": self.is_running,
            "state": self.current_state,
            "pid": self._proc.pid if self._proc else None,
            "processed_count": len(self._processed_commands),
            "last_heartbeat": self._last_heartbeat,
        }


# Singleton Audio Listener Daemon
audio_daemon = AudioListenerDaemon()


def run_standalone():
    """Runs audio listener daemon as a standalone headless service."""
    daemon = AudioListenerDaemon()
    if not daemon.start(mode="mic"):
        sys.exit(1)

    print("JARVIS Audio Listener Daemon running. Press Ctrl+C to stop.")
    try:
        while daemon.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
        print("Daemon stopped.")


if __name__ == "__main__":
    run_standalone()
