"""
JARVIS Always-On Voice Daemon.

Continuously listens on the microphone for wake phrases ("Hey Jarvis"),
transcribes speech with faster-whisper, routes commands through the
orchestrator, and speaks replies via Windows SAPI.

Runs headless in the background - no browser, no localhost tab required.

Stage 1: Continuous microphone capture (sounddevice, 16 kHz mono PCM)
Stage 2: Energy-based voice activity detection and utterance segmentation
Stage 3: Real faster-whisper transcription of each detected utterance
Stage 4: Wake phrase matching and command extraction
Stage 5: Orchestrator execution with Evidence-backed results
Stage 6: SAPI spoken reply with barge-in interruption support

Every wake event and executed command is recorded as Evidence
(First Law: No Evidence, No Claim).
"""

from __future__ import annotations

import asyncio
import io
import os
import queue
import threading
import time
import uuid
import wave
from typing import Any, Callable, Dict, List, Optional

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("voice.daemon")

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy ships with faster-whisper
    np = None


def _resample_linear(pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Linear-interpolates mono int16 PCM between sample rates."""
    if src_rate == dst_rate or not pcm:
        return pcm
    if np is None:  # pragma: no cover - numpy always present in practice
        return pcm
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return pcm
    n_dst = max(1, int(round(samples.size * dst_rate / src_rate)))
    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_dst, endpoint=False)
    out = np.interp(x_new, x_old, samples)
    return np.clip(out, -32768, 32767).astype(np.int16).tobytes()


def probe_input_devices(
    duration_sec: float = 0.7,
    min_mean: float = 100.0,
    max_mean: float = 8000.0,
    max_clipped_frac: float = 0.01,
    min_nonzero_window_frac: float = 0.75,
) -> List[Dict[str, Any]]:
    """Records a short sample from every input device and classifies it.

    Measured with the SAME mechanism the daemon uses (sounddevice InputStream
    callbacks), because several Realtek devices on this host pass a one-shot
    `sd.rec` sample yet deliver ZERO live callbacks (12/20 measured on this
    machine). Status meanings (First Law - measured, not assumed):
      live   - sustained acoustic signal (noise floor >= min_mean, no dropouts,
               no full-scale glitching) -> safe for wake-word listening
      silent - stream delivers but carries near-digital silence (muted mic)
      glitch - full-scale noise or intermittent dropouts (driver fault)
      error  - device could not be opened OR never delivers callbacks
    """
    results: List[Dict[str, Any]] = []
    if np is None:  # pragma: no cover
        return results
    try:
        import sounddevice as sd
        import queue as _queue
        import time as _time
    except Exception as exc:  # pragma: no cover
        logger.warning(f"probe_input_devices: sounddevice unavailable: {exc}")
        return results

    devices = sd.query_devices()
    window = max(1, int(duration_sec * 4))  # 0.25 s windows
    for idx, info in enumerate(devices):
        if info.get("max_input_channels", 0) < 1:
            continue
        entry: Dict[str, Any] = {
            "index": idx,
            "name": info.get("name", ""),
            "hostapi": sd.query_hostapis(info.get("hostapi", 0)).get("name", ""),
            "default_rate": int(info.get("default_samplerate", 16000)),
        }
        # Probe at the rate the daemon would actually use (native), because
        # MME opens differ from WDM/WASAPI restrictions across this host.
        rate = entry["default_rate"]
        if rate < 8000:
            rate = 16000
        chunks: List[bytes] = []
        cb_hits = 0

        def _probe_cb(indata, frames, time_info, status):
            nonlocal cb_hits
            cb_hits += 1
            chunks.append(bytes(indata))

        audio = None
        try:
            with sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype="int16",
                device=idx,
                blocksize=max(1, int(rate * 0.1)),
                callback=_probe_cb,
            ):
                _time.sleep(duration_sec)
            if cb_hits > 0:
                audio = b"".join(chunks)
        except Exception:
            audio = None

        if audio is None or len(audio) < 2:
            entry["status"] = "error"
            entry["error"] = "open_failed" if cb_hits == 0 else "no_callbacks"
            results.append(entry)
            continue

        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
        mean = float(np.mean(np.abs(samples)))
        peak = float(np.max(np.abs(samples)))
        clipped_frac = float(np.mean(np.abs(samples) > 30000))
        win_len = max(1, len(samples) // window)
        nonzero = 0
        total_windows = 0
        for start in range(0, len(samples), win_len):
            chunk = samples[start : start + win_len]
            if chunk.size == 0:
                continue
            total_windows += 1
            if float(np.sqrt((chunk ** 2).mean())) > 5.0:
                nonzero += 1
        nonzero_frac = (nonzero / total_windows) if total_windows else 0.0

        entry.update(
            {
                "rate": rate,
                "mean": round(mean, 2),
                "peak": round(peak, 1),
                "clipped_frac": round(clipped_frac, 4),
                "nonzero_window_frac": round(nonzero_frac, 3),
            }
        )
        if mean < min_mean:
            entry["status"] = "silent"
            # Additive honesty: a NONZERO mean is a working microphone in a
            # quiet room (usable for wake listening); exact digital silence
            # with peak==0 is muted/hidden hardware (not usable).
            entry["usable"] = (mean > 0.0)
        elif mean >= max_mean or clipped_frac >= max_clipped_frac:
            entry["status"] = "glitch"
        elif nonzero_frac < min_nonzero_window_frac:
            entry["status"] = "glitch"
        else:
            entry["status"] = "live"
        results.append(entry)
    return results


def select_input_device(
    explicit: Optional[int] = None,
    probe: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Picks the best capture device: explicit/env > live shared-mode > live > default.

    Returns {"device": Optional[int], "name": str, "live": bool, "source": str, ...}
    """
    try:
        import sounddevice as sd
    except Exception:  # pragma: no cover
        return {"device": None, "name": "", "live": False, "source": "no_sounddevice"}

    default_idx = None
    try:
        default_idx = sd.default.device[0]
    except Exception:
        default_idx = None

    env_raw = os.environ.get("JARVIS_MIC_DEVICE", "").strip()
    if explicit is None and env_raw:
        try:
            explicit = int(env_raw)
        except ValueError:
            explicit = None
    if explicit is not None:
        try:
            info = sd.query_devices(explicit)
            return {
                "device": explicit,
                "name": info.get("name", ""),
                "live": False,  # not measured when forced
                "source": "explicit",
            }
        except Exception:
            pass

    if probe is None:
        probe = probe_input_devices()

    usable = [
        e for e in probe
        if (e.get("status") == "live" or e.get("usable") is True)
        and not any(tag in (e.get("name") or "").lower() for tag in ("stereo mix", "pc speaker"))
    ]
    if usable:
        # Intent-first selection (measured on this host): the physically
        # present far-field device is the Realtek "Microphone Array"; its MME
        # alias accepted 16 kHz but stalled, while native-rate capture flows
        # clean - the daemon resamples to 16 kHz in its callback.
        def rank(entry: Dict[str, Any]) -> tuple:
            name_l = (entry.get("name") or "").lower()
            tier = 0 if "array" in name_l else (1 if name_l.startswith("microphone") else 2)
            return (tier, -(entry.get("mean") or 0.0), entry.get("index", 0))

        ranked = sorted(usable, key=rank)
        head_api = ranked[0].get("hostapi", "")
        tier = [e for e in ranked if e.get("hostapi") == head_api] or ranked
        shared = [e for e in tier if e.get("hostapi") in ("MME", "Windows DirectSound", "Windows WASAPI")]
        chosen = (shared or tier or ranked)[0]
        return {
            "device": chosen["index"],
            "name": chosen.get("name", ""),
            "live": True,
            "source": "probe",
            "probe_entry": chosen,
        }

    name = ""
    if default_idx is not None:
        try:
            name = sd.query_devices(default_idx).get("name", "")
        except Exception:
            name = ""
    return {
        "device": default_idx,
        "name": name,
        "live": False,
        "source": "default_fallback",
        "probe_summary": {
            "live": 0,
            "silent": sum(1 for e in probe if e.get("status") == "silent"),
            "glitch": sum(1 for e in probe if e.get("status") == "glitch"),
            "error": sum(1 for e in probe if e.get("status") == "error"),
        },
    }


class VoiceDaemon:
    """Always-on wake-word voice daemon (PWR-006 family)."""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    BLOCK_MS = 100
    BLOCK_FRAMES = SAMPLE_RATE * BLOCK_MS // 1000
    SILENCE_END_SEC = 0.7
    TRAILING_SILENCE_SEC = 0.35
    MIN_SPEECH_SEC = 0.25
    MAX_COMMAND_SEC = 10.0
    MAX_QUEUE_BLOCKS = 300
    MEAN_ABS_THRESHOLD = 500.0

    SILENCE_END_BLOCKS = max(1, int(round(SILENCE_END_SEC * 1000 / BLOCK_MS)))
    TRAILING_SILENCE_BLOCKS = max(1, int(round(TRAILING_SILENCE_SEC * 1000 / BLOCK_MS)))
    MIN_SPEECH_BLOCKS = max(1, int(round(MIN_SPEECH_SEC * 1000 / BLOCK_MS)))
    MAX_COMMAND_BLOCKS = max(1, int(round(MAX_COMMAND_SEC * 1000 / BLOCK_MS)))

    STATES = ("IDLE", "LISTENING_FOR_WAKE", "CAPTURING_COMMAND", "PROCESSING", "SPEAKING")

    def __init__(
        self,
        audio_stream: Any = None,
        stt: Any = None,
        tts: Any = None,
        orchestrator: Any = None,
        wake_detector: Any = None,
        wake_phrases: Optional[List[str]] = None,
        speech_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        speak_replies: bool = True,
        mic_device: Optional[int] = None,
        probe_devices: bool = True,
        gate: Any = None,
        acoustic_gate_enabled: Optional[bool] = None,
    ):
        self.state = "IDLE"
        self.running = False

        self._audio_stream = audio_stream
        self._stt = stt
        self._tts = tts
        self._orchestrator = orchestrator
        self._wake = wake_detector
        self.wake_phrases = [
            p.lower().strip()
            for p in (wake_phrases or getattr(settings, "voice_wake_phrases", ["hey jarvis", "jarvis", "ok jarvis"]))
        ]
        self._speech_callback = speech_callback
        self._speak_replies = speak_replies
        self._mic_device = mic_device
        self._probe_devices = probe_devices
        self._gate = gate  # injectable for tests; lazily resolves to the global acoustic gate
        if acoustic_gate_enabled is None:
            # Env lever: JARVIS_ACOUSTIC_GATE=off restores the pure legacy wake
            # path (useful for deterministic test runs / constrained hosts).
            env_val = os.getenv("JARVIS_ACOUSTIC_GATE", "on").strip().lower()
            acoustic_gate_enabled = env_val not in ("0", "off", "false", "no", "disabled")
        self._gate_enabled = bool(acoustic_gate_enabled)
        self._gate_hit_in_utterance = False
        self._last_gate_score = 0.0
        self._gate_cooldown_until: float = 0.0
        self._capture_rate = self.SAMPLE_RATE
        self._mic_info: Dict[str, Any] = {"device": None, "name": "", "live": False, "source": "not_started"}

        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=self.MAX_QUEUE_BLOCKS)
        self._worker: Optional[threading.Thread] = None
        self._stream: Any = None
        self._running_flag = threading.Event()
        self._stats_lock = threading.Lock()

        self._buffer = bytearray()
        self._speech_blocks = 0
        self._silence_blocks = 0
        self._utterance_active = False

        self.wake_count = 0
        self.acoustic_wake_count = 0
        self.gated_utterance_count = 0
        self.command_count = 0
        self.error_count = 0
        self.last_wake_ts: Optional[float] = None
        self.last_transcript = ""
        self.last_reply = ""
        self.last_command = ""
        self.started_at: Optional[float] = None
        self.evidence_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    #  Component access (lazy)                                            #
    # ------------------------------------------------------------------ #

    @property
    def stt(self) -> Any:
        if self._stt is None:
            from jarvis.voice.stt import stt_engine
            self._stt = stt_engine
        return self._stt

    @property
    def tts(self) -> Any:
        if self._tts is None:
            from jarvis.voice.tts import tts_engine
            self._tts = tts_engine
        return self._tts

    @property
    def orchestrator(self) -> Any:
        if self._orchestrator is None:
            from jarvis.core.orchestrator import orchestrator as orch
            self._orchestrator = orch
        return self._orchestrator

    @property
    def wake(self) -> Any:
        if self._wake is None:
            from jarvis.voice.wake import wake_detector
            self._wake = wake_detector
        return self._wake

    @property
    def gate(self) -> Any:
        """Acoustic wake gate. Resolves to the process-wide singleton on first use;
        loading openWakeWord is deferred until real audio hits the gate."""
        if self._gate is None:
            from jarvis.voice.wake import get_acoustic_gate
            self._gate = get_acoustic_gate()
        return self._gate

    def _gate_ready(self) -> bool:
        """True when the acoustic gate is enabled and actually loaded/available.

        Every failure mode (disabled, not installed, model load failed) lands
        here as False, which restores the legacy transcription-based wake path
        (Whisper on every utterance). Fail-closed, never silent.
        """
        if not self._gate_enabled:
            return False
        if self._gate is None:
            return False  # not loaded yet: legacy path until audio arrives
        try:
            return bool(self._gate.available)
        except Exception:
            return False

    def _gate_ready_for_listening(self) -> bool:
        """Gate armed AND actively scoring right now.

        During the post-wake cooldown the acoustic gate is deliberately muted;
        the utterance short-circuit that skips Whisper must not treat that
        window as "gate listening" — transcription fallback covers it instead.
        """
        if time.time() < self._gate_cooldown_until:
            return False
        return self._gate_ready()

    @staticmethod
    def openwakeword_installed() -> bool:
        """Cheap availability probe (no model load): is openwakeword importable?"""
        try:
            import importlib.util
            return importlib.util.find_spec("openwakeword") is not None
        except Exception:
            return False

    def _run_gate(self, block: bytes) -> Optional[Dict[str, Any]]:
        """Feeds one block through the acoustic gate, lazily loading it on first use.

        Returns the gate event dict when the gate is armed, or None when the
        legacy transcription path applies (gate disabled/unavailable/failed).
        """
        now = time.time()
        if not self._gate_enabled:
            return None
        if now < self._gate_cooldown_until:
            # Post-wake suppression window (prevents model state re-triggering).
            return None
        if self._gate is None:
            try:
                _ = self.gate  # first-use resolve: loads openWakeWord once
            except Exception as exc:
                logger.warning(f"Acoustic wake gate init failed ({exc}); using transcription-based wake.")
                self._gate_enabled = False
                return None
        if not self._gate_ready():
            return None
        try:
            event = self._gate.gate(block)
        except Exception as exc:
            logger.warning(f"Acoustic gate error: {exc}")
            return None
        if str(event.get("source") or "") != "acoustic":
            return None
        return event

    def _sleep_gate(self, seconds: float = 2.5) -> None:
        """Post-wake suppression: cooldown window + clearing model state.

        After a wake or command the openWakeWord model still carries the
        phrase's smoothed activation; without this reset it can instantly
        re-trigger when the daemon returns to LISTENING_FOR_WAKE.
        """
        self._gate_cooldown_until = time.time() + seconds
        if self._gate is not None:
            try:
                self._gate.reset()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Evidence helpers                                                   #
    # ------------------------------------------------------------------ #

    def _record_evidence(self, source: str, data: Dict[str, Any]) -> Dict[str, Any]:
        from jarvis.core.evidence import Evidence
        evidence = Evidence(source=source, data=data, timestamp=time.time(), trust_level="verified")
        record = evidence.to_dict()
        with self._stats_lock:
            self.evidence_log.append(record)
            if len(self.evidence_log) > 500:
                self.evidence_log.pop(0)
        return record

    # ------------------------------------------------------------------ #
    #  Audio helpers                                                      #
    # ------------------------------------------------------------------ #

    def _energy(self, pcm: bytes) -> float:
        if not pcm or len(pcm) < 2:
            return 0.0
        if np is not None:
            samples = np.frombuffer(pcm, dtype=np.int16)
            if samples.size == 0:
                return 0.0
            return float(np.mean(np.abs(samples.astype(np.float32))))
        total = 0
        count = len(pcm) // 2
        for i in range(count):
            val = int.from_bytes(pcm[i * 2:i * 2 + 2], "little", signed=True)
            total += abs(val)
        return total / max(count, 1)

    def _pcm_to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(pcm)
        return buf.getvalue()

    def _transcribe(self, pcm: bytes) -> Dict[str, Any]:
        wav = self._pcm_to_wav(pcm)
        try:
            return self.stt.transcribe(wav, sample_rate=self.SAMPLE_RATE)
        except Exception as exc:
            logger.error(f"STT transcription failed: {exc}")
            with self._stats_lock:
                self.error_count += 1
            return {"text": "", "confidence": 0.0, "error": str(exc)}

    def _strip_wake(self, text: str) -> str:
        low = text.lower().strip()
        for phrase in sorted(self.wake_phrases, key=len, reverse=True):
            idx = low.find(phrase)
            if idx >= 0:
                remainder = text[idx + len(phrase):]
                return remainder.strip(" ,.!?;:")
        return ""

    # ------------------------------------------------------------------ #
    #  Core utterance state machine                                       #
    # ------------------------------------------------------------------ #

    def feed(self, block: bytes) -> List[Dict[str, Any]]:
        """Processes one PCM block. Returns a list of emitted events.

        Timing is block-count based (each block spans BLOCK_MS), so utterance
        segmentation behaves identically for real-time microphone streams and
        directly-injected test audio.
        """
        events: List[Dict[str, Any]] = []
        if not block:
            return events

        energy = self._energy(block)
        now = time.time()
        is_speech = energy >= self.MEAN_ABS_THRESHOLD

        if self.state == "IDLE":
            return events

        if self.state == "SPEAKING":
            if is_speech and energy >= self.MEAN_ABS_THRESHOLD * 2:
                try:
                    self.tts.cancel_speech()
                except Exception:
                    pass
                self._reset_buffer()
                self.state = "LISTENING_FOR_WAKE"
                self._sleep_gate()  # suppress TTS-echo activation remnants
                event = {"type": "barge_in", "energy": round(energy, 1), "timestamp": now}
                self._emit(event, events)
            return events

        if self.state == "PROCESSING":
            return events

        # Acoustic wake gate: scored on EVERY block while listening (speech and
        # silence). Required by the model's behavior: "hey jarvis" scores climb
        # through the phrase and persist across trailing frames, so the verdict
        # lands on post-phrase frames (measured: 0.93-0.9986 on trailing
        # silence). The low-power win over legacy is skipping Whisper, not
        # skipping frames. Barge-in suppression is inherent: while SPEAKING/
        # PROCESSING the gate is not fed at all.
        if self.state == "LISTENING_FOR_WAKE":
            gate_event = self._run_gate(block)
            if gate_event is not None:
                score = float(gate_event.get("score") or 0.0)
                if score > self._last_gate_score:
                    self._last_gate_score = score
                if gate_event.get("wake"):
                    self._gate_hit_in_utterance = True
                    self._record_evidence(
                        source="voice_daemon.acoustic_wake_frame",
                        data={"score": score, "threshold": gate_event.get("threshold")},
                    )

        if is_speech:
            if not self._utterance_active:
                self._utterance_active = True
                self._speech_blocks = 0
                self._silence_blocks = 0
                self._buffer.clear()
                self._gate_hit_in_utterance = False
            self._speech_blocks += 1
            self._silence_blocks = 0
            self._buffer.extend(block)
            return events

        if not self._utterance_active:
            return events

        self._silence_blocks += 1
        if self._silence_blocks <= self.TRAILING_SILENCE_BLOCKS:
            self._buffer.extend(block)

        total_blocks = self._speech_blocks + self._silence_blocks
        command_maxed = self.state == "CAPTURING_COMMAND" and total_blocks >= self.MAX_COMMAND_BLOCKS
        utterance_end = (
            self._silence_blocks >= self.SILENCE_END_BLOCKS
            or command_maxed
        )

        if not utterance_end:
            return events

        if self._speech_blocks >= self.MIN_SPEECH_BLOCKS or command_maxed:
            if (
                self.state == "LISTENING_FOR_WAKE"
                and self._gate_ready_for_listening()
                and not self._gate_hit_in_utterance
            ):
                # Acoustic gate armed and this utterance scored below threshold:
                # ambient speech never reaches Whisper (the low-power path).
                with self._stats_lock:
                    self.gated_utterance_count += 1
                self._reset_buffer()
                return events
            pcm = bytes(self._buffer)
            self._reset_buffer()
            events.extend(self._handle_utterance(pcm))
        else:
            self._reset_buffer()
        return events

    def _handle_utterance(self, pcm: bytes) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        result = self._transcribe(pcm)
        text = (result.get("text") or "").strip()
        with self._stats_lock:
            self.last_transcript = text
        if not text and not (self.state == "LISTENING_FOR_WAKE" and self._gate_hit_in_utterance):
            return events

        if self.state == "LISTENING_FOR_WAKE":
            gate_hit = self._gate_hit_in_utterance
            self._gate_hit_in_utterance = False
            phrase_match = any(p in text.lower() for p in self.wake_phrases)
            if not phrase_match and not gate_hit:
                return events

            acoustic_only = gate_hit and not phrase_match
            self.wake_count += 1
            if gate_hit:
                self.acoustic_wake_count += 1
            self.last_wake_ts = time.time()
            if phrase_match:
                self._record_evidence(
                    source="voice_daemon.wake",
                    data={
                        "transcript": text,
                        "confidence": result.get("confidence", 0.0),
                        "acoustic_confirmed": bool(gate_hit),
                        "source": "transcription+acoustic" if gate_hit else "transcription",
                    },
                )
            else:
                self._record_evidence(
                    source="voice_daemon.wake_acoustic",
                    data={
                        "transcript": text,
                        "acoustic_score": self._last_gate_score,
                        "confidence": result.get("confidence", 0.0),
                        "source": "acoustic",
                    },
                )
            if self._gate_ready():
                self._sleep_gate()  # clear model state so the phrase can't re-trigger
            command = self._strip_wake(text) if phrase_match else text
            if command:
                events.extend(self._execute_command(command, trigger="wake_with_command", wake_transcript=text))
            else:
                self.state = "CAPTURING_COMMAND"
                event = {
                    "type": "wake_detected",
                    "source": "acoustic" if acoustic_only else "transcription",
                    "transcript": text,
                    "timestamp": self.last_wake_ts,
                }
                self._emit(event, events)
            return events

        if self.state == "CAPTURING_COMMAND":
            events.extend(self._execute_command(text, trigger="command_capture", wake_transcript=""))
            return events

        return events

    def _execute_command(self, command: str, trigger: str, wake_transcript: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        self.state = "PROCESSING"
        with self._stats_lock:
            self.last_command = command
        start = time.time()

        try:
            try:
                orch_result = asyncio.run(self.orchestrator.process_user_query(command))
            except RuntimeError as loop_err:
                if "running event loop" not in str(loop_err):
                    raise
                loop = asyncio.new_event_loop()
                try:
                    orch_result = loop.run_until_complete(self.orchestrator.process_user_query(command))
                finally:
                    loop.close()
        except Exception as exc:
            with self._stats_lock:
                self.error_count += 1
            self.state = "LISTENING_FOR_WAKE"
            self._sleep_gate()
            self._record_evidence(
                source="voice_daemon.command",
                data={"command": command, "status": "error", "error": str(exc)},
            )
            event = {"type": "command_failed", "command": command, "error": str(exc)}
            self._emit(event, events)
            return events

        reply_data = orch_result.get("response", {})
        if isinstance(reply_data, dict):
            reply_text = reply_data.get("message") or reply_data.get("reply") or reply_data.get("type") or str(reply_data)
        else:
            reply_text = str(reply_data)

        duration_ms = round((time.time() - start) * 1000, 2)
        with self._stats_lock:
            self.command_count += 1
            self.last_reply = reply_text
        self._record_evidence(
            source="voice_daemon.command",
            data={
                "command": command,
                "task_id": orch_result.get("task_id"),
                "status": orch_result.get("status"),
                "reply_preview": reply_text[:200],
                "duration_ms": duration_ms,
            },
        )

        self.state = "SPEAKING"
        self._sleep_gate()  # speaking window: gate idle, clear activation remnants
        if self._speak_replies and reply_text:
            try:
                self.tts.speak_live(reply_text, async_mode=True)
                estimated = min(15.0, 0.5 + 0.06 * len(reply_text))
                timer = threading.Timer(estimated, self._end_speaking)
                timer.daemon = True
                timer.start()
            except Exception as exc:
                logger.warning(f"TTS speak failed: {exc}")
                self.state = "LISTENING_FOR_WAKE"
        else:
            self.state = "LISTENING_FOR_WAKE"

        event = {
            "type": "command_executed",
            "trigger": trigger,
            "wake_transcript": wake_transcript,
            "command": command,
            "task_id": orch_result.get("task_id"),
            "status": orch_result.get("status"),
            "reply_text": reply_text,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        }
        self._emit(event, events)
        return events

    def _end_speaking(self) -> None:
        if self.state == "SPEAKING":
            self.state = "LISTENING_FOR_WAKE"
            self._sleep_gate()

    def _reset_buffer(self) -> None:
        self._buffer.clear()
        self._speech_blocks = 0
        self._silence_blocks = 0
        self._utterance_active = False

    def _emit(self, event: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
        events.append(event)
        logger.info(f"VoiceDaemon event: {event.get('type')} - {str(event)[:160]}")
        if self._speech_callback:
            try:
                self._speech_callback(event)
            except Exception as exc:
                logger.error(f"Speech callback error: {exc}")

    # ------------------------------------------------------------------ #
    #  Microphone / worker lifecycle                                      #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # pragma: no cover - device dependent
        if status:
            logger.warning(f"Audio stream status: {status}")
        try:
            raw = bytes(indata)
            if self._capture_rate != self.SAMPLE_RATE and np is not None:
                raw = _resample_linear(raw, self._capture_rate, self.SAMPLE_RATE)
            self._queue.put_nowait(raw)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(raw)
            except queue.Full:
                pass

    def _worker_loop(self) -> None:
        while self._running_flag.is_set():
            try:
                block = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.feed(block)
            except Exception as exc:
                with self._stats_lock:
                    self.error_count += 1
                logger.error(f"Voice worker error: {exc}")

    def start(self, use_microphone: bool = True) -> Dict[str, Any]:
        if self.running:
            return self.health()

        self._running_flag.set()
        self.state = "LISTENING_FOR_WAKE"
        self._sleep_gate(0.0)  # fresh start: arm the gate immediately
        self.started_at = time.time()

        self._worker = threading.Thread(target=self._worker_loop, name="jarvis-voice-worker", daemon=True)
        self._worker.start()

        mic_opened = False
        if use_microphone:
            try:
                import sounddevice as sd

                probe = probe_input_devices() if self._probe_devices else []
                selection = select_input_device(explicit=self._mic_device, probe=probe)
                self._mic_info = selection
                device = selection.get("device")

                # Resolve a capture rate the selected device accepts. Measured on
                # this host (First Law evidence): opening directly at 16 kHz on
                # 44.1/48 kHz-native devices produced stream status errors and
                # delayed delivery, while native-rate capture flows clean -
                # so capture at the device's native rate and resample to 16 kHz
                # in the callback (pipelines and tests inject 16k PCM directly).
                capture_rate = self.SAMPLE_RATE
                if device is not None:
                    try:
                        dev_info = sd.query_devices(device)
                        native = int(dev_info.get("default_samplerate", self.SAMPLE_RATE) or self.SAMPLE_RATE)
                        if native in (44100, 48000, 96000, 22050, 24000):
                            capture_rate = native
                    except Exception:
                        capture_rate = self.SAMPLE_RATE

                self._capture_rate = capture_rate
                block_frames = max(1, int(capture_rate * self.BLOCK_MS // 1000))
                self._stream = sd.InputStream(
                    samplerate=capture_rate,
                    channels=self.CHANNELS,
                    dtype="int16",
                    blocksize=block_frames,
                    device=device,
                    callback=self._audio_callback,
                )
                self._stream.start()
                mic_opened = True
                self._mic_info = {
                    **selection,
                    "rate": capture_rate,
                    "resampled_to": self.SAMPLE_RATE,
                }
                logger.info(
                    f"VoiceDaemon microphone opened: device={device} "
                    f"({selection.get('name', '?')}) rate={capture_rate} Hz "
                    f"source={selection.get('source')} live={selection.get('live')}"
                )
                if selection.get("source") == "default_fallback" and selection.get("probe_summary"):
                    logger.warning(
                        "No live microphone detected by probe "
                        f"({selection['probe_summary']}). Check the hardware "
                        "privacy shutter / Fn mic-mute key."
                    )
            except Exception as exc:
                logger.error(f"VoiceDaemon microphone open failed: {exc}")
                with self._stats_lock:
                    self.error_count += 1
                self._mic_info = {**self._mic_info, "error": str(exc)}

        self.running = True
        self._record_evidence(
            source="voice_daemon.started",
            data={
                "microphone": mic_opened,
                "mic": self._mic_info,
                "wake_phrases": self.wake_phrases,
                "pid": uuid.uuid4().hex[:8],
            },
        )
        logger.info(
            f"VoiceDaemon started (mic={mic_opened}, state={self.state}, "
            f"wake_phrases={self.wake_phrases})"
        )
        return self.health()

    def stop(self) -> Dict[str, Any]:
        self.running = False
        self._running_flag.clear()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3.0)
        self._worker = None
        self.state = "IDLE"
        self._reset_buffer()
        self._gate_hit_in_utterance = False
        if self._gate is not None:
            try:
                self._gate.reset()
            except Exception:
                pass
        self._record_evidence(source="voice_daemon.stopped", data={"state": "IDLE"})
        logger.info("VoiceDaemon stopped.")
        return self.health()

    def health(self) -> Dict[str, Any]:
        with self._stats_lock:
            return {
                "running": self.running,
                "state": self.state,
                "microphone_open": self._stream is not None,
                "mic_device": self._mic_info.get("device"),
                "mic_device_name": self._mic_info.get("name", ""),
                "mic_live": self._mic_info.get("live", False),
                "mic_source": self._mic_info.get("source", ""),
                "mic_capture_rate": self._capture_rate,
                "wake_phrases": self.wake_phrases,
                "wake_count": self.wake_count,
                "acoustic_gate_enabled": self._gate_enabled,
                "acoustic_gate_installed": self.openwakeword_installed(),
                "acoustic_gate_armed": self._gate_ready(),
                "acoustic_gate_engine": "openwakeword-onnx" if self._gate_ready() else None,
                "acoustic_gate_model": (
                    (self._gate.model_names or ["(default set)"])[0]
                    if self._gate is not None and self._gate_ready() else None
                ),
                "acoustic_gate_threshold": (
                    self._gate.threshold if self._gate is not None and self._gate_ready() else None
                ),
                "acoustic_gate_unavailable_reason": (
                    (self._gate.unavailable_reason or None) if self._gate is not None
                    and not self._gate_ready() and self._gate_enabled else None
                ),
                "acoustic_wake_count": self.acoustic_wake_count,
                "gated_utterance_count": self.gated_utterance_count,
                "last_acoustic_score": self._last_gate_score,
                "command_count": self.command_count,
                "error_count": self.error_count,
                "last_wake_ts": self.last_wake_ts,
                "last_transcript": self.last_transcript,
                "last_command": self.last_command,
                "last_reply": self.last_reply,
                "evidence_count": len(self.evidence_log),
                "started_at": self.started_at,
                "sample_rate": self.SAMPLE_RATE,
                "stt_backend": "faster-whisper",
                "tts_backend": "windows_sapi",
            }


# Singleton always-on voice daemon
voice_daemon = VoiceDaemon()


def main() -> None:  # pragma: no cover - interactive entrypoint
    """Entry point for `python -m jarvis.voice.daemon` background service."""
    daemon = VoiceDaemon()
    health = daemon.start(use_microphone=True)
    print(f"[JARVIS Voice Daemon] {health}")
    try:
        while daemon.running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
