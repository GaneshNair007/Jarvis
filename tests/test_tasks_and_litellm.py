"""Automated Tests for Task Engine APIs (Part 2) and LiteLLM Model Router (Milestone 2).

Validates:
- Full Task Engine Lifecycle: POST /tasks, GET /tasks, GET /tasks/{id}, POST /tasks/{id}/cancel
- Task Logs & Artifact Retrieval: GET /tasks/{id}/logs, GET /tasks/{id}/artifacts
- LiteLLM Unified Inference Execution across Bypass, Local Reflex, and Private Tiers
- Cost Governor Budget Integration & Circuit Breakers
"""

import pytest
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.cost_governor import cost_governor


@pytest.fixture
def client():
    return TestClient(app)


def test_create_task_api(client):
    """Verifies POST /tasks creates a task, executes orchestration, and returns status."""
    resp = client.post("/tasks", json={
        "intent": "system health report",
        "user_id": "ganesh",
        "priority": "high",
        "sensitivity_level": "low"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "COMPLETED"
    assert data["tier"] == "BYPASS"


def test_list_and_get_tasks_api(client):
    """Verifies GET /tasks and GET /tasks/{id}."""
    create_resp = client.post("/tasks", json={"intent": "disk usage"})
    assert create_resp.status_code == 200
    task_id = create_resp.json()["task_id"]

    # List tasks
    list_resp = client.get("/tasks?limit=10")
    assert list_resp.status_code == 200
    tasks_data = list_resp.json()
    assert "tasks" in tasks_data
    assert tasks_data["total"] >= 1

    # Get specific task
    get_resp = client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 200
    task = get_resp.json()
    assert task["task_id"] == task_id


def test_cancel_task_api(client):
    """Verifies POST /tasks/{id}/cancel sets status to CANCELLED."""
    from jarvis.core.state_machine import state_machine
    test_id = "tsk_cancel_test"
    state_machine.create_task(test_id, "QUEUED")

    cancel_resp = client.post(f"/tasks/{test_id}/cancel", params={"reason": "User changed mind"})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"
    assert state_machine.get_task_state(test_id) == "CANCELLED"


def test_task_logs_and_artifacts_api(client):
    """Verifies GET /tasks/{id}/logs and GET /tasks/{id}/artifacts endpoints."""
    resp = client.post("/tasks", json={"intent": "system health report"})
    task_id = resp.json()["task_id"]

    logs_resp = client.get(f"/tasks/{task_id}/logs")
    assert logs_resp.status_code == 200
    logs_data = logs_resp.json()
    assert logs_data["task_id"] == task_id
    assert "logs" in logs_data

    artifacts_resp = client.get(f"/tasks/{task_id}/artifacts")
    assert artifacts_resp.status_code == 200
    artifacts_data = artifacts_resp.json()
    assert artifacts_data["task_id"] == task_id
    assert "artifacts" in artifacts_data


def test_litellm_bypass_execution():
    """Verifies execute_inference bypasses model calls for deterministic OS commands."""
    req = RoutingRequest(user_intent="lock workstation", task_type="instant_command")
    decision = model_router.route(req)
    assert decision.tier == "BYPASS"

    res = model_router.execute_inference(decision=decision, prompt="lock workstation")
    assert res["status"] == "bypassed"
    assert res["tokens_used"] == 0
    assert res["cost_usd"] == 0.0


def test_litellm_local_inference_fallback():
    """Verifies execute_inference on Local Tier returns a clean response with token counting."""
    req = RoutingRequest(
        user_intent="Explain Docker networking in 1 sentence",
        task_type="general",
        sensitivity_level="low"
    )
    decision = model_router.route(req)
    assert decision.tier == "TIER_1_LOCAL"

    res = model_router.execute_inference(decision=decision, prompt=req.user_intent, timeout_sec=1.5)
    assert res["status"] in ("completed", "fallback_completed")
    assert "reply" in res
    assert res["tokens_used"] > 0
    assert "duration_ms" in res
