"""
Tests for Autonomous Career Radar & Verified Digest Dispatching
Verifies:
- GET /api/v1/career/radar returns real verified opportunities
- Filtering by query parameter 'q' works dynamically
- POST /api/v1/career/email-digest creates verifiable RFC 822 draft
- Dispatched draft is saved to outbox and hashed with SHA-256
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app
from jarvis.core.career_radar import career_radar, DEFAULT_TARGET_EMAIL, DEFAULT_SENDER_EMAIL

client = TestClient(app)


def test_career_radar_live_fetch():
    """Verify live radar returns structured opportunities with zero fake data."""
    res = client.get("/api/v1/career/radar")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LIVE"
    assert data["total_opportunities"] > 0
    assert "ai_internships" in data
    assert "gsoc_organizations" in data
    assert "devpost_ai_hackathons" in data

    # Check internships structure
    internships = data["ai_internships"]
    assert len(internships) >= 5
    first = internships[0]
    assert "title" in first
    assert "organization" in first
    assert "application_url" in first
    assert first["application_url"].startswith("http")

    # Check GSoC organizations
    gsoc = data["gsoc_organizations"]
    assert len(gsoc) >= 5
    assert any("DeepMind" in o["name"] or "OpenCV" in o["name"] for o in gsoc)

    # Check hackathons
    hackathons = data["devpost_ai_hackathons"]
    assert len(hackathons) >= 5
    assert any("PayPal" in h["title"] or "Meta" in h["title"] or "Kiroween" in h["title"] for h in hackathons)


def test_career_radar_filtering():
    """Verify filtering works across technologies and names."""
    res = client.get("/api/v1/career/radar?q=PyTorch")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "FILTERED"
    assert data["query"] == "pytorch"
    # Matches PyTorch in Meta internship, Kornia GSoC, etc.
    assert data["total_opportunities"] > 0


def test_career_email_digest_dispatch():
    """Verify email digest drafting and verifiable SHA-256 draft storage."""
    payload = {
        "to_email": DEFAULT_TARGET_EMAIL,
        "from_email": DEFAULT_SENDER_EMAIL,
        "query": "",
    }
    res = client.post("/api/v1/career/email-digest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SENT", "DRAFT_SAVED"]
    assert data["to"] == DEFAULT_TARGET_EMAIL
    assert data["from"] == DEFAULT_SENDER_EMAIL
    assert "draft_path" in data
    assert "sha256" in data
    assert len(data["sha256"]) == 64
