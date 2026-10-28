"""
Automated verification tests for Phase 1 Voice Subsystems.
Tests Wake Word (PWR-001/002), STT (PWR-003), TTS (PWR-004), and Full-Duplex Barge-in (PWR-005).
"""

import pytest
import asyncio
from jarvis.voice.wake import wake_detector
from jarvis.voice.stt import stt_engine
from jarvis.voice.tts import tts_engine
from jarvis.voice.pipeline import voice_pipeline

def test_wake_word_phrase_detection():
    """PWR-001: Wake phrase detection triggers activation."""
    assert wake_detector.detect_phrase_in_text("Hey Jarvis, what is the time?")
    assert wake_detector.detect_phrase_in_text("jarvis lock screen")
    assert not wake_detector.detect_phrase_in_text("hello computer")

def test_push_to_talk_activation():
    """PWR-002: Push-to-talk immediate activation."""
    received_events = []
    wake_detector.register_callback(lambda ev: received_events.append(ev))

    event = wake_detector.trigger_push_to_talk("test_hotkey")
    assert event["trigger"] == "push_to_talk"
    assert len(received_events) > 0
    assert received_events[-1]["source"] == "test_hotkey"

def test_tts_synthesis_to_wav():
    """PWR-004: Text-to-speech synthesizes valid WAV audio bytes."""
    wav_bytes = tts_engine.synthesize_to_wav("Jarvis voice verification test.")
    assert len(wav_bytes) > 44 # Must have at least a WAV header (44 bytes)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

def test_barge_in_cancellation():
    """PWR-005: Barge-in cancels active speech playback."""
    tts_engine.is_speaking = True
    assert tts_engine.is_speaking

    voice_pipeline.handle_barge_in()
    assert not tts_engine.is_speaking
    assert voice_pipeline.current_state == "LISTENING"

def test_stt_transcription_pipeline():
    """PWR-003: Speech-to-text processes audio bytes."""
    # Synthesize sample audio
    sample_wav = tts_engine.synthesize_to_wav("System health report")
    result = stt_engine.transcribe(sample_wav)
    assert "text" in result
    assert result["confidence"] > 0.0

def test_full_duplex_conversational_turn():
    """PWR-005: Full voice turn executes and returns audio response."""
    sample_wav = tts_engine.synthesize_to_wav("System health")
    res = asyncio.run(voice_pipeline.process_voice_turn(sample_wav, play_audio_live=False))

    assert res["status"] == "success"
    assert "transcription" in res
    assert "reply_text" in res
    assert len(res["audio_bytes"]) > 44
    assert res["audio_bytes"][:4] == b"RIFF"
