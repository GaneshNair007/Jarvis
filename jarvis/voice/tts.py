"""
JARVIS Text-to-Speech (TTS) Module (PWR-004)
Synthesizes natural spoken speech with low latency and barge-in cancellation.
Supports ElevenLabs Neural Voice API, Windows SAPI natively (with SpFileStream for real WAV output),
and pure Python PCM audio fallback.
"""

import os
import io
import json
import time
import tempfile
import urllib.request
import urllib.error
import wave
import struct
import math
from typing import Optional, Dict, Any
from jarvis.config import settings
from jarvis.core.logger import logger


class TextToSpeech:
    def __init__(self, voice_speed: Optional[int] = None, volume: Optional[int] = None):
        self.voice_speed = voice_speed if voice_speed is not None else settings.tts_speed
        self.volume = volume if volume is not None else settings.tts_volume
        self.elevenlabs_api_key = os.getenv(
            "ELEVENLABS_API_KEY", getattr(settings, "elevenlabs_api_key", None)
        )
        self.elevenlabs_voice_id = os.getenv(
            "ELEVENLABS_VOICE_ID", getattr(settings, "elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
        )
        self.is_speaking = False
        self._interrupted = False
        self._sapi_speaker = None
        self._init_sapi()

    def _init_sapi(self) -> None:
        try:
            import win32com.client

            self._sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
            self._sapi_speaker.Rate = self.voice_speed
            self._sapi_speaker.Volume = self.volume
            logger.info("Windows native SAPI SpeechSynthesizer initialized.")
        except Exception as e:
            logger.info(f"SAPI not loaded: {e}; using fallback PCM WAV generator.")
            self._sapi_speaker = None

    def synthesize_elevenlabs(self, text: str) -> Optional[bytes]:
        """Synthesizes high-fidelity speech using ElevenLabs API when configured."""
        if not self.elevenlabs_api_key or not text:
            return None

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    logger.info("ElevenLabs speech synthesis succeeded.")
                    return resp.read()
        except Exception as e:
            logger.warning(f"ElevenLabs TTS call failed or timed out: {e}; falling back to SAPI/PCM.")
            return None

    def cancel_speech(self) -> None:
        """Interrupts ongoing speech immediately upon user barge-in."""
        self._interrupted = True
        self.is_speaking = False
        if self._sapi_speaker:
            try:
                # 2 = SVSFPurgeBeforeSpeak
                self._sapi_speaker.Speak("", 2)
            except Exception:
                pass
        logger.info("Speech playback cancelled (barge-in event).")

    def speak_live(self, text: str, async_mode: bool = True) -> bool:
        """Speaks text directly through host speakers."""
        if not text:
            return False

        self._interrupted = False
        self.is_speaking = True

        if self._sapi_speaker:
            try:
                # 1 = SVSFlagsAsync
                flags = 1 if async_mode else 0
                self._sapi_speaker.Speak(text, flags)
                return True
            except Exception as e:
                logger.error(f"SAPI live speak error: {e}")

        self.is_speaking = False
        return False

    def synthesize_to_wav(self, text: str) -> bytes:
        """
        Synthesizes text into audio bytes.
        Order of precedence:
        1. ElevenLabs Neural TTS (if ELEVENLABS_API_KEY is configured)
        2. Windows native SAPI to WAV
        3. Pure Python standard library PCM WAV generator
        """
        if not text:
            return b""

        # 1. Attempt ElevenLabs synthesis
        if self.elevenlabs_api_key:
            audio = self.synthesize_elevenlabs(text)
            if audio:
                return audio

        # 2. Attempt SAPI synthesis to SpFileStream
        if self._sapi_speaker:
            try:
                import win32com.client

                stream = win32com.client.Dispatch("SAPI.SpFileStream")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                stream.Open(tmp_path, 3)  # 3 = SSFMCreateForWrite
                self._sapi_speaker.AudioOutputStream = stream
                self._sapi_speaker.Speak(text, 0)
                stream.Close()

                # Read bytes and remove temp file
                with open(tmp_path, "rb") as f:
                    wav_data = f.read()
                os.remove(tmp_path)
                return wav_data
            except Exception as e:
                logger.warning(f"SAPI file synthesis failed: {e}; using fallback PCM generator.")

        # 3. Fallback: Pure Python standard library PCM WAV generator (chime/beep/audio)
        sample_rate = 16000
        duration = min(3.0, 0.3 + (len(text) * 0.04))
        num_samples = int(sample_rate * duration)
        buf = io.BytesIO()

        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)

            # Generate pleasant soft audio tone sequence
            freq = 440.0  # A4
            data = bytearray()
            for i in range(num_samples):
                t = float(i) / sample_rate
                value = int(12000.0 * math.sin(2.0 * math.pi * freq * t) * math.exp(-t * 2.0))
                data += struct.pack("<h", value)

            wf.writeframes(data)

        return buf.getvalue()


# Singleton Text to Speech
tts_engine = TextToSpeech()
