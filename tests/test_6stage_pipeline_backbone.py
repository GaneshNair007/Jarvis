"""
Tests for JARVIS 6-Stage Execution Pipeline Backbone.

Verifies:
- Stage 1: Understand (intent parsing, dialogue context recall, deterministic OS fast-path)
- Stage 2: Plan (subtask decomposition, dependency ordering)
- Stage 3: Select (mapping to the 8 canonical specialist agent roles)
- Stage 4: Execute (tool & model execution with policy evaluation)
- Stage 5: Verify (independent verification via CriticAgent issuing structured Verdict)
- Stage 6: Consolidate & Persist (single consolidated answer, ConversationService persistence)
- Multi-turn conversational continuity across pipeline runs.
"""

import asyncio
from unittest.mock import patch, MagicMock
import pytest

from jarvis.core.orchestrator import JarvisOrchestrator
from jarvis.memory.conversation_service import ConversationService
from jarvis.agents.critic import Verdict


@pytest.fixture
def test_orchestrator(tmp_path):
    """Provides a fresh JarvisOrchestrator instance with isolated in-memory memory service."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from jarvis.memory.models import Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    mem_service = ConversationService(engine=engine, session_factory=session_factory)

    orch = JarvisOrchestrator()
    orch.conversation_service = mem_service
    return orch


def test_stage_1_deterministic_os_shortcut_bypasses_planning(test_orchestrator):
    """Verifies that Stage 1 immediately executes deterministic OS commands without invoking LLM."""
    query = "take screenshot"
    res = asyncio.run(test_orchestrator.process_user_query(query, conversation_id="os_sess"))

    assert res["status"] == "COMPLETED"
    assert res["tier"] == "BYPASS"
    assert "understand" in res["stages_executed"]
    assert res["stage_outputs"]["understand"]["is_instant_shortcut"] is True
    assert res["verdict"] == "pass"

    # Context must still be stored in conversation service
    history = test_orchestrator.conversation_service.get_recent_context("os_sess")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "take screenshot"
    assert history[1]["role"] == "assistant"


def test_6stage_pipeline_full_execution_flow(test_orchestrator):
    """Verifies all 6 stages execute in sequence for a standard request."""
    query = "Research latest papers on quantum neuromorphic computing"
    mock_inference_reply = {
        "status": "success",
        "tier": "TIER_1_LOCAL",
        "model": "ollama/llama3.1",
        "reply": "Quantum neuromorphic computing integrates superconducting qubits with spike-timing networks.",
        "tokens_used": 42,
        "cost_usd": 0.0,
    }

    with patch.object(test_orchestrator.router, "execute_inference", return_value=mock_inference_reply):
        res = asyncio.run(test_orchestrator.process_user_query(query, conversation_id="quantum_sess"))

        # Verify Pipeline Completion
        assert res["status"] == "COMPLETED"
        assert res["stages_executed"] == [
            "understand",
            "plan",
            "select",
            "execute",
            "verify",
            "consolidate_persist",
        ]

        # Stage 1: Understand
        s1 = res["stage_outputs"]["understand"]
        assert s1["query"] == query
        assert s1["decision"]["tier"] in ["TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD", "FALLBACK_CLOUD"]

        # Stage 2: Plan
        s2 = res["stage_outputs"]["plan"]
        assert s2["subtask_count"] >= 1
        assert any(st["role"] == "researcher" for st in s2["subtasks"])

        # Stage 3: Select
        s3 = res["stage_outputs"]["select"]
        assert "researcher" in s3["selected_roles"]
        assert "reviewer" in s3["selected_roles"]
        assert s3["verifier"] == "reviewer"

        # Stage 4: Execute
        s4 = res["stage_outputs"]["execute"]
        assert s4["execution_status"] == "success"
        assert s4["model_used"] == "ollama/llama3.1"
        assert s4["tokens_used"] == 42

        # Stage 5: Verify
        s5 = res["stage_outputs"]["verify"]
        assert s5["verdict"] in [Verdict.PASS.value, Verdict.PASS_WITH_WARNINGS.value]
        assert s5["score"] > 0.0

        # Stage 6: Consolidate & Persist
        s6 = res["stage_outputs"]["consolidate_persist"]
        assert s6["persisted_conversation_id"] == "quantum_sess"
        assert "Quantum neuromorphic computing" in s6["final_reply"]

        # Verify Persistence in ConversationService
        history = test_orchestrator.conversation_service.get_recent_context("quantum_sess")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == query
        assert history[1]["role"] == "assistant"
        assert "Quantum neuromorphic" in history[1]["content"]


def test_specialist_role_selection_mappings(test_orchestrator):
    """Verifies that Stage 3 correctly binds requests to canonical specialist roles."""
    # Engineering query
    eng_roles = test_orchestrator._map_query_to_specialists("Write a python script to parse AST and run pytest")
    assert "engineer" in eng_roles
    assert "reviewer" in eng_roles

    # Academic Tutor query
    acad_roles = test_orchestrator._map_query_to_specialists("Help me break down my operating systems assignment and prepare viva questions")
    assert "academic_tutor" in acad_roles

    # Career query
    career_roles = test_orchestrator._map_query_to_specialists("Review my resume for GSoC and find machine learning hackathons")
    assert "career" in career_roles

    # Communication query
    comm_roles = test_orchestrator._map_query_to_specialists("Draft an email reply to the hiring manager and check inbox")
    assert "communication" in comm_roles

    # Productivity query
    prod_roles = test_orchestrator._map_query_to_specialists("Check my schedule and set a deadline reminder for tomorrow")
    assert "productivity" in prod_roles


def test_critic_agent_verification_in_stage_5(test_orchestrator):
    """Verifies that Stage 5 catches safety violations (PII/secrets) and issues appropriate verdict."""
    query = "Give me test API key example"
    # Output contains a leak of a secret token
    leaky_reply = {
        "status": "success",
        "tier": "TIER_1_LOCAL",
        "model": "ollama/llama3.1",
        "reply": "Here is the key: api_key = sk-live-99887766554433221100aabbccddeeff",
        "tokens_used": 15,
    }

    with patch.object(test_orchestrator.router, "execute_inference", return_value=leaky_reply):
        res = asyncio.run(test_orchestrator.process_user_query(query, conversation_id="critic_sess"))

        s5 = res["stage_outputs"]["verify"]
        # Critic should catch secret_key pattern
        assert s5["issues_count"] > 0
        categories = [i["category"] for i in s5["issues"]]
        assert "safety" in categories or "policy" in categories


def test_multi_turn_dialogue_preserved_across_queries(test_orchestrator):
    """Verifies that consecutive queries across the 6-stage pipeline recall dialogue history."""
    conv_id = "dialogue_continuity_sess"

    mock_reply_1 = {
        "status": "success",
        "tier": "TIER_1_LOCAL",
        "model": "ollama/llama3.1",
        "reply": "I have registered your interest in Autonomous Drone Operating Systems.",
        "tokens_used": 20,
    }

    mock_reply_2 = {
        "status": "success",
        "tier": "TIER_1_LOCAL",
        "model": "ollama/llama3.1",
        "reply": "For the Autonomous Drone OS, here is the real-time sensor fusion architecture.",
        "tokens_used": 25,
    }

    # Turn 1
    with patch.object(test_orchestrator.router, "execute_inference", return_value=mock_reply_1):
        res1 = asyncio.run(
            test_orchestrator.process_user_query("I am developing an Autonomous Drone OS", conversation_id=conv_id)
        )
        assert res1["status"] == "COMPLETED"

    # Turn 2
    with patch.object(test_orchestrator.router, "execute_inference", return_value=mock_reply_2):
        res2 = asyncio.run(
            test_orchestrator.process_user_query("Design the sensor fusion pipeline for it", conversation_id=conv_id)
        )
        assert res2["status"] == "COMPLETED"
        # Stage 1 of Turn 2 must show previous turns recalled
        assert res2["stage_outputs"]["understand"]["dialogue_history_recalled"] >= 2

    # Verify conversation service state
    all_turns = test_orchestrator.conversation_service.get_recent_context(conv_id, limit=10)
    assert len(all_turns) == 4
    assert all_turns[0]["content"] == "I am developing an Autonomous Drone OS"
    assert all_turns[1]["content"] == "I have registered your interest in Autonomous Drone Operating Systems."
    assert all_turns[2]["content"] == "Design the sensor fusion pipeline for it"
    assert all_turns[3]["content"] == "For the Autonomous Drone OS, here is the real-time sensor fusion architecture."
