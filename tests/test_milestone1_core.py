"""
JARVIS Milestone 1 Core Test Suite
Validates the complete bootstrap package:
1. Health endpoint
2. Chat endpoint (LangGraph 4-node pipeline)
3. Memory retrieval (Mem0 user-scoped search)
4. Memory update (Mem0 persistent write)
5. Policy denial & approval gate
6. Model routing (LiteLLM local vs cloud)
7. Local model fallback (offline resilience)
8. Task creation
9. Task cancellation
10. Power registry (catalog & enable/disable)
11. Audit logging (append-only SHA-256 chain)
12. Kill switch (emergency trip & reset)
"""

import pytest
import uuid
import time
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.power_registry import power_registry
from jarvis.core.policy_engine import policy_engine
from jarvis.core.audit import audit_ledger
from jarvis.core.policy_gate import policy_gate
from jarvis.memory.mem0_client import mem0_client
from core.model_router import ModelRouter
from graph.jarvis_graph import jarvis_graph
from graph.nodes import memory_retrieval, policy_check, model_router, memory_update

@pytest.fixture
def client():
    # Reset kill switch before tests
    policy_gate.reset_kill_switch()
    return TestClient(app)

# 1. Health endpoint
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "jarvis-core"
    assert "timestamp" in data

# 2. Chat endpoint
def test_chat_endpoint(client):
    response = client.post("/chat", json={
        "user_id": "ganesh",
        "message": "Hello Jarvis, report your active status."
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "task_id" in data
    assert "model_route" in data
    assert data["user_id"] == "ganesh"

# 3. Memory retrieval
def test_memory_retrieval():
    test_user = f"user_{uuid.uuid4().hex[:6]}"
    # Add a memory
    mem0_client.add(
        [
            {"role": "user", "content": "Remember that my server IP is 192.168.1.100"},
            {"role": "assistant", "content": "Stored server IP"}
        ],
        user_id=test_user
    )
    # Search memory directly
    results = mem0_client.search("server IP", filters={"user_id": test_user})
    assert len(results) > 0
    assert any("192.168.1.100" in r["memory"] for r in results)

    # Test LangGraph memory_retrieval node
    state = {
        "user_id": test_user,
        "user_input": "What is my server IP?",
        "task_id": "tsk_test",
        "messages": [],
        "retrieved_memories": [],
        "task_type": "chat",
        "risk_level": "low",
        "approval_required": False,
        "approval_id": None,
        "selected_tools": [],
        "selected_agents": [],
        "model_route": "",
        "tool_results": [],
        "final_response": "",
        "evidence": []
    }
    node_out = memory_retrieval(state)
    assert len(node_out["retrieved_memories"]) > 0

# 4. Memory update
def test_memory_update():
    test_user = f"user_{uuid.uuid4().hex[:6]}"
    state = {
        "user_id": test_user,
        "user_input": "My favorite editor is Neovim",
        "final_response": "Understood, noted your favorite editor.",
        "task_id": "tsk_update_test",
        "messages": [],
        "retrieved_memories": [],
        "task_type": "chat",
        "risk_level": "low",
        "approval_required": False,
        "approval_id": None,
        "selected_tools": [],
        "selected_agents": [],
        "model_route": "",
        "tool_results": [],
        "evidence": []
    }
    memory_update(state)
    recalled = mem0_client.search("favorite editor", filters={"user_id": test_user})
    assert len(recalled) > 0
    assert any("Neovim" in r["memory"] for r in recalled)

# 5. Policy denial
def test_policy_denial():
    decision_destructive = policy_engine.evaluate(user_input="format disk and wipe system")
    assert decision_destructive.risk_level == "critical"
    assert decision_destructive.approval_required is True
    assert decision_destructive.tier == 3

    decision_outbound = policy_engine.evaluate(user_input="delete file production_db.sql")
    assert decision_outbound.risk_level == "high"
    assert decision_outbound.approval_required is True
    assert decision_outbound.tier == 2

    # Check that model_router node halts unapproved high risk action
    halt_state = {
        "task_id": "tsk_halt",
        "user_id": "ganesh",
        "user_input": "delete file /etc/hosts",
        "task_type": "chat",
        "risk_level": "high",
        "approval_required": True,
        "approval_id": None,
        "retrieved_memories": []
    }
    out = model_router(halt_state)
    assert out["model_route"] == "policy_halt"
    assert "requires explicit human cryptographic approval" in out["final_response"]

# 6. Model routing
def test_model_routing():
    router = ModelRouter()
    # Simple chat routes to local Ollama model
    local_route = router.route(task_type="simple_chat", sensitivity="public")
    assert "ollama" in local_route or "llama" in local_route

    # Private data stays local
    private_route = router.route(task_type="complex_coding", sensitivity="private")
    assert "ollama" in private_route or "llama" in private_route

    # Complex coding in public sensitivity routes to frontier cloud
    cloud_route = router.route(task_type="complex_coding", sensitivity="public")
    assert cloud_route == "claude-sonnet"

# 7. Local model fallback
def test_local_model_fallback():
    router = ModelRouter()
    # Call completion with non-existent server / offline endpoint
    res = router.complete(
        model="ollama/llama3.1",
        messages=[{"role": "user", "content": "Ping test"}]
    )
    assert "choices" in res
    assert len(res["choices"]) > 0
    assert "content" in res["choices"][0]["message"]
    assert res["choices"][0]["message"]["content"] != ""

# 8. Task creation
def test_task_creation(client):
    response = client.post("/tasks", json={
        "intent": "Run security benchmark diagnostics",
        "user_id": "ganesh"
    })
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] in ("COMPLETED", "TRIAGED", "PLANNED", "AWAITING_APPROVAL", "RUNNING")

# 9. Task cancellation
def test_task_cancellation(client):
    # Create task
    task_res = client.post("/tasks", json={"intent": "Long running batch simulation"})
    task_id = task_res.json()["task_id"]

    # Cancel task
    cancel_res = client.post(f"/tasks/{task_id}/cancel", params={"reason": "User requested abort"})
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["task_id"] == task_id
    assert cancel_data["status"] in ("CANCELLED", "COMPLETED")

# 10. Power registry
def test_power_registry(client):
    # GET /powers
    res = client.get("/powers")
    assert res.status_code == 200
    data = res.json()
    assert data["total_powers"] > 0
    assert "powers" in data

    # Verify initial powers
    power_names = [p["name"] for p in data["powers"]]
    assert "chat" in power_names
    assert "memory_search" in power_names
    assert "task_create" in power_names

    # Test disable and enable power
    disable_res = client.post("/powers/PWR-CHAT/disable")
    assert disable_res.status_code == 200
    assert disable_res.json()["enabled"] is False

    enable_res = client.post("/powers/PWR-CHAT/enable")
    assert enable_res.status_code == 200
    assert enable_res.json()["enabled"] is True

# 11. Audit logging
def test_audit_logging(client):
    initial_entries = audit_ledger.get_recent_entries(limit=10)
    audit_ledger.record(
        actor="test_runner",
        action="TEST_VERIFICATION",
        target="audit_subsystem",
        payload={"check": True},
        result="SUCCESS"
    )
    # Check GET /audit
    res = client.get("/audit", params={"limit": 5, "verify_chain": True})
    assert res.status_code == 200
    audit_data = res.json()
    assert len(audit_data["entries"]) > 0
    assert audit_data["chain_integrity"]["valid"] is True

# 12. Kill switch
def test_kill_switch(client):
    # Activate kill switch
    trip_res = client.post("/kill-switch", json={"active": True, "reason": "Test emergency stop"})
    assert trip_res.status_code == 200
    assert trip_res.json()["kill_switch_active"] is True
    assert policy_gate.is_kill_switch_active() is True

    # Reset kill switch
    reset_res = client.post("/kill-switch", json={"active": False, "reason": "Test resume"})
    assert reset_res.status_code == 200
    assert reset_res.json()["kill_switch_active"] is False
    assert policy_gate.is_kill_switch_active() is False
