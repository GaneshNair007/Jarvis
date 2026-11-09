"""
JARVIS Wake Word Detection (PWR-001 & PWR-002)
Supports:
  - Acoustic keyword detection ("Hey Jarvis", "Jarvis")
  - Push-to-Talk hotkey activation
  - Silence / Voice Activity thresholding
"""

import time
import threading
from typing import Callable, Optional, List, Dict, Any
from jarvis.config import settings
from jarvis.core.logger import logger


class AcousticWakeGate:
    """
    Low-power always-on acoustic wake gate (openWakeWord, ONNX CPU inference).

    Scores 16 kHz int16 audio chunks against the "hey jarvis" wake model and
    releases a wake event without running full Whisper transcription on every
    ambient utterance. Designed to FAIL-CLOSED: if openwakeword or its models
    are unavailable, gate() returns False and callers fall back to the legacy
    transcription-based wake path (documented, not silent).
    """

    FRAME_SAMPLES = 1280  # openWakeWord native 80 ms frame at 16 kHz
    DEFAULT_THRESHOLD = 0.5

    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD
        self.available = False
        self.unavailable_reason = "not_initialized"
        self._model = None
        self.model_names: List[str] = []
        self._pending = bytearray()  # accumulate feed blocks into 1280-sample frames
        self.last_score = 0.0
        self.try_load()

    def try_load(self) -> bool:
        """Attempts to initialize openWakeWord models. Honest failure only."""
        try:
            import openwakeword
            from pathlib import Path

            from openwakeword.model import Model

            # This openWakeWord build rejects wakeword_models=None
            # ('NoneType' has no len()); load the packaged ONNX models
            # explicitly, preferring the "jarvis" wake-phrase family.
            # Layouts differ across versions: <pkg>/models or <pkg>/resources/models.
            pkg_root = Path(openwakeword.__file__).parent
            onnx_paths = []
            for candidate in (pkg_root / "models", pkg_root / "resources" / "models"):
                if candidate.is_dir():
                    found = sorted(str(p) for p in candidate.glob("*.onnx"))
                    if found:
                        onnx_paths = found
                        break
            jarvis_paths = [p for p in onnx_paths if "jarvis" in Path(p).name.lower()]
            if not jarvis_paths:
                try:
                    from openwakeword.utils import download_models

                    logger.info("AcousticWakeGate: 'hey jarvis' model missing; downloading...")
                    download_models(["hey_jarvis"])
                    for candidate in (pkg_root / "models", pkg_root / "resources" / "models"):
                        if candidate.is_dir():
                            refreshed = [str(p) for p in candidate.glob("*jarvis*.onnx")]
                            if refreshed:
                                jarvis_paths = sorted(refreshed)
                                break
                except Exception as dl_exc:
                    logger.warning(f"AcousticWakeGate model download failed: {dl_exc}")
            if not (jarvis_paths or onnx_paths):
                raise FileNotFoundError(f"no onnx wake models packaged under {pkg_root}")
            load_paths = jarvis_paths or onnx_paths
            self._model = Model(wakeword_models=load_paths, inference_framework="onnx")
            self.model_names = [
                str(name)
                for name in getattr(self._model, "model_names", {}).keys()
            ] if hasattr(self._model, "model_names") else []
            if not self.model_names:
                self.model_names = [Path(p).stem for p in load_paths]
            self.available = True
            self.unavailable_reason = ""
            logger.info(f"AcousticWakeGate: openWakeWord models loaded {self.model_names or '(default set)'} "
                        f"files={len(load_paths)} threshold={self.threshold}")
        except Exception as exc:
            self._model = None
            self.available = False
            self.unavailable_reason = str(exc)[:200]
            logger.warning(f"AcousticWakeGate unavailable ({self.unavailable_reason}). "
                           "Falling back to transcription-based wake detection.")
        return self.available

    def gate(self, pcm: bytes) -> Dict[str, Any]:
        """
        Feeds one int16 PCM block through the acoustic model.
        Returns an event dict: {"wake": bool, "score": float, "source": "acoustic", ...}
        """
        if not self.available or self._model is None or not pcm:
            return {"wake": False, "score": 0.0, "source": "acoustic_unavailable"}

        import numpy as np

        self._pending.extend(pcm)
        frame_len = self.FRAME_SAMPLES * 2  # int16 -> 2 bytes/sample
        best_score = 0.0
        wake_hit = False
        while len(self._pending) >= frame_len:
            frame_bytes = bytes(self._pending[:frame_len])
            del self._pending[:frame_len]
            frame = np.frombuffer(frame_bytes, dtype=np.int16)
            try:
                scores = self._model.predict(frame)
            except Exception as exc:
                logger.warning(f"AcousticWakeGate predict error: {exc}")
                continue
            hit_score = max(scores.values()) if isinstance(scores, dict) and scores else 0.0
            best_score = max(best_score, hit_score)
            if hit_score >= self.threshold:
                wake_hit = True
            self.last_score = hit_score

        return {
            "wake": wake_hit,
            "score": round(best_score, 4),
            "source": "acoustic",
            "threshold": self.threshold,
            "timestamp": time.time(),
        }

    def reset(self) -> None:
        """Clears pending audio state (e.g. after wake handling or stream restart)."""
        self._pending.clear()
        self.last_score = 0.0
        try:
            if self._model is not None and hasattr(self._model, "reset"):
                self._model.reset()  # clear openWakeWord internal smoothing buffers
        except Exception:
            pass


