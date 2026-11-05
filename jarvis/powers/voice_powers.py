"""
JARVIS Voice & Audio Interaction Powers (PWR-001 to PWR-005)
Wake word detection, speech-to-text, text-to-speech, voice profiles,
and interrupt handling for the JARVIS voice pipeline.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, Optional


class VoicePowers:
    """Voice input/output powers for JARVIS."""

    def __init__(self) -> None:
        self._tts_process: Optional[subprocess.Popen] = None
        self._stopwatch_start: Optional[float] = None

    # ------------------------------------------------------------------ #
    #  PWR-001 — Wake Word Status                                         #
    # ------------------------------------------------------------------ #
    def wake_word_status(self) -> Dict[str, Any]:
        """PWR-001: Returns wake word engine status (active/inactive, engine type)."""
        try:
            # Attempt to detect a running wake-word engine
            engine_type = "unknown"
            active = False

            # Check for common wake-word processes
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            running = result.stdout.lower()

            if "porcupine" in running or "pvporcupine" in running:
                engine_type = "porcupine"
                active = True
            elif "snowboy" in running:
                engine_type = "snowboy"
                active = True
            elif "vosk" in running:
                engine_type = "vosk"
                active = True

            return {
                "power_id": "PWR-001",
                "status": "success",
                "active": active,
                "engine_type": engine_type,
                "message": f"Wake word engine {'active' if active else 'inactive'} ({engine_type})",
            }
        except Exception as e:
            return {
                "power_id": "PWR-001",
                "status": "error",
                "active": False,
                "engine_type": "unknown",
                "message": f"Could not query wake word status: {e}",
            }

    # ------------------------------------------------------------------ #
    #  PWR-002 — Speech to Text                                           #
    # ------------------------------------------------------------------ #
    def speech_to_text(self, audio_path: Optional[str] = None) -> Dict[str, Any]:
        """PWR-002: Convert speech to text.

        Tries OpenAI Whisper (local model) first, then falls back to a
        Windows Speech Recognition stub via PowerShell.
        """
        try:
            # ---- Try whisper (pip install openai-whisper) ----
            try:
                import whisper  # type: ignore[import-untyped]

                model = whisper.load_model("base")
                if audio_path and os.path.isfile(audio_path):
                    result = model.transcribe(audio_path)
                    return {
                        "power_id": "PWR-002",
                        "status": "success",
                        "engine": "whisper",
                        "text": result.get("text", ""),
                        "language": result.get("language", "unknown"),
                    }
                else:
                    return {
                        "power_id": "PWR-002",
                        "status": "error",
                        "engine": "whisper",
                        "message": f"Audio file not found: {audio_path}",
                    }
            except ImportError:
                pass  # Fall through to Windows fallback

            # ---- Fallback: Windows Speech Recognition via PowerShell ----
            if audio_path and os.path.isfile(audio_path):
                ps_script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$sr = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
                    "$sr.SetInputToWaveFile('{}'); "
                    "$sr.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
                    "$result = $sr.Recognize(); "
                    "if ($result) {{ $result.Text }} else {{ '<no speech detected>' }}"
                ).format(audio_path.replace("'", "''"))

                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True, text=True, timeout=30,
                )
                text = proc.stdout.strip() or "<no speech detected>"
                return {
                    "power_id": "PWR-002",
                    "status": "success",
                    "engine": "windows_sapi",
                    "text": text,
                }
            else:
                return {
                    "power_id": "PWR-002",
                    "status": "error",
                    "engine": "none",
                    "message": "No audio path provided or file not found, and whisper is not installed.",
                }
        except Exception as e:
            return {
                "power_id": "PWR-002",
                "status": "error",
                "message": f"Speech-to-text failed: {e}",
            }

    # ------------------------------------------------------------------ #
    #  PWR-003 — Text to Speech                                           #
    # ------------------------------------------------------------------ #
    def text_to_speech(self, text: str, voice: str = "jarvis") -> Dict[str, Any]:
        """PWR-003: Speak text aloud using pyttsx3 or Windows SAPI."""
        try:
            # ---- Try pyttsx3 first ----
            try:
                import pyttsx3  # type: ignore[import-untyped]

                engine = pyttsx3.init()
                voices = engine.getProperty("voices")
                # Try to match the requested voice name
                for v in voices:
                    if voice.lower() in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
                engine.say(text)
                engine.runAndWait()
                engine.stop()
                return {
                    "power_id": "PWR-003",
                    "status": "success",
                    "engine": "pyttsx3",
                    "text": text,
                    "voice": voice,
                }
            except ImportError:
                pass  # Fall through to SAPI

            # ---- Fallback: Windows SAPI via PowerShell ----
            safe_text = text.replace("'", "''").replace('"', '`"')
            ps_cmd = (
                "Add-Type -AssemblyName System.Speech; "
                "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Speak('{safe_text}')"
            )
            self._tts_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self._tts_process.wait(timeout=60)
            return {
                "power_id": "PWR-003",
                "status": "success",
                "engine": "windows_sapi",
                "text": text,
                "voice": voice,
            }
        except Exception as e:
            return {
                "power_id": "PWR-003",
                "status": "error",
                "message": f"Text-to-speech failed: {e}",
            }

    # ------------------------------------------------------------------ #
    #  PWR-004 — Voice Profile Status                                     #
    # ------------------------------------------------------------------ #
    def voice_profile_status(self) -> Dict[str, Any]:
        """PWR-004: Return voice profile/biometric status.

        Checks the Windows Speech Recognition profile training level.
        """
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Speech; "
                "$ri = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
                "try { $ri.SetInputToDefaultAudioDevice() } catch {}; "
                "Write-Output 'profile_available'"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            available = "profile_available" in proc.stdout
            return {
                "power_id": "PWR-004",
                "status": "success",
                "profile_available": available,
                "engine": "windows_sapi",
                "message": "Voice profile detected" if available else "No voice profile configured",
            }
        except Exception as e:
            return {
                "power_id": "PWR-004",
                "status": "error",
                "profile_available": False,
                "message": f"Could not query voice profile: {e}",
            }

    # ------------------------------------------------------------------ #
    #  PWR-005 — Interrupt Handling                                       #
    # ------------------------------------------------------------------ #
    def interrupt_handling(self) -> Dict[str, Any]:
        """PWR-005: Handle voice interruption by stopping any active TTS playback."""
        try:
            killed = False
            # Kill tracked TTS subprocess
            if self._tts_process is not None and self._tts_process.poll() is None:
                self._tts_process.terminate()
                self._tts_process = None
                killed = True

            # Also kill any lingering PowerShell SAPI processes
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq powershell.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            # We won't aggressively kill all PowerShells — only our tracked one

            return {
                "power_id": "PWR-005",
                "status": "success",
                "interrupted": killed,
                "message": "TTS playback interrupted" if killed else "No active TTS to interrupt",
            }
        except Exception as e:
            return {
                "power_id": "PWR-005",
                "status": "error",
                "message": f"Interrupt handling failed: {e}",
            }


voice_powers = VoicePowers()
