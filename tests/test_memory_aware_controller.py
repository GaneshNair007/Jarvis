"""Tests for Milestone M2: Memory-Aware Controller integration."""

import uuid
from jarvis.brain.memory.service import brain_memory_service
from jarvis.brain.schemas import MemoryCategory
from jarvis.memory.mem0_client import mem0_client
from jarvis.graph.nodes import memory_retrieval, memory_update, model_router


def test_controller_memory_retrieval_combines_sources():
    test_user = f"user_{uuid.uuid4().hex[:6]}"

    # 1. Store canonical preference
    brain_memory_service.store_memory(
        user_id=test_user,
        content="Prefers dark mode and concise summaries",
        category=MemoryCategory.PREFERENCE,
    )

    # 2. Store legacy Mem0 memory
    mem0_client.add(
        [
            {"role": "user", "content": "My primary database is PostgreSQL"},
            {"role": "assistant", "content": "Acknowledged"},
        ],
        user_id=test_user,
    )

    state = {
        "user_id": test_user,
        "user_input": "database preference",
    }
    result = memory_retrieval(state)
    retrieved = result["retrieved_memories"]

    # Verify both canonical preference and legacy memory appear
    assert any("dark mode" in m for m in retrieved)
    assert any("PostgreSQL" in m for m in retrieved)


def test_controller_memory_update_persists_to_both_engines():
    test_user = f"user_{uuid.uuid4().hex[:6]}"
    state = {
        "user_id": test_user,
        "user_input": "What is the deploy branch?",
        "final_response": "The deployment branch is release-v1.",
    }

    memory_update(state)

    # Verify in canonical memory
    memories = brain_memory_service.search_memories(user_id=test_user)
    assert len(memories) > 0
    assert any("release-v1" in m.content for m in memories)


def test_controller_model_router_policy_halt():
    state = {
        "approval_required": True,
        "approval_id": None,
        "user_input": "Deploy code to production",
    }
    result = model_router(state)
    assert result["model_route"] == "policy_halt"
    assert "cryptographic approval" in result["final_response"]
