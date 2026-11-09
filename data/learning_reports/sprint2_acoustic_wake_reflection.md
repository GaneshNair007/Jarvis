# Sprint 2/3 Reflection — Acoustic Wake Gate + Always-On Boot

**Date:** 2026-11-09
**Branch:** `feature/sprint2-acoustic-wake-and-always-on` (from `preview/jarvis-assembled`)
**Fourth Law record:** written before the completion claim (constitution v1.2.0).

## What I built
1. **`AcousticWakeGate`** (`jarvis/voice/wake.py`): openWakeWord ONNX wake scoring
   ("hey_jarvis_v0.1"), 1280-sample (80 ms @ 16 kHz) frames, threshold 0.5,
   fail-closed to the legacy transcription path, explicit model-load error
   reasons, lazy process-wide singleton (`get_acoustic_gate`) so importing the
   module never loads the model.
2. **Daemon wiring** (`jarvis/voice/daemon.py`): gate runs on EVERY block while
   LISTENING_FOR_WAKE (speech *and* silence — required by measured model
   behavior), acoustic-only wake acceptance with evidence receipts, wake +
   cooldown suppression, transcription fallback for ambient utterances only
   when the gate is not actively scoring, honest health fields
   (`acoustic_gate_enabled/installed/armed/engine/model/threshold/unavailable_reason`,
   `acoustic_wake_count`, `gated_utterance_count`, `last_acoustic_score`),
   env lever `JARVIS_ACOUSTIC_GATE=off` and constructor injection for tests.
3. **PWR-001 honesty**: `wake_word_status()` now reports the acoustic layer
   (installed/armed/models/threshold) separately from "a listener process is
   running" — active is never faked.
4. **Mic subsystem truth** (`probe_input_devices` + `select_input_device` +
   start()): probe measures with the daemon's own InputStream mechanics;
   non-delivering devices are classified `error` (measured: Realtek devices
   12/20 pass `sd.rec` one-shots but never call callbacks); loopbacks
   ("Stereo Mix", "PC Speaker") excluded; intent-preference for "Microphone
   Array"; native-rate capture with callback resampling to 16 kHz (16 kHz
   direct capture on MME stalled/delayed on this host).
5. **Always-on boot (Sprint 3 P0)**: `scripts/install_jarvis_startup.ps1` run;
   `JARVIS Background.vbs` verified present in the user's Startup folder
   (launches API server on 127.0.0.1:8000 + voice daemon via
   `pythonw -m jarvis.voice.daemon` at next sign-in).
6. **`scripts/live_wake_session.py`**: 120 s always-on evidence session with
   JSON receipts (`data/logs/acoustic_wake_session.json`).

## What failed along the way (and how I know)
- `Model(wakeword_models=None)` → `'NoneType' has no len()` on this
  openWakeWord build → load packaged ONNX explicitly.
- Models live in `openwakeword/resources/models/` in this version, not
  `<pkg>/models/` → probe both layouts, download "hey jarvis" if missing.
- Feeding the gate only VAD-speech blocks starved it: the wake verdict
  persists on TRAILING frames after the phrase (measured 0.938→0.9986 on
  silence). Now: every listening block is scored.
- Post-wake leftover model state instantly re-triggered → `_sleep_gate()`
  (cooldown + `Model.reset()`) on every return to LISTENING_FOR_WAKE.
- A cooldown window accidentally silenced even the transcription fallback
  (deleting the mental model: cooldown only mutes the acoustic gate).
- `sd.rec`-based probe said "live"/"quiet" for devices that the daemon's
  own stream never delivers callbacks on → probe now uses callback
  mechanics and reports what the pipeline actually gets.
- The machine's speakers produce no audible SAPI output during today's
  attempts (array hears 0.2 noise-floor while "speaking"); loopback
  measurement unavailable (Stereo Mix delivers no callbacks). The
  synthetic self-echo path is therefore not today's proof — a human wake
  phrase through the live session is the acceptance gate.

## Evidence ledger for this sprint
- Real-model scores on SAPI "Hey Jarvis" (injected frames): max 0.9985; on
  "the weather is quite pleasant today": 0.0000; on silence/hum floors ≈ 0.
- Live mic session (device 1, old 16 kHz direct path, during spoken phrase):
  gate max 0.9034 — the array + model chain works through real air.
- **Human wake receipt (2026-11-09, cued session, device 1 @ 44.1 kHz native
  capture, callback-resampled to 16 kHz exactly like the daemon path):**
  human said the wake phrase; gate scored 0.7157 live (2 wake events) and
  the saved capture re-scored OFFLINE (resample → sequential feeding)
  reproduces it: wake events at frames 77/78 (t≈7.7–7.8 s), scores
  0.7134 / 0.6724, with the climb 0.0634 → 0.2799 → 0.7134 → 0.6724 →
  0.4485 showing the threshold-crossing accumulation. (The 2 back-to-back
  events are an artifact of the bare test rig, which feeds the whole capture
  without the daemon's post-wake `_sleep_gate` cooldown; in the daemon one
  wake is accepted and the model state resets before listening again.)
- Calibration honesty: non-wake human speech in the same captures
  ("Can you hear me?", "Are you ready...") scored 0.0005–0.037 — near
  zero, exactly as the model treats non-wake speech; Whisper transcribed
  those captures at conf 0.95, proving the capture content is intelligible.
- Always-on sessions (180 s + 120 s, real orchestrator wired): mic live on
  Microphone Array, 10 energy-detected utterances carried, gate correctly
  reported no wake (no phrase spoken in those windows).
- Machine speakers inaudible to the array (Stereo Mix loopback delivers no
  callbacks) → synthetic self-echo is NOT a proof path on this host; human
  voice is the acceptance instrument.
- Full suite on the final tree: see commit-time run result.
- Startup folder receipt: `JARVIS Background.vbs` present.
- Daemon `_run_gate` instrumentation repro: full wake sequence on real
  SAPI audio (0.9321→0.9986 → wake → whisper → CAPTURING_COMMAND).

## Playbook for next time
- Measure with the mechanism you ship (callback probe vs `sd.rec` differed).
- Never gate audio by VAD *before* a stateful model — feed the whole stream
  while waiting for the wake decision.
- Reset stateful models after accepting their verdicts (activation lingers).
- A suppression window must not disable the fallback listener it protects.
- Log launch times of every stage in a live run (model loads were hidden
  cost: ~10 s of "dead" listening before first frame). Add a pre-warm call
  to `get_acoustic_gate()` in `VoiceDaemon.start()` next sprint.
- SAPI synthetic audio scores ~0.99 on the packaged model; a human voice
  scores ~0.7: threshold 0.5 works for both, but re-check headroom when
  adding new wake phrases or voices ( Whisper on this host's captures is
  conf≈0.95 but phrase wording can garble — acoustic gate is the reliable
  wake instrument, transcription the command extractor).
- Cues and feedback loops matter: echo the Whisper transcript of what was
  heard in every cued test, or the tester never knows which words arrived.
