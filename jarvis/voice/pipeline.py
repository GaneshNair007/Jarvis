"""
JARVIS Full-Duplex Voice Pipeline (PWR-005)
Manages the end-to-end voice loop:
  Wake Detection -> Audio Capture -> STT -> Intent Processing -> TTS Output
Includes real-time barge-in interruption handling.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from jarvis.core.logger import logger
from jarvis.voice.wake import wake_detector
from jarvis.voice.stt import stt_engine
from jarvis.voice.tts import tts_engine
from jarvis.core.orchestrator import orchestrator

class FullDuplexVoicePipeline:
    STATES = ["IDLE", "LISTENING", "PROCESSING", "SPEAKING"]

    def __init__(self):
        self.wake = wake_detector
        self.stt = stt_engine
        self.tts = tts_engine
        self.orchestrator = orchestrator
        self.current_state = "IDLE"
        self._setup_wake_hook()

    def _setup_wake_hook(self) -> None:
        self.wake.register_callback(self._on_wake_activation)

    def _on_wake_activation(self, event: Dict[str, Any]) -> None:
        logger.info(f"Voice Pipeline: Wake event received ({event.get('trigger')})")
        if self.current_state == "SPEAKING":
            self.handle_barge_in()
        self.current_state = "LISTENING"

    def handle_barge_in(self) -> None:
        """Interrupts speech synthesis immediately when user starts speaking."""
        logger.info("Voice Pipeline: User barge-in detected! Aborting speech.")
        self.tts.cancel_speech()
        self.current_state = "LISTENING"

    async def process_voice_turn(self, audio_bytes: bytes, play_audio_live: bool = False) -> Dict[str, Any]:
        """
        Executes a single conversational voice turn:
        1. STT: Transcribe user audio
        2. Orchestration: Route query & execute
        3. TTS: Synthesize speech response
        """
        start_time = time.time()
        self.current_state = "PROCESSING"

        # 1. Transcribe
        stt_result = self.stt.transcribe(audio_bytes)
        user_text = stt_result.get("text", "").strip()
        logger.info(f"Voice Pipeline Transcribed: '{user_text}'")

        if not user_text:
            self.current_state = "IDLE"
            return {"status": "empty_input", "reply_text": "", "audio_bytes": b""}

        # 2. Orchestration & Execution
        orch_result = await self.orchestrator.process_user_query(user_text)

        # Extract reply text
        reply_data = orch_result.get("response", {})
        if isinstance(reply_data, dict):
            reply_text = reply_data.get("message") or reply_data.get("reply") or str(reply_data)
        else:
            reply_text = str(reply_data)

        # 3. TTS Synthesis
        self.current_state = "SPEAKING"
        if play_audio_live:
            self.tts.speak_live(reply_text, async_mode=True)
            wav_bytes = b""
        else:
            wav_bytes = self.tts.synthesize_to_wav(reply_text)

        self.current_state = "IDLE"
        total_latency = (time.time() - start_time) * 1000

        return {
            "status": "success",
            "transcription": user_text,
            "reply_text": reply_text,
            "audio_bytes": wav_bytes,
            "task_id": orch_result.get("task_id"),
            "tier": orch_result.get("tier"),
            "latency_ms": round(total_latency, 2)
        }

# Singleton Voice Pipeline
voice_pipeline = FullDuplexVoicePipeline()
