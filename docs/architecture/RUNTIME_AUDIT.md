# JARVIS Live Runtime Environment Audit

**Generated:** 2026-11-03  
**Audit Branch:** `audit/capability-audit`  
**Host Machine:** Windows 11 Home (x64)  

---

## 1. Executive Runtime Scorecard

| Component | Test Executed | Command Output / Observation | Status |
| :--- | :--- | :--- | :--- |
| **Ollama Daemon** | `ollama list` | `CommandNotFoundException`: The term 'ollama' is not recognized. | **OFFLINE / NOT INSTALLED** |
| **Local Models** | `ollama list` | None (Ollama CLI missing; zero local models registered). | **NONE FOUND** |
| **GPU Acceleration** | `nvidia-smi` | NVIDIA GeForce RTX 4050 Laptop GPU (6141 MiB VRAM, Driver 591.66, CUDA 13.1). | **AVAILABLE (3.8 GB Free VRAM)** |
| **Host Storage** | `Get-PSDrive C` | Used: ~292.0 GB (313,546,051,584 bytes), Free: ~2.84 GB (3,047,215,104 bytes). | **CRITICAL STORAGE WARNING** |
| **Python Environment**| Python 3.12.10 | System Python: `C:\Users\Ganesh Nair\AppData\Local\Programs\Python\Python312\python.exe` | **READY** |
| **FastAPI Entrypoint**| `import jarvis.api.server` | Loaded title: `"JARVIS Personal AI Operating System"`. | **ONLINE / VERIFIED** |
| **Automated Tests** | `pytest tests/ -q --tb=no` | **557 passed, 8 failed, 3 warnings** (Total: 565 test cases, runtime: 731.19s). | **98.6% PASS RATE** |
| **Voice: Wake Word** | `jarvis/voice/wake.py` | RMS energy threshold calculation; no background listener thread. | **SIMULATED / MOCK** |
| **Voice: STT** | `jarvis/voice/stt.py` | Returns hardcoded sample strings when `faster-whisper` is uninstalled. | **MOCK FALLBACK** |
| **Voice: TTS** | `jarvis/voice/tts.py` | Windows SAPI (`win32com.client.Dispatch("SAPI.SpVoice")`) initialized. | **ACTIVE (SAPI COM)** |

---

## 2. Detailed Runtime Diagnostics

### A. Ollama & Local Model Inference
- **CLI Check:** `ollama list`
- **Result:**
  ```text
  ollama : The term 'ollama' is not recognized as the name of a cmdlet, function, script file, or operable program.
  ```
- **Analysis:** Ollama is not installed in the Windows `PATH`. All tests or routes attempting to connect to `http://localhost:11434/api/generate` will fail or fall back to LiteLLM / Cloud mock endpoints.
- **Pytest Impact:** 3 unit tests failed directly due to absent local Ollama:
  - `tests/test_benchmark_powers.py::test_ollama_offline_10_consecutive_turns_latency`
  - `tests/test_benchmark_powers.py::test_ollama_offline_adversarial_prompts`
  - `tests/test_litellm_local.py::test_litellm_local_inference_fallback`

---

### B. Host Hardware: GPU and Disk Space

#### GPU Status (`nvidia-smi`):
```text
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 591.66                 Driver Version: 591.66         CUDA Version: 13.1     |
|-----------------------------------+------------------------+----------------------------+
| GPU  Name              Driver-Model| Bus-Id          Disp.A | Volatile Uncorr. ECC       |
| Fan  Temp   Perf          Pwr:Usage/Cap | Memory-Usage       | GPU-Util  Compute M.       |
|===================================+========================+============================|
|   0  NVIDIA GeForce RTX ... WDDM  | 00000000:01:00.0    On |                        N/A |
| N/A   48C    P8              8W / 50W |   2253MiB /  6141MiB |      1%      Default      |
+-----------------------------------------------------------------------------------------+
```
- **VRAM Total:** 6,141 MiB (~6 GB)
- **VRAM Used:** 2,253 MiB (Display & OS subsystems)
- **VRAM Available:** ~3,888 MiB (~3.8 GB)
- **Capability:** Capable of running quantized 4-bit / 8-bit SLMs (e.g. Qwen 2.5 3B or Phi-3.5 3.8B) or Kokoro TTS once disk space is restored.

