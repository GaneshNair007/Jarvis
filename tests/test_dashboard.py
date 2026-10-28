"""
Automated verification tests for Phase 0 Dashboard and Voice API Routes.
"""

from fastapi.testclient import TestClient
from jarvis.api.server import app

client = TestClient(app)

def test_serve_dashboard_root():
    """Phase 0: Web dashboard HTML served at '/'."""
    response = client.get("/")
    assert response.status_code == 200
    assert "JARVIS — Personal AI Operating System HUD" in response.text
    assert "System Telemetry" in response.text
    assert "Command Console" in response.text

def test_serve_dashboard_explicit_route():
    """Phase 0: Web dashboard HTML served at '/dashboard'."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "JARVIS" in response.text

def test_voice_push_to_talk_api():
    """Phase 1: Push-to-talk REST trigger."""
    response = client.post("/api/v1/voice/push-to-talk")
    assert response.status_code == 200
    data = response.json()
    assert data["trigger"] == "push_to_talk"

def test_voice_barge_in_api():
    """Phase 1: Barge-in REST trigger."""
    response = client.post("/api/v1/voice/barge-in")
    assert response.status_code == 200
    data = response.json()
    assert data["speech_cancelled"] is True

def test_voice_synthesize_api():
    """Phase 1: Speech synthesis REST endpoint returns WAV audio."""
    payload = {"text": "Jarvis online", "play_live": False}
    response = client.post("/api/v1/voice/synthesize", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert len(response.content) > 44
    assert response.content[:4] == b"RIFF"