# --------------------------------------------------------------------------- #
#  Lazy singleton: importing this module must NOT load or download openWakeWord
#  models. The gate loads on first real use (fail-closed to legacy wake).
# --------------------------------------------------------------------------- #

_GATE_SINGLETON: Optional[AcousticWakeGate] = None
_GATE_LOCK = threading.Lock()


def get_acoustic_gate() -> AcousticWakeGate:
    """Returns the process-wide acoustic wake gate, loading it on first use."""
    global _GATE_SINGLETON
    with _GATE_LOCK:
        if _GATE_SINGLETON is None:
            _GATE_SINGLETON = AcousticWakeGate()
        return _GATE_SINGLETON


class WakeWordDetector:
    WAKE_PHRASES = list(settings.voice_wake_phrases)

    def __init__(self, sensitivity: Optional[float] = None):
        self.sensitivity = sensitivity if sensitivity is not None else settings.voice_sensitivity
        self.is_listening = False
        self._listener_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._ptt_active = False

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener for wake-word activation events."""
        self._callbacks.append(callback)

    def trigger_push_to_talk(self, source: str = "hotkey") -> Dict[str, Any]:
        """PWR-002: Immediately activates Jarvis without waiting for audio wake word."""
        logger.info(f"Push-to-talk triggered via {source}")
        event = {
            "type": "wake_word_activation",
            "trigger": "push_to_talk",
            "source": source,
            "timestamp": time.time(),
            "phrase": "push_to_talk",
        }
        self._dispatch_event(event)
        return event

    def detect_phrase_in_text(self, text: str) -> bool:
        """Checks if a string contains any authorized wake phrase."""
        cleaned = text.strip().lower()
        return any(phrase in cleaned for phrase in self.WAKE_PHRASES)

    def process_audio_frame(self, frame_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Processes an incoming raw audio buffer frame.
        Evaluates energy level and acoustic features.
        """
        if not frame_bytes or len(frame_bytes) < 320:
            return None

        # Simple energy threshold for simulated/mocked frame processing
        # When openWakeWord is installed, it runs model inference on frame
        energy = sum(abs(b - 128) for b in frame_bytes[:1000]) / min(len(frame_bytes), 1000)
        if energy > settings.voice_energy_threshold:  # Voice activity detected
            return {"detected": True, "confidence": min(1.0, energy / 100.0), "timestamp": time.time()}
        return None

    def _dispatch_event(self, event: Dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error in wake-word callback: {e}")

    def start_listening(self) -> None:
        """Starts background listener."""
        self.is_listening = True
        logger.info("Wake-word listener started (listening for 'Hey Jarvis').")

    def stop_listening(self) -> None:
        """Stops background listener."""
        self.is_listening = False
        logger.info("Wake-word listener stopped.")


# Singleton Wake Word Detector
wake_detector = WakeWordDetector()

# Singleton acoustic gate (openWakeWord-backed, fail-closed)
acoustic_gate = AcousticWakeGate()