#### Disk Status (`Get-PSDrive C`):
```text
Used (GB): 292.01 GB
Free (GB): 2.84 GB
Total (GB): 294.85 GB
Free Percentage: 0.96%
```
- **CRITICAL ALERT:** Available disk space is **2.84 GB**. 
- Attempting to install Ollama model weights (e.g., `llama3:8b` ~4.7 GB, `deepseek-r1:8b` ~4.9 GB) will result in immediate disk exhaustion and OS instability.

---

### C. Voice Interaction Pipeline (`jarvis/voice/`)

1. **Wake-Word Detection (`jarvis/voice/wake.py`):**
   - **Code Analysis:** `WakeWordDetector` defines `detect_wake_word(audio_chunk: bytes) -> bool`.
   - **Implementation Reality:** Computes root-mean-square (RMS) energy across audio chunks:
     ```python
     rms = math.sqrt(sum(sample**2 for sample in samples) / len(samples))
     return rms > self.energy_threshold
     ```
   - **Finding:** It does not run a neural wake-word engine (like openWakeWord or Porcupine). Any sound exceeding the threshold is treated as a wake-word. No continuous background audio stream is automatically opened.

2. **Speech-to-Text (`jarvis/voice/stt.py`):**
   - **Code Analysis:** `SpeechToText.transcribe(audio_bytes)` attempts to load `faster-whisper`.
   - **Implementation Reality:** If `faster_whisper` is uninstalled or fails, it falls back to:
     ```python
     if not self.whisper_model:
         return "Jarvis, report system health" if duration_sec > 0.5 else "Jarvis"
     ```
   - **Finding:** Without the binary `faster-whisper` package and model weights, STT returns a hardcoded mock transcription.

3. **Text-to-Speech (`jarvis/voice/tts.py`):**
   - **Code Analysis:** Initializes Windows native COM speaker:
     ```python
     self._sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
     ```
   - **Implementation Reality:** Real Windows SAPI audio synthesis works and outputs audio through the OS sound driver. If SAPI is unavailable, it outputs synthetic sine-wave PCM audio into a WAV buffer.
   - **Kokoro-82M TTS:** **NOT PRESENT** in `jarvis/voice/tts.py`.

---

### D. FastAPI Entrypoints & Startup Verification

1. **Primary Entrypoints Identified:**
   - `jarvis/api/server.py`: Primary production ASGI server (`app = FastAPI(title=APP_TITLE, ...)`).
   - `app/main.py`: Top-level wrapper mounting `jarvis.api.server:app`.
   - `jarvis/main.py`: Interactive CLI / daemon runner.

2. **Startup Verification Test:**
   ```powershell
   & "C:\Users\Ganesh Nair\AppData\Local\Programs\Python\Python312\python.exe" -c "from jarvis.api.server import app; print(app.title)"
   ```
   - **Result:** `JARVIS Personal AI Operating System`
   - **Exit Code:** `0` (Clean startup without missing import exceptions).

---

### E. Pytest Suite Execution

- **Command:**
  ```powershell
  & "C:\Users\Ganesh Nair\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/ -q --tb=no
  ```
- **Results:**
  ```text
  8 failed, 557 passed, 3 warnings in 731.19s (0:12:11)
  ```
- **Pass Rate:** **98.6%** (557 / 565)
- **Detailed Failure Analysis (8 failures):**
  1. `tests/test_instant_powers.py::test_instant_powers_guardrails` (TypeError: argument unpacking mismatch).
  2. `tests/test_power_registry.py::test_representative_power_execution[PWR-327]` (Validation assertion mismatch).
  3. `tests/test_benchmark_powers.py::test_ollama_offline_10_consecutive_turns_latency` (Ollama daemon offline).
  4. `tests/test_benchmark_powers.py::test_ollama_offline_adversarial_prompts` (Ollama daemon offline).
  5. `tests/test_finance_powers.py::test_finance_powers` (AssertionError: mock portfolio price return).
  6. `tests/test_smart_home_powers.py::test_smart_home_powers` (TypeError: parameter schema mismatch).
  7. `tests/test_automation_powers.py::test_automation_powers` (AssertionError: output status mismatch).
  8. `tests/test_litellm_local.py::test_litellm_local_inference_fallback` (Ollama daemon offline).
