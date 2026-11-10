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
    payload = {"user_intent": "Open VS Code", "task_type": "instant_command"}
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
        "attached_context": "Annual salary and investment holdings",
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
    assert data["boot_time"] is not None
    assert isinstance(data["boot_time"], str)
    assert data["disk"]["percent"] >= 0.0
    assert data["host_status"] in ["healthy", "warning", "critical"]
    assert data["status"] in ["healthy", "degraded", "critical"]


def test_system_health_disk_threshold_critical(monkeypatch):
    """Verify disk >= 95% or free < 2GB triggers critical status in it_admin_powers and /api/v1/system/health."""
    from unittest.mock import MagicMock
    import psutil
    from jarvis.powers.it_admin_powers import it_admin_powers

    mock_disk = MagicMock(total=100 * (1024**3), used=96 * (1024**3), free=1.5 * (1024**3), percent=96.0)
    mock_ram = MagicMock(total=16 * (1024**3), used=4 * (1024**3), available=12 * (1024**3), percent=25.0)
    monkeypatch.setattr(psutil, "disk_usage", lambda path: mock_disk)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_ram)
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 10.0)

    report = it_admin_powers.system_health_report()
    assert report["status"] == "critical"
    assert report["boot_time"] is not None
    assert isinstance(report["boot_time"], str)

    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["host_status"] == "critical"
    assert data["status"] == "critical"


def test_system_health_disk_threshold_warning(monkeypatch):
    """Verify disk >= 90% and < 95% triggers warning status in it_admin_powers and degraded in /api/v1/system/health."""
    from unittest.mock import MagicMock
    import psutil
    from jarvis.powers.it_admin_powers import it_admin_powers

    mock_disk = MagicMock(total=100 * (1024**3), used=92 * (1024**3), free=8.0 * (1024**3), percent=92.0)
    mock_ram = MagicMock(total=16 * (1024**3), used=4 * (1024**3), available=12 * (1024**3), percent=25.0)
    monkeypatch.setattr(psutil, "disk_usage", lambda path: mock_disk)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_ram)
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 10.0)

    report = it_admin_powers.system_health_report()
    assert report["status"] == "warning"

    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["host_status"] == "warning"
    assert data["status"] in ["degraded", "critical"]


def test_system_health_healthy(monkeypatch):
    """Verify normal resource levels yield healthy host_status."""
    from unittest.mock import MagicMock
    import psutil
    from jarvis.powers.it_admin_powers import it_admin_powers

    mock_disk = MagicMock(total=100 * (1024**3), used=40 * (1024**3), free=60.0 * (1024**3), percent=40.0)
    mock_ram = MagicMock(total=16 * (1024**3), used=4 * (1024**3), available=12 * (1024**3), percent=25.0)
    monkeypatch.setattr(psutil, "disk_usage", lambda path: mock_disk)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_ram)
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 10.0)

    report = it_admin_powers.system_health_report()
    assert report["status"] == "healthy"

    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["host_status"] == "healthy"


def test_system_health_logger_exception_resilience(monkeypatch):
    """Verify that exceptions in telemetry gathering log a warning and return evidence_health without crashing."""
    from jarvis.powers.it_admin_powers import it_admin_powers

    def faulty_report():
        raise RuntimeError("Telemetry failure simulation")

    monkeypatch.setattr(it_admin_powers, "system_health_report", faulty_report)
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


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


def test_api_scheduler_endpoints():
    # 1. GET /scheduler/status
    res = client.get("/scheduler/status")
    assert res.status_code == 200
    data = res.json()
    assert data["total_jobs"] == 3
    assert "career_internship_scout" in [j["job_id"] for j in data["jobs"]]

    # 2. POST /scheduler/trigger/invalid_job
    bad_res = client.post("/scheduler/trigger/invalid_job_999")
    assert bad_res.status_code == 404


def test_api_workforce_fleet_status():
    res = client.get("/workforce/fleet")
    assert res.status_code == 200
    data = res.json()
    assert data["total_agents"] == 105
    assert data["status"] == "ALL_SYSTEMS_OPERATIONAL"
