"""
Automated verification tests for FastAPI REST Endpoints.
"""

from fastapi.testclient import TestClient
from jarvis.api.server import app

client = TestClient(app)

def test_api_model_status():
    response = client.get("/model/status")
    assert response.status_code == 200
    data = response.json()
    assert "tier_1_local" in data
    assert "tier_2_private" in data
    assert "tier_3_cloud" in data

def test_api_model_route_bypass():
    payload = {
        "user_intent": "Open VS Code",
        "task_type": "instant_command"
    }
    response = client.post("/model/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "BYPASS"
    assert data["provider"] == "deterministic"

def test_api_model_route_sensitive():
    payload = {
        "user_intent": "Analyze private tax statement",
        "task_type": "memory_retrieval",
        "sensitivity_level": "confidential",
        "attached_context": "Annual salary and investment holdings"
    }
    response = client.post("/model/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] in ["TIER_1_LOCAL", "TIER_2_PRIVATE"]

def test_api_system_health():
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data

def test_api_chat():
    payload = {"query": "System health"}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["tier"] == "BYPASS"

def test_api_powers():
    response = client.get("/api/v1/powers")
    assert response.status_code == 200
    data = response.json()
    assert data["total_powers"] >= 300

def test_api_audit():
    response = client.get("/api/v1/audit?verify_chain=true")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert data["chain_integrity"]["valid"] is True

def test_api_kill_switch():
    # Activate
    resp_on = client.post("/api/v1/kill-switch?active=true&reason=Test")
    assert resp_on.status_code == 200
    assert resp_on.json()["kill_switch_active"] is True

    # Reset
    resp_off = client.post("/api/v1/kill-switch?active=false")
    assert resp_off.status_code == 200
    assert resp_off.json()["kill_switch_active"] is False
