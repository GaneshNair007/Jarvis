"""
End-to-End JARVIS Functional Verification.

Proves JARVIS is fully functional end-to-end:
  * Speaks (TTS via SAPI -> real WAV audio)
  * Thinks & acts offline (model router local-heuristic fallback)
  * Codes (multi-agent subagent dispatch with Evidence/TrustResult)
  * Self-improves (CODER_ANTIGRAVITY -> self_upgrade_pipeline)
  * Runs multiple subagents in parallel (swarm execute_plan)
  * Executes instant OS commands through the orchestrator
"""

import io
import wave
import asyncio

import pytest
from pathlib import Path

from jarvis.core.evidence import TrustResult
from jarvis.core.model_router import model_router, RoutingRequest, RoutingDecision
from jarvis.core.orchestrator import orchestrator
from jarvis.voice.tts import tts_engine
from jarvis.powers.multiagent_powers import multiagent_powers


# --------------------------------------------------------------------- #
#  Speak: TTS produces real audio                                       #
# --------------------------------------------------------------------- #


def test_tts_speaks_real_audio():
    """JARVIS can speak: synthesize_to_wav returns valid WAV audio bytes."""
    wav = tts_engine.synthesize_to_wav("JARVIS online. Systems functional.")
    assert wav[:4] == b"RIFF", "TTS did not produce a WAV file"
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() in (16000, 22050, 44100)
        frames = wf.readframes(wf.getnframes())
        assert len(frames) > 1000, "TTS produced no audible samples"


# --------------------------------------------------------------------- #
#  Think & Act: offline local-heuristic reasoning                       #
# --------------------------------------------------------------------- #


def test_think_offline_returns_helpful_reply():
    """With no LLM backend, JARVIS still reasons via local reflex (success, not unavailable)."""
    decision = RoutingDecision(
        task_id="tsk_e2e_think",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="offline e2e",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )
    resp = model_router.execute_inference(decision, "Who are you?")
    assert resp["status"] == "success"
    assert resp["error"] is None
    assert "JARVIS" in resp["reply"] or "assistant" in resp["reply"].lower()
    assert resp["cost_usd"] == 0.0


# --------------------------------------------------------------------- #
#  Code: subagent dispatch returns Evidence-backed result               #
# --------------------------------------------------------------------- #


def test_coding_subagent_returns_evidence_backed_result():
    """A coding subagent executes a task and returns Evidence + TrustResult."""
    res = multiagent_powers.invoke_subagent("coder", {"task": "Write a function to ping a host"})
    assert res["status"] == "COMPLETED"
    assert "trust_result" in res
    assert res["trust_result"]["verdict"] == "success"
    assert res["trust_result"]["evidence"]["source"].startswith("multiagent.")
    assert "coder" in res["output"].lower()


# --------------------------------------------------------------------- #
#  Antigravity: self-improvement pipeline                               #
# --------------------------------------------------------------------- #


def test_antigravity_self_upgrade_pipeline():
    """CODER_ANTIGRAVITY routes to the real self_upgrade_pipeline (PWR-310)."""
    codebase = "D:\\jarvis" if Path("D:\\jarvis").exists() else str(Path(__file__).resolve().parent.parent)
    res = multiagent_powers.invoke_subagent("coder_antigravity", {"codebase_path": codebase})
    assert res["power_id"] == "PWR-310"
    assert res["status"] in ("COMPLETED", "PARTIAL")
    assert "trust_result" in res
    assert res["trust_result"]["verdict"] == "success"
    assert res["tests_total"] >= 1


# --------------------------------------------------------------------- #
#  Subagents: parallel multi-task execution through the swarm           #
# --------------------------------------------------------------------- #


def test_swarm_runs_multiple_subagents_in_parallel():
    """The swarm decomposes a coding goal and runs subtasks in parallel."""
    plan = multiagent_powers.swarm.decompose_goal("Build a system health monitor with tests")
    assert len(plan.tasks) >= 2
    assert plan.tasks[0].role.value in ("planner", "coder")
    assert plan.tasks[-1].role.value in ("security_guard", "reviewer_critic")

    completed = asyncio.run(multiagent_powers.swarm.execute_plan(plan.plan_id))
    assert completed.status == "COMPLETED"
    assert all(t.status == "COMPLETED" for t in completed.tasks)
    assert completed.total_cost_usd > 0
    # Every subtask produced structured output (not a stub string).
    for t in completed.tasks:
        assert "role" in t.outputs
        assert "power_id" in t.outputs


# --------------------------------------------------------------------- #
#  Orchestrator: instant command + code dispatch end-to-end             #
# --------------------------------------------------------------------- #


def test_orchestrator_executes_instant_command():
    """The orchestrator routes 'system health' to BYPASS and COMPLETES it."""
    import asyncio

    res = asyncio.run(orchestrator.process_user_query("system health"))
    assert res["status"] == "COMPLETED"
    assert res["tier"] == "BYPASS"
    assert "cpu_percent" in res["response"]


def test_orchestrator_routes_code_to_subagents():
    """A '/code' goal dispatches through the multi-agent swarm (PWR-288)."""
    import asyncio

    res = asyncio.run(orchestrator.process_user_query("/code write a hello world function"))
    assert res["status"] == "COMPLETED"
    assert res["response"]["power_id"] == "PWR-288"
    assert res["response"]["subtasks_executed"] >= 2
