# JARVIS Voice Subsystem Audit

**Date:** 2026-11-03  
**Auditor:** Antigravity Autonomous Systems Engineer  
**Branch:** `sprint1/trust-and-reliability`  
**Root:** `jarvis/voice/` and `jarvis/api/routes_voice.py`  

---

## 1. Subsystem Component Classification

| Module | Classification | Implementation Status | Evidence & Details |
|---|---|---|---|
| **`jarvis/voice/tts.py`** | **REAL** | Active & Operational | Uses native Windows SAPI COM (`win32com.client.Dispatch("SAPI.SpVoice")`) with `SpFileStream` for real WAV byte generation. Also supports ElevenLabs REST API when `ELEVENLABS_API_KEY` is present. Pure Python PCM sine/envelope generator exists as safe fallback. |
| **`jarvis/voice/stt.py`** | **STUB / CONDITIONAL** | Partial Fallback | Checks for `faster_whisper.WhisperModel`. If installed, performs real int8 CPU transcription. On host, `faster-whisper` is **NOT installed**; falls back to `_mock_transcribe()` or energy-based string heuristics. |
| **`jarvis/voice/wake.py`** | **STUB / MOCK** | Simulation Only | Does not run a real acoustic model (like `openWakeWord` or `porcupine`). Push-to-talk (`trigger_push_to_talk`) works deterministically, but continuous microphone acoustic keyword scanning is simulated via random/energy loop. |
| **`jarvis/voice/pipeline.py`** | **PARTIAL** | State Machine Real; Audio Loop Mock | Real state transitions (`IDLE` → `LISTENING` → `PROCESSING` → `SPEAKING`) and real barge-in cancellation calling `tts_engine.interrupt()`. However, audio ingestion relies on stubs from `wake.py` and `stt.py`. |
| **`jarvis/api/routes_voice.py`** | **REAL** | Mounted & Callable | Endpoints `/api/v1/voice/transcribe`, `/api/v1/voice/synthesize`, `/api/v1/voice/push-to-talk`, and `/api/v1/voice/barge-in` are fully registered on the FastAPI app. |

---

## 2. Live Verification Test

- **TTS SAPI Execution Test:**  
  Tested via `tts_engine.synthesize_to_wav("JARVIS online")`:  
  Generated genuine 44.1kHz 16-bit PCM RIFF WAV header and audio byte buffer (HTTP 200 via `/api/v1/voice/synthesize`).
- **Wake Word Limitation:**  
  "Hey Jarvis" cannot trigger from background ambient audio without installing a lightweight local keyword engine like `openWakeWord`.

---

## 3. Path to 100% Real Local Voice (Post-Sprint 1)

1. **Acoustic Wake Word:** Install `openwakeword` with pre-trained `hey_jarvis_v0.1.onnx` (~4 MB model, runs in <5ms on CPU).
2. **STT:** Install `faster-whisper` with `base.en` or `tiny.en` (~75 MB model, ~150ms transcription latency on RTX 4050 or laptop CPU).
3. **Neural TTS:** Integrate local Kokoro-82M or retain Windows SAPI (0ms network latency, zero cloud dependency).
