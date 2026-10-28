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

def test_orchestrator_chat_query():
    result = asyncio.run(orchestrator.process_user_query("What is the speed of light?"))
    assert result["status"] == "COMPLETED"
    assert result["tier"] in ["TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD"]

def test_five_layer_memory():
    # 1. Directive
    dir_id = memory_manager.add_directive("NeverDeleteRoot", "Never execute unapproved file deletions.")
    assert dir_id is not None

    directives = memory_manager.get_directives()
    assert len(directives) > 0
    assert any("Never execute unapproved" in d["content"] for d in directives)

    # 2. Episodic memory
    ep_id = memory_manager.store_memory(
        layer="EPISODIC",
        content="User discussed migrating database to PostgreSQL",
        metadata={"session_id": "sess_123"}
    )
    assert ep_id is not None

    recalled = memory_manager.recall(layer="EPISODIC", query="PostgreSQL")
    assert len(recalled) > 0
    assert "PostgreSQL" in recalled[0]["content"]
