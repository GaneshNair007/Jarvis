"""Automated Tests for Multi-Agent Swarm Orchestration (PWR-288 to PWR-307).

Validates:
- PWR-288: Orchestrator agent dispatch and plan execution
- PWR-289: Planner agent decomposition
- PWR-290 to PWR-301: Specialized sub-agent invocations
- PWR-303: Live agent dashboard telemetry
- PWR-304: Inter-agent handoff with context preservation
- PWR-305: Bounded parallel execution (max concurrency semaphore)
- PWR-306: Cumulative agent cost tracker
- PWR-307: Graceful cancellation via cancellation tokens
"""

import pytest
import asyncio
from jarvis.agents.swarm import AgentRole, agent_swarm
from jarvis.powers.multiagent_powers import multiagent_powers


def test_pwr_288_orchestrator_dispatch():
    """Validates end-to-end multi-agent goal dispatch."""
    res = multiagent_powers.orchestrator_dispatch("Research and summarize recent vector search advances")
    assert res["power_id"] == "PWR-288"
    assert res["status"] == "COMPLETED"
    assert res["subtasks_executed"] >= 2


def test_pwr_289_plan_and_decompose():
    """Validates goal decomposition into structured subtasks."""
    res = multiagent_powers.plan_and_decompose("Build a distributed event queue in Python")
    assert res["power_id"] == "PWR-289"
    assert len(res["tasks"]) >= 3
    assert any(t["role"] == "coder" for t in res["tasks"])


def test_specialized_subagents_pwr_290_to_301():
    """Validates individual sub-agent role handlers."""
    roles = [
        ("researcher", "PWR-290"),
        ("coder", "PWR-291"),
        ("file_agent", "PWR-292"),
        ("browser", "PWR-293"),
        ("system_admin", "PWR-294"),
        ("finance", "PWR-295"),
        ("content_strategist", "PWR-296"),
        ("reviewer_critic", "PWR-297"),
        ("security_guard", "PWR-298"),
        ("approval_manager", "PWR-299"),
        ("memory_manager", "PWR-300"),
        ("tool_selector", "PWR-301"),
    ]

    for role_name, expected_power in roles:
        res = multiagent_powers.invoke_subagent(role_name, {"sample": "input"})
        assert res["power_id"] == expected_power
        assert res["status"] == "COMPLETED"


def test_pwr_303_agent_dashboard():
    """Validates agent telemetry dashboard output."""
    dash = multiagent_powers.get_agent_dashboard()
    assert dash["power_id"] == "PWR-303"
    assert dash["registered_agents_count"] >= 14
    assert "coder" in dash["registered_agents"]


def test_pwr_304_agent_handoff():
    """Validates seamless context-preserving handoff."""
    res = multiagent_powers.handoff_task(
        source_agent="researcher",
        target_agent="content_strategist",
        payload={"research_notes": "Retrieved 5 papers on hybrid retrieval"}
    )
    assert res["power_id"] == "PWR-304"
    assert res["status"] == "HANDOFF_SUCCESS"
    assert res["payload_preserved"] is True


def test_pwr_305_parallel_execution():
    """Validates bounded concurrent execution of multiple agent goals."""
    goals = [
        "Analyze system memory telemetry",
        "Inspect repository git diff",
        "Benchmark SQLite FTS5 index speed"
    ]
    res = multiagent_powers.execute_parallel_swarms(goals)
    assert res["power_id"] == "PWR-305"
    assert res["executed_plans_count"] == 3
    assert all(s == "COMPLETED" for s in res["statuses"])


def test_pwr_306_cost_telemetry():
    """Validates cost tracking across agent runs."""
    cost_info = multiagent_powers.get_cost_telemetry()
    assert cost_info["power_id"] == "PWR-306"
    assert cost_info["cumulative_cost_usd"] >= 0.0


def test_pwr_307_agent_cancellation():
    """Validates token-based cancellation."""
    plan = agent_swarm.decompose_goal("Long running batch data ingestion")
    cancelled = multiagent_powers.cancel_swarm_execution(plan.plan_id, reason="User interrupted")
    assert cancelled["power_id"] == "PWR-307"
    assert cancelled["cancelled"] is True

