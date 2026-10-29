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
    assert data["total_powers"] == 355
    assert len(data["powers"]) == 355
    assert data["total_categories"] == 22

def test_api_powers_ecosystem():
    response = client.get("/api/v1/powers/ecosystem")
    assert response.status_code == 200
    data = response.json()
    assert data["total_powers"] == 355
    assert data["total_repositories"] == 11
    assert "openclaw" in data["repositories"]
    assert "browser-use" in data["repositories"]

def test_api_power_detail():
    # Valid lookup uppercase
    res = client.get("/api/v1/powers/PWR-001")
    assert res.status_code == 200
    assert res.json()["power_name"] == "Wake-Word Activation"

    # Valid lookup lowercase
    res_low = client.get("/api/v1/powers/pwr-001")
    assert res_low.status_code == 200
    assert res_low.json()["power_id"] == "PWR-001"

    # Invalid lookup 404
    res_404 = client.get("/api/v1/powers/PWR-NONEXISTENT")
    assert res_404.status_code == 404

def test_api_powers_filters():
    # Filter by repo
    res_repo = client.get("/api/v1/powers?repo=browser-use")
    assert res_repo.status_code == 200
    assert res_repo.json()["total_powers"] >= 10

    # Filter by category
    res_cat = client.get("/api/v1/powers?category=Voice")
    assert res_cat.status_code == 200
    assert res_cat.json()["total_powers"] >= 5

    # Filter by search query
    res_q = client.get("/api/v1/powers?q=screenshot")
    assert res_q.status_code == 200
    assert res_q.json()["total_matches"] >= 1

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
