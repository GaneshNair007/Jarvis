"""
Automated verification tests for End-to-End Orchestrator and Persistent Memory.
"""

import asyncio
from jarvis.core.orchestrator import orchestrator
from jarvis.memory.layers import memory_manager


def test_orchestrator_instant_command():
    result = asyncio.run(orchestrator.process_user_query("System health"))
    assert result["status"] == "COMPLETED"
    assert result["tier"] == "BYPASS"
    assert "cpu_percent" in result["response"]


def test_orchestrator_chat_query(monkeypatch):
    monkeypatch.setattr(
        orchestrator.router,
        "execute_inference",
        lambda **_kwargs: {"status": "completed", "reply": "The speed of light is approximately 299,792 km/s."},
    )
    result = asyncio.run(orchestrator.process_user_query("What is the speed of light?"))
    assert result["status"] == "COMPLETED"
    assert result["tier"] in ["TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD"]
    assert result["response"]["reply"].startswith("The speed of light")


def test_five_layer_memory():
    # 1. Directive
    dir_id = memory_manager.add_directive("NeverDeleteRoot", "Never execute unapproved file deletions.")
    assert dir_id is not None

    directives = memory_manager.get_directives()
    assert len(directives) > 0
    assert any("Never execute unapproved" in d["content"] for d in directives)

    # 2. Episodic memory
    ep_id = memory_manager.store_memory(
        layer="EPISODIC", content="User discussed migrating database to PostgreSQL", metadata={"session_id": "sess_123"}
    )
    assert ep_id is not None

    recalled = memory_manager.recall(layer="EPISODIC", query="PostgreSQL")
    assert len(recalled) > 0
    assert "PostgreSQL" in recalled[0]["content"]


def test_unhandled_instant_command_never_claims_success():
    result = orchestrator._execute_instant_command("open an unsupported application")
    assert result["status"] == "unavailable"
    assert result["error"] == "NO_HANDLER"


def test_smart_home_demo_state_is_never_reported_as_physical_control():
    result = orchestrator._execute_instant_command("turn on the AC")
    assert result["status"] == "unavailable"
    assert result["error"] == "NO_VERIFIED_DEVICE_CONTROLLER"


def test_screenshot_requires_a_real_capture_receipt(monkeypatch):
    from jarvis.powers.screen_powers import screen_powers

    monkeypatch.setattr(
        screen_powers,
        "capture_region",
        lambda: {"status": "success", "path": "capture.png", "sha256": "abc123"},
    )
    result = orchestrator._execute_instant_command("take screenshot")
    assert result["status"] == "success"
    assert result["file"] == "capture.png"
    assert result["sha256"] == "abc123"
