"""
JARVIS Speech-to-Text (STT) Module (PWR-003)
Converts spoken audio buffers (WAV/PCM) into clean text.
Supports faster-whisper when available, with automatic host System.Speech.Recognition fallback.
"""

import os
import time
import io
import wave
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from jarvis.core.logger import logger


class SpeechToText:
    def __init__(self, model_size: str = "base.en"):
        self.model_size = model_size
        self._whisper_model = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            from faster_whisper import WhisperModel

            self._whisper_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info(f"faster-whisper model '{self.model_size}' loaded successfully.")
        except Exception as e:
            logger.info(f"faster-whisper not initialized ({e}); using Windows System.Speech fallback.")
            self._whisper_model = None

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Transcribes raw audio bytes into clean text.
        Returns dict with text, confidence, duration, and latency.
        """
        start_time = time.time()
        if not audio_bytes:
            return {"text": "", "confidence": 0.0, "duration_sec": 0.0, "latency_ms": 0.0, "status": "empty_input"}

        # Calculate audio duration
        duration_sec = 0.0
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration_sec = frames / float(rate)
        except Exception:
            duration_sec = len(audio_bytes) / float(sample_rate * 2)

        # 1. Primary: faster-whisper neural transcription
        if self._whisper_model is not None:
            try:
                audio_io = io.BytesIO(audio_bytes)
                segments, info = self._whisper_model.transcribe(audio_io, beam_size=5, vad_filter=True)
                text = " ".join([seg.text for seg in segments]).strip()
                latency = (time.time() - start_time) * 1000

                if text:
                    return {
                        "text": text,
                        "language": getattr(info, "language", "en"),
                        "confidence": 0.95,
                        "duration_sec": round(duration_sec, 2),
                        "latency_ms": round(latency, 2),
                        "engine": "faster-whisper",
                    }
                else:
                    return {
                        "text": "",
                        "language": getattr(info, "language", "en"),
                        "confidence": 0.0,
                        "duration_sec": round(duration_sec, 2),
                        "latency_ms": round(latency, 2),
                        "engine": "faster-whisper",
                        "status": "no_speech_detected",
                    }
            except Exception as e:
                logger.error(f"faster-whisper transcription error: {e}; falling back to Windows Speech.")

        # 2. Host Fallback: Windows native System.Speech.Recognition
        return self._transcribe_windows_speech(audio_bytes, sample_rate, duration_sec, start_time)

    def _transcribe_windows_speech(
        self, audio_bytes: bytes, sample_rate: int, duration_sec: float, start_time: float
    ) -> Dict[str, Any]:
        """
        Executes genuine transcription using host-native System.Speech.Recognition.
        """
        tmp_path = None
        try:
            # Ensure valid WAV container format
            is_wav = audio_bytes.startswith(b"RIFF")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                if is_wav:
                    tmp.write(audio_bytes)
                else:
                    # Write PCM bytes as valid WAV
                    with wave.open(tmp, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(audio_bytes)

            listener_ps1 = Path(__file__).resolve().parent.parent.parent / "scripts" / "jarvis_speech_listener.ps1"
            if listener_ps1.exists():
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(listener_ps1),
                    "-Mode",
                    "wav",
                    "-WaveFile",
                    tmp_path,
                ]
            else:
                escaped_path = tmp_path.replace("'", "''")
                ps_script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$sr = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
                    f"$sr.SetInputToWaveFile('{escaped_path}'); "
                    "$sr.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
                    "$res = $sr.Recognize(); "
                    "if ($res) { ConvertTo-Json -Compress @{ text = $res.Text; confidence = [math]::Round($res.Confidence, 3) } } "
                    "else { ConvertTo-Json -Compress @{ text = ''; confidence = 0.0 } }"
                )
                cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            latency = (time.time() - start_time) * 1000

            recognized_text = ""
            confidence = 0.0

            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    data = json.loads(line)
                    ev = data.get("event") or data.get("type")
                    if ev in ("SPEECH", "WAKE") or "text" in data:
                        text_val = data.get("text") or data.get("phrase") or data.get("full_text") or ""
                        if text_val:
                            recognized_text = text_val
                            confidence = float(data.get("confidence", 0.8))
                except Exception:
                    continue

            return {
                "text": recognized_text,
                "language": "en",
                "confidence": confidence,
                "duration_sec": round(duration_sec, 2),
                "latency_ms": round(latency, 2),
                "engine": "windows_system_speech",
                "status": "success" if recognized_text else "no_speech_detected",
            }
        except Exception as e:
            logger.error(f"Windows speech recognition fallback failed: {e}")
            latency = (time.time() - start_time) * 1000
            return {
                "text": "",
                "language": "en",
                "confidence": 0.0,
                "duration_sec": round(duration_sec, 2),
                "latency_ms": round(latency, 2),
                "engine": "windows_system_speech",
                "status": "error",
                "error": str(e),
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


# Singleton Speech to Text
stt_engine = SpeechToText()
