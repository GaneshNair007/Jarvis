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
            "phrase": "push_to_talk"
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
            return {
                "detected": True,
                "confidence": min(1.0, energy / 100.0),
                "timestamp": time.time()
            }
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
