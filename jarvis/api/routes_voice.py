"""
JARVIS Voice REST API Routes
Endpoints for speech-to-text, text-to-speech, push-to-talk, and barge-in.
"""

from fastapi import APIRouter, UploadFile, File, Form, Response, HTTPException
from pydantic import BaseModel
from typing import Optional

from jarvis.voice.wake import wake_detector
from jarvis.voice.stt import stt_engine
from jarvis.voice.tts import tts_engine
from jarvis.voice.pipeline import voice_pipeline

router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])

class SynthesizeRequest(BaseModel):
    text: str
    play_live: bool = False

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribes an uploaded audio file (WAV/WebM) into text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file provided")
    return stt_engine.transcribe(audio_bytes)

@router.post("/synthesize")
async def synthesize_speech(req: SynthesizeRequest):
    """Synthesizes text into spoken audio (returns WAV binary stream)."""
    if req.play_live:
        tts_engine.speak_live(req.text, async_mode=True)
        return {"status": "playing_live", "text": req.text}

    wav_bytes = tts_engine.synthesize_to_wav(req.text)
    return Response(content=wav_bytes, media_type="audio/wav")

@router.post("/turn")
async def voice_conversational_turn(file: UploadFile = File(...)):
    """Executes a full voice conversational turn: Audio In -> Audio Out."""
    audio_bytes = await file.read()
    res = await voice_pipeline.process_voice_turn(audio_bytes, play_audio_live=False)
    wav_bytes = res.pop("audio_bytes", b"")

    headers = {
        "X-Jarvis-Transcription": res.get("transcription", ""),
        "X-Jarvis-Reply": res.get("reply_text", "")[:200],
        "X-Jarvis-Tier": res.get("tier", "")
    }
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)

@router.post("/push-to-talk")
async def trigger_ptt():
    """PWR-002: Immediately triggers push-to-talk wake event."""
    return wake_detector.trigger_push_to_talk(source="web_dashboard")

@router.post("/barge-in")
async def trigger_barge_in():
    """Interrupts active TTS speech immediately."""
    voice_pipeline.handle_barge_in()
    return {"status": "barge_in_triggered", "speech_cancelled": True}
