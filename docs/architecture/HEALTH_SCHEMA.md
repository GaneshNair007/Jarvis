# JARVIS System Health Schema & Evidence Specification

This document defines the authoritative response schema for `GET /api/v1/system/health`.
In alignment with the **First Law of JARVIS**, the health endpoint never returns ungrounded boolean values (`{"ollama": true}`). Instead, every subsystem reports its connectivity status accompanied by forensic evidence.

---

## 1. Specification (JSON Schema Equivalent)

```json
{
  "status": "healthy" | "degraded" | "critical",
  "timestamp": 1730616000.0,
  "first_law_enforced": true,
  "fabricated": false,
  "ollama": {
    "status": "online" | "offline",
    "evidence": [
      "TCP connection established to 127.0.0.1:11434"
    ]
  },
  "scheduler": {
    "status": "running" | "stopped",
    "last_heartbeat": "2026-11-03T12:40:00.123456",
    "heartbeat_count": 42,
    "total_jobs": 3
  },
  "voice": {
    "status": "stub",
    "components": {
      "tts": "real",
      "stt": "stub",
      "wake_word": "stub",
      "audio_output": "real",
      "barge_in": "stub"
    },
    "evidence": [
      "Windows SAPI pyttsx3 initialized",
      "Wake word model missing on disk (classified as STUB)",
      "STT recognizer uncalibrated (classified as STUB)"
    ]
  },
  "gmail": {
    "status": "connected" | "disconnected" | "degraded",
    "evidence": [
      "no credentials (GMAIL_APP_PASSWORD/OAUTH) configured in environment"
    ]
  },
  "internet": {
    "status": "connected" | "disconnected",
    "evidence": [
      "socket probe to 8.8.8.8:53 succeeded"
    ]
  },
  "nvidia": {
    "status": "connected" | "disconnected",
    "evidence": [
      "NVIDIA_API_KEY present in environment"
    ]
  },
  "cognitum": {
    "status": "connected" | "disconnected",
    "evidence": [
      "COGNITUM_API_KEY missing"
    ]
  },
  "cpu": {
    "percent": 14.2
  },
  "memory": {
    "percent": 68.5,
    "available_gb": 5.12
  },
  "disk": {
    "percent": 96.8,
    "free_gb": 2.84
  },
  "boot_time": "2026-11-03 08:15:00",
  "host_status": "healthy"
}
```

---

## 2. Field Definitions & Evidence Requirements

### 2.1 `ollama`
- **`status`**: `"online"` only if a TCP connection to `127.0.0.1:11434` can be opened and closed within 1000ms. Otherwise `"offline"`.
- **`evidence`**: Contains the exact socket diagnosis (`"TCP connection established..."` or `"connection refused or timeout at localhost:11434"`).

### 2.2 `scheduler`
- **`status`**: `"running"` if `ProactiveAutonomousScheduler` background loop is active; `"stopped"` if halted.
- **`last_heartbeat`**: ISO 8601 string of the most recent loop tick or manual heartbeat trigger.
- **`heartbeat_count`**: Monotonically increasing integer incremented every polling interval. Proves the scheduler is not frozen.
- **`total_jobs`**: Count of registered automated routines (e.g. 08:00 Career Scout, 12:00 Hackathon Scout, 18:00 AI Digest).

### 2.3 `voice`
- **`status`**: Overall status. Hardcoded as `"stub"` based on findings in `docs/architecture/VOICE_AUDIT.md`.
- **`components`**:
  - `tts`: `"real"` (Windows SAPI5 / pyttsx3 executes speech locally).
  - `stt`: `"stub"` (Microphone stream placeholder without continuous listening loop).
  - `wake_word`: `"stub"` (No Porcupine / OpenWakeWord ONNX model configured on disk).
  - `audio_output`: `"real"` (OS audio device output functional).
  - `barge_in`: `"stub"` (Acoustic echo cancellation placeholder).
- **`evidence`**: Audit rationale and hardware test verification statements.

### 2.4 `gmail`
- **`status`**:
  - `"connected"`: Both credentials exist AND `imap.gmail.com:993` is reachable.
  - `"degraded"`: Credentials exist, but `imap.gmail.com:993` timed out (offline/firewalled).
  - `"disconnected"`: Neither `GMAIL_APP_PASSWORD` nor OAuth tokens are found in `.env` / filesystem.
- **`evidence`**: Diagnostic detail of the credential check and socket reachability.

### 2.5 `internet`
- **`status`**: `"connected"` if UDP/TCP probe to `8.8.8.8:53` succeeds within 2000ms; `"disconnected"` otherwise.
- **`evidence`**: Connection confirmation or OS socket errno.

### 2.6 `host` (CPU, Memory, Disk)
- Backward-compatible telemetry extracted from `psutil` via `ITAdminPowers.system_health_report()`.
- Guarantees compatibility with existing tests and HUD WebSocket stream (`/ws/stream`).

---

## 3. Real-World Payload Example (Current Live Host State)

```json
{
  "status": "healthy",
  "timestamp": 1730616120.45,
  "first_law_enforced": true,
  "fabricated": false,
  "ollama": {
    "status": "offline",
    "evidence": [
      "connection refused or timeout at localhost:11434"
    ]
  },
  "scheduler": {
    "status": "running",
    "last_heartbeat": "2026-11-03T12:43:00.123456",
    "heartbeat_count": 14,
    "total_jobs": 3
  },
  "voice": {
    "status": "stub",
    "components": {
      "tts": "real",
      "stt": "stub",
      "wake_word": "stub",
      "audio_output": "real",
      "barge_in": "stub"
    },
    "evidence": [
      "Windows SAPI pyttsx3 initialized",
      "Wake word model missing on disk (classified as STUB)",
      "STT recognizer uncalibrated (classified as STUB)"
    ]
  },
  "gmail": {
    "status": "disconnected",
    "evidence": [
      "no credentials (GMAIL_APP_PASSWORD/OAUTH) configured in environment"
    ]
  },
  "internet": {
    "status": "connected",
    "evidence": [
      "socket probe to 8.8.8.8:53 succeeded"
    ]
  },
  "nvidia": {
    "status": "disconnected",
    "evidence": [
      "NVIDIA_API_KEY missing"
    ]
  },
  "cognitum": {
    "status": "disconnected",
    "evidence": [
      "COGNITUM_API_KEY missing"
    ]
  },
  "cpu": {
    "percent": 8.4
  },
  "memory": {
    "percent": 62.1
  },
  "disk": {
    "percent": 97.4
  },
  "boot_time": "2026-11-03 08:15:00",
  "host_status": "healthy"
}
```
