"""
Unit & API Integration Tests for Reflection Engine, Capabilities, and Backlog
Tests:
  1. ExecutionAnalyzer, GapDetector, OpportunityDetector, ImprovementGenerator, ReflectionScorer
  2. CapabilityRegistry & CapabilityService maturity levels (MISSING, EXPERIMENTAL, BASIC, ADVANCED, ELITE)
  3. FastAPI Endpoints (/api/v1/reflections, /api/v1/capabilities, /api/v1/improvements)
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus
from jarvis.reflection import ReflectionEngine
from jarvis.capabilities.registry import CapabilityRegistry, CapabilityLevel
from jarvis.self_improvement.service import ImprovementService


@pytest.fixture
def api_client():
    return TestClient(app)


class TestReflectionEngineComponents:
    """Tests the 5 reflection engine modules working together."""

    def test_full_reflection_pipeline(self):
        engine = ReflectionEngine()
        graph = TaskGraph(goal_id="goal_test_reflection")

        # Node 1: Completed with opportunity
        t1 = TaskNode(
            task_id="t1",
            name="Scout Hackathon",
            description="Find online hackathons",
            department="hackathon",
            parent_goal="goal_test_reflection",
            status=TaskStatus.COMPLETED,
            tool_requirements=["web_search"],
            outputs={"opportunity": "Publish as open standard AI hackathon harness"},
        )
        t1.metadata["verification"] = {"passed": True}

        # Node 2: Failed due to missing tool
        t2 = TaskNode(
            task_id="t2",
            name="Automate GUI Action",
            description="Run desktop click",
            department="desktop",
            parent_goal="goal_test_reflection",
            status=TaskStatus.FAILED,
            tool_requirements=["unsupported_hardware_probe"],
            retry_count=3,
        )
        t2.metadata["last_error"] = "Execution timeout: unsupported_hardware_probe tool unavailable"

        graph.add_node(t1)
        graph.add_node(t2)

        report = engine.generate_reflection(graph)

        assert report.goal_id == "goal_test_reflection"
        assert report.analysis.total_tasks == 2
        assert report.analysis.completed_tasks == 1
        assert report.analysis.failed_tasks == 1

        # Gap detection
        assert len(report.gaps) >= 1
        assert any(g.gap_type == "MISSING_TOOL" for g in report.gaps)

        # Opportunity detection
        assert len(report.opportunities) >= 1
        assert any("Publish as open standard" in o.description for o in report.opportunities)

        # Improvement proposals generated
        assert len(report.improvement_proposals) >= 1

        # Constitution Score
        assert report.constitution_score.overall_score >= 0.0


class TestCapabilityRegistry:
    """Tests Capability Registry and Level transitions."""

    def test_capability_levels_and_queries(self):
        reg = CapabilityRegistry()
        reg.register_capability(
            name="custom_whisper_voice",
            level=CapabilityLevel.EXPERIMENTAL,
            category="voice",
            description="Local whisper transcription",
            required_tools=["whisper_cli"],
        )

        assert reg.has_capability("custom_whisper_voice", CapabilityLevel.EXPERIMENTAL)
        assert not reg.has_capability("custom_whisper_voice", CapabilityLevel.ADVANCED)

        # Upgrade level
        reg.update_capability("custom_whisper_voice", level=CapabilityLevel.ADVANCED, success_rate=0.99)
        assert reg.has_capability("custom_whisper_voice", CapabilityLevel.ADVANCED)

        # Find missing
        missing = reg.find_missing_capabilities()
        assert any(c.name == "autonomous_self_repair" for c in missing)


class TestReflectionAPIEndpoints:
    """Tests FastAPI reflection and capability endpoints."""

    def test_create_and_get_reflection(self, api_client):
        # 1. Create reflection
        resp = api_client.post(
            "/api/v1/reflections",
            json={"goal_id": "goal_api_test_01", "include_constitution_audit": True},
        )
        assert resp.status_code == 201
        data = resp.json()
        refl_id = data["id"]
        assert data["goal_id"] == "goal_api_test_01"
        assert "constitution_alignment_score" in data

        # 2. Get reflection by ID
        get_resp = api_client.get(f"/api/v1/reflections/{refl_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == refl_id

        # 3. Get reflections for goal
        goal_resp = api_client.get("/api/v1/goals/goal_api_test_01/reflections")
        assert goal_resp.status_code == 200
        assert len(goal_resp.json()) >= 1

    def test_capabilities_and_improvements_endpoints(self, api_client):
        # 1. List capabilities
        caps_resp = api_client.get("/api/v1/capabilities")
        assert caps_resp.status_code == 200
        assert len(caps_resp.json()) >= 1

        # Filter by level
        elite_resp = api_client.get("/api/v1/capabilities?level=ELITE")
        assert elite_resp.status_code == 200
        assert any(c["level"] == "ELITE" for c in elite_resp.json())

        # 2. Create Improvement Request
        imp_resp = api_client.post(
            "/api/v1/reflections/improvements",
            json={
                "title": "Add Kokoro Fast Path",
                "description": "Bypass cloud TTS when RTX 4050 is available",
                "category": "performance",
                "priority": "HIGH",
            },
        )
        assert imp_resp.status_code == 201
        imp_data = imp_resp.json()
        assert imp_data["status"] == "PROPOSED"

        # 3. List Improvements
        list_imp = api_client.get("/api/v1/improvements")
        assert list_imp.status_code == 200
        assert any(i["title"] == "Add Kokoro Fast Path" for i in list_imp.json())
