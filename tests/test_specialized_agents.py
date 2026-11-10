"""
Unit Tests for JARVIS Milestone 2: Unified 8 Specialized Agents & Permitted Tool Suites
Tests coverage:
  - BaseSpecialistAgent, AgentTask, AgentContext, AgentResult contracts
  - Tool suites and permission enforcement
  - All 8 specialized agents:
      1. ResearcherAgent
      2. EngineerAgent
      3. AcademicTutorAgent
      4. CareerAgent
      5. ProductivityAgent
      6. CommunicationAgent
      7. DesktopAgent
      8. ReviewerAgent & VerificationReport
  - Dynamic 4-tier desktop application resolution & security filtering
  - Central AgentRegistry discovery & alias resolution
"""

import datetime
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from jarvis.agents.academic_tutor import AcademicTutorAgent, academic_tutor_agent
from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.agents.career_agent import CareerAgent, career_agent
from jarvis.agents.communication_agent import CommunicationAgent, communication_agent
from jarvis.agents.critic import CriticReport, Verdict
from jarvis.agents.desktop_agent import DesktopAgent, desktop_agent
from jarvis.agents.engineer import EngineerAgent, engineer_agent
from jarvis.agents.productivity_agent import ProductivityAgent, productivity_agent
from jarvis.agents.registry import AgentRegistry, agent_registry
from jarvis.agents.researcher import ResearcherAgent, researcher_agent
from jarvis.agents.reviewer_agent import ReviewerAgent, VerificationReport, reviewer_agent
from jarvis.powers.desktop_powers import BLOCKED_SYSTEM_BINARIES, resolve_app_path


# ── Area 1: Base Contracts & Permitted Tools ──────────────────────────────────


class TestBaseContracts:
    def test_agent_task_creation_and_properties(self):
        """AgentTask supports task_id, goal, role alias, and to_dict()."""
        task = AgentTask(goal="Analyze data", assigned_role="researcher", parameters={"key": "val"})
        assert task.task_id.startswith("task_")
        assert task.goal == "Analyze data"
        assert task.role == "researcher"
        assert task.assigned_role == "researcher"
        task.role = "engineer"
        assert task.assigned_role == "engineer"

        d = task.to_dict()
        assert d["goal"] == "Analyze data"
        assert d["role"] == "engineer"
        assert d["parameters"] == {"key": "val"}

    def test_agent_context_properties(self):
        """AgentContext supports history/metadata aliases and serialization."""
        ctx = AgentContext(user_id="ganesh", recent_history=[{"role": "user", "content": "hi"}])
        assert ctx.user_id == "ganesh"
        assert len(ctx.history) == 1
        assert ctx.history[0]["content"] == "hi"

        d = ctx.to_dict()
        assert d["user_id"] == "ganesh"
        assert len(d["history"]) == 1

    def test_agent_result_serialization(self):
        """AgentResult accurately reflects status, evidence, and tools."""
        res = AgentResult(
            task_id="t1",
            agent_name="ResearcherAgent",
            role="researcher",
            status="SUCCESS",
            output="Report text",
            evidence={"sources": ["web"]},
            tools_used=["web_search"],
            duration_ms=12.5,
        )
        d = res.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "SUCCESS"
        assert d["tools_used"] == ["web_search"]
        assert d["duration_ms"] == 12.5

    def test_permitted_tools_validation(self):
        """BaseSpecialistAgent validates permitted tools correctly."""
        class MockAgent(BaseSpecialistAgent):
            name = "MockAgent"
            role = "mock"
            permitted_tools = ["tool_a", "tool_b"]

            async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
                return AgentResult(task_id=task.task_id, agent_name=self.name, role=self.role, status="SUCCESS")

        agent = MockAgent()
        assert agent.validate_tool_permitted("tool_a") is True
        assert agent.validate_tool_permitted("tool_b") is True
        assert agent.validate_tool_permitted("tool_unauthorized") is False
        assert agent.get_status() == "idle"


# ── Area 2: ResearcherAgent ───────────────────────────────────────────────────


class TestResearcherAgentSpecialist:
    def test_researcher_identity_and_tools(self):
        """ResearcherAgent has canonical role and permitted tools."""
        assert researcher_agent.role == "researcher"
        assert researcher_agent.validate_tool_permitted("web_search") is True
        assert researcher_agent.validate_tool_permitted("local_search") is True
        assert researcher_agent.validate_tool_permitted("unauthorized_destructive_tool") is False

    def test_synthesize_findings_empty(self):
        """Synthesize findings with empty results returns truthful message."""
        synth = researcher_agent.synthesize_findings("quantum teleportation", [])
        assert "no relevant information found" in synth.lower()

    def test_synthesize_findings_with_data(self):
        """Synthesize findings with structured data returns summary."""
        findings = [
            {"source": "local_documents", "title": "Quantum Paper", "snippet": "Entangled qubits teleport state.", "relevance_score": 0.9}
        ]
        with patch.object(researcher_agent, "_synthesise", return_value="Quantum summary"):
            synth = researcher_agent.synthesize_findings("quantum", findings)
            assert synth == "Quantum summary"

    @pytest.mark.asyncio
    async def test_researcher_execute_success(self):
        """ResearcherAgent.execute() produces AgentResult with sources."""
        task = AgentTask(goal="State of AI", parameters={"query": "State of AI"})
        ctx = AgentContext()

        with patch.object(researcher_agent, "_search_local", return_value=[]), \
             patch.object(researcher_agent, "_search_documents", return_value=[]), \
             patch.object(researcher_agent, "_search_web", return_value=[]):
            res = await researcher_agent.execute(task, ctx)
            assert res.status == "SUCCESS"
            assert res.role == "researcher"
            assert res.agent_name == "ResearcherAgent"
            assert res.task_id == task.task_id


# ── Area 3: EngineerAgent ─────────────────────────────────────────────────────


class TestEngineerAgentSpecialist:
    def test_engineer_identity_and_tools(self):
        """EngineerAgent has canonical role and permitted tools."""
        assert engineer_agent.role == "engineer"
        assert engineer_agent.validate_tool_permitted("python_sandbox") is True
        assert engineer_agent.validate_tool_permitted("pytest_runner") is True
        assert engineer_agent.validate_tool_permitted("git_status") is True
        assert engineer_agent.validate_tool_permitted("unauthorized_tool") is False

    def test_run_code_success(self):
        """run_code executes valid Python code in sandbox."""
        code = "print('Hello from EngineerAgent')\nx = 2 + 3\nprint(f'Result: {x}')"
        res = engineer_agent.run_code(code)
        assert res["status"] == "SUCCESS"
        assert res["returncode"] == 0
        assert "Result: 5" in res["stdout"]

    def test_run_code_syntax_error(self):
        """run_code pre-validates AST and captures SyntaxError without crash."""
        bad_code = "def broken_func(\n   return 42"
        res = engineer_agent.run_code(bad_code)
        assert res["status"] == "FAILED"
        assert res["returncode"] != 0
        assert "SyntaxError" in res["stderr"]

    def test_git_operations(self):
        """EngineerAgent delegates git operations cleanly."""
        status = engineer_agent.git_status()
        assert isinstance(status, dict)
        assert "clean" in status or "error" in status

        diff = engineer_agent.git_diff()
        assert isinstance(diff, dict)

    @pytest.mark.asyncio
    async def test_engineer_execute_code(self):
        """EngineerAgent.execute() dispatches code execution."""
        task = AgentTask(goal="Compute factorials", parameters={"code": "print(24)"})
        ctx = AgentContext()
        res = await engineer_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert "24" in res.output["stdout"]
        assert "python_sandbox" in res.tools_used


# ── Area 4: AcademicTutorAgent ────────────────────────────────────────────────


class TestAcademicTutorAgentSpecialist:
    def test_tutor_identity_and_tools(self):
        """AcademicTutorAgent has canonical role and permitted tools."""
        assert academic_tutor_agent.role == "academic_tutor"
        assert academic_tutor_agent.validate_tool_permitted("study_explainer") is True
        assert academic_tutor_agent.validate_tool_permitted("assignment_solver") is True
        assert academic_tutor_agent.validate_tool_permitted("viva_generator") is True

    def test_explain_concept_empty_topic(self):
        """explain_concept handles empty topic safely without crashing."""
        res = academic_tutor_agent.explain_concept("")
        assert res["topic"] == ""
        assert "No topic" in res["explanation"]

    def test_explain_concept_valid(self):
        """explain_concept returns structured explanation, analogy, and takeaways."""
        res = academic_tutor_agent.explain_concept("Virtual Memory", subject="Operating Systems")
        assert res["topic"] == "Virtual Memory"
        assert len(res["key_takeaways"]) > 0
        assert len(res["analogy"]) > 0

    def test_generate_viva_questions(self):
        """generate_viva_questions returns requested count of Q&A pairs."""
        viva = academic_tutor_agent.generate_viva_questions("B-Trees", count=3)
        assert len(viva) == 3
        for q in viva:
            assert "question" in q
            assert "expected_answer" in q

    @pytest.mark.asyncio
    async def test_solve_and_humanize_empty(self):
        """solve_and_humanize handles empty input cleanly."""
        res = await academic_tutor_agent.solve_and_humanize("", subject="Math")
        assert res["status"] == "EMPTY_ASSIGNMENT"

    @pytest.mark.asyncio
    async def test_tutor_execute(self):
        """AcademicTutorAgent.execute() dispatches explanation task."""
        task = AgentTask(goal="Explain QuickSort", parameters={"topic": "QuickSort", "subject": "Algorithms"})
        ctx = AgentContext()
        res = await academic_tutor_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert "QuickSort" in res.output["topic"]


# ── Area 5: CareerAgent ───────────────────────────────────────────────────────


class TestCareerAgentSpecialist:
    def test_career_identity_and_tools(self):
        """CareerAgent has canonical role and permitted tools."""
        assert career_agent.role == "career"
        assert career_agent.validate_tool_permitted("gsoc_scout") is True
        assert career_agent.validate_tool_permitted("hackathon_scout") is True

    def test_curated_orgs_exposure(self):
        """curated_orgs property exposes premier GSoC organizations."""
        orgs = career_agent.curated_orgs
        assert len(orgs) >= 5
        org_names = [o.name for o in orgs]
        assert any("Python Software Foundation" in name for name in org_names)

    def test_scout_opportunities_no_mock_data(self):
        """scout_opportunities returns empty list for nonexistent query without mocks."""
        opps = career_agent.scout_opportunities("completely_nonexistent_xyz999_stack")
        assert opps == []

    def test_scout_opportunities_matching(self):
        """scout_opportunities matches genuine starter issues."""
        opps = career_agent.scout_opportunities("sympy")
        assert len(opps) > 0

    def test_generate_pitch(self):
        """generate_pitch creates mentor-aligned pitch for valid issue."""
        pitch = career_agent.generate_pitch("psf_sympy_01")
        assert "pitch_markdown" in pitch or "content" in pitch

    def test_audit_readiness(self):
        """audit_readiness audits candidate portfolio."""
        audit = career_agent.audit_readiness("GaneshNair007")
        assert "overall_gsoc_readiness_score" in audit
        assert audit["overall_gsoc_readiness_score"] > 80

    @pytest.mark.asyncio
    async def test_career_execute(self):
        """CareerAgent.execute() handles gsoc exploration."""
        task = AgentTask(goal="Scout GSoC", parameters={"language": "Python"})
        ctx = AgentContext()
        res = await career_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert len(res.output) > 0


# ── Area 6: ProductivityAgent ─────────────────────────────────────────────────


class TestProductivityAgentSpecialist:
    def test_productivity_identity_and_tools(self):
        """ProductivityAgent has canonical role and permitted tools."""
        assert productivity_agent.role == "productivity"
        assert productivity_agent.validate_tool_permitted("calendar_add_event") is True
        assert productivity_agent.validate_tool_permitted("deadline_tracker") is True

    def test_add_and_read_calendar_event(self, tmp_path):
        """ProductivityAgent adds and reads RFC 5545 .ics events."""
        cal_path = tmp_path / "test_cal.ics"
        now = datetime.datetime.now()
        res = productivity_agent.add_event(
            summary="Milestone Review",
            start_time=now + datetime.timedelta(days=2),
            end_time=now + datetime.timedelta(days=2, hours=1),
            description="Discuss M2 delivery",
            file_path=cal_path,
        )
        assert res["success"] is True

        events = productivity_agent.read_ics_file(file_path=cal_path)
        assert len(events) == 1
        assert "Milestone Review" in events[0]["summary"]

    def test_parse_datetime_malformed(self):
        """_parse_datetime safely handles malformed date strings returning None."""
        dt = productivity_agent._parse_datetime("invalid-date-string-123")
        assert dt is None

    def test_parse_and_schedule(self):
        """parse_and_schedule auto-schedules deadline tasks."""
        sched = productivity_agent.parse_and_schedule("Submit final project report")
        assert sched["status"] == "SCHEDULED"
        assert "start" in sched
        assert "end" in sched


# ── Area 7: CommunicationAgent ────────────────────────────────────────────────


class TestCommunicationAgentSpecialist:
    def test_communication_identity_and_tools(self):
        """CommunicationAgent has canonical role and permitted tools."""
        assert communication_agent.role == "communication"
        assert communication_agent.validate_tool_permitted("email_draft") is True
        assert communication_agent.validate_tool_permitted("email_scan_inbox") is True

    def test_draft_email_creates_eml(self, tmp_path):
        """draft_email creates valid RFC 822 .eml file in target outbox."""
        outbox = tmp_path / "outbox"
        res = communication_agent.draft_email(
            to="supervisor@university.edu",
            subject='Proposal: "AI Kernel Architecture" & Plans',
            body="Dear Professor,\nHere is the updated architectural document.\nRegards,\nGanesh",
            outbox_dir=outbox,
        )
        assert res["status"] in ("drafted", "DRAFT_SAVED")
        eml_file = Path(res.get("file_path") or res.get("eml_path"))
        assert eml_file.exists()
        assert eml_file.suffix == ".eml"

    def test_scan_inbox_truthful_disconnected(self):
        """scan_inbox returns honest DISCONNECTED status without credentials."""
        with patch.dict("os.environ", {"GMAIL_USER": "", "GMAIL_APP_PASSWORD": ""}, clear=False):
            res = communication_agent.scan_inbox()
            assert res["status"] == "DISCONNECTED"
            assert res["connected"] is False
            assert res["opportunities"] == []

    @pytest.mark.asyncio
    async def test_communication_execute(self, tmp_path):
        """CommunicationAgent.execute() dispatches email drafting."""
        task = AgentTask(
            goal="Draft welcome email",
            parameters={"to": "dev@example.com", "subject": "Welcome", "body": "Hello", "outbox_dir": tmp_path},
        )
        ctx = AgentContext()
        res = await communication_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert res.output["status"] in ("drafted", "DRAFT_SAVED")


# ── Area 8: DesktopAgent & Dynamic App Resolution ─────────────────────────────


class TestDesktopAgentSpecialist:
    def test_desktop_identity_and_tools(self):
        """DesktopAgent has canonical role and permitted tools."""
        assert desktop_agent.role == "desktop"
        assert desktop_agent.validate_tool_permitted("app_resolver") is True
        assert desktop_agent.validate_tool_permitted("window_focus") is True
        assert desktop_agent.validate_tool_permitted("screen_capture") is True

    def test_resolve_known_shortcut_notepad(self):
        """Dynamic app resolver resolves built-in shortcuts first."""
        notepad_path = desktop_agent.resolve_app_path("notepad")
        assert notepad_path is not None
        assert "notepad" in str(notepad_path).lower()
        assert notepad_path.exists()

    def test_resolve_cmd_shortcut(self):
        """Dynamic app resolver resolves cmd."""
        cmd_path = desktop_agent.resolve_app_path("cmd")
        assert cmd_path is not None
        assert "cmd" in str(cmd_path).lower()
        assert cmd_path.exists()

    def test_resolve_nonexistent_application_returns_none(self):
        """Nonexistent application returns None cleanly without error."""
        res = desktop_agent.resolve_app_path("completely_nonexistent_binary_xyz123.exe")
        assert res is None

    def test_resolve_blocked_destructive_binaries(self):
        """Destructive binaries are rejected by security policy returning None."""
        for binary in BLOCKED_SYSTEM_BINARIES:
            res = desktop_agent.resolve_app_path(binary)
            assert res is None, f"Binary {binary} should be blocked!"

    def test_pwr_016_active_window(self):
        """pwr_016_get_active_window returns active window details."""
        win = desktop_agent.pwr_016_get_active_window()
        assert isinstance(win, dict)
        assert "title" in win or "window_id" in win or "success" in win

    @pytest.mark.asyncio
    async def test_desktop_execute_resolve(self):
        """DesktopAgent.execute() dispatches app resolution."""
        task = AgentTask(goal="Resolve notepad", parameters={"resolve_app": "notepad"})
        ctx = AgentContext()
        res = await desktop_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert res.output["resolved_path"] is not None


# ── Area 9: ReviewerAgent & VerificationReport ────────────────────────────────


class TestReviewerAgentSpecialist:
    def test_reviewer_identity_and_tools(self):
        """ReviewerAgent has canonical role and permitted tools."""
        assert reviewer_agent.role == "reviewer"
        assert reviewer_agent.validate_tool_permitted("safety_scanner") is True
        assert reviewer_agent.validate_tool_permitted("evidence_verifier") is True

    def test_verify_contract4_clean_results(self):
        """ReviewerAgent.verify() returns PASS on clean execution results."""
        results = [
            AgentResult(
                task_id="t1",
                agent_name="EngineerAgent",
                role="engineer",
                status="SUCCESS",
                output="Unit tests passed (12/12).",
                evidence={"commit": "abc1234"},
                tools_used=["pytest_runner"],
            )
        ]
        report = reviewer_agent.verify(task="Verify unit tests", execution_results=results)
        assert isinstance(report, VerificationReport)
        assert report.verdict == "PASS"
        assert report.score >= 0.7
        assert report.safety_passed is True

    def test_verify_contract4_safety_failure(self):
        """ReviewerAgent.verify() detects secret keys and fails verification."""
        results = [
            AgentResult(
                task_id="t2",
                agent_name="EngineerAgent",
                role="engineer",
                status="SUCCESS",
                output="Configuration exported with api_key: sk-live-secret-12345",
                evidence={},
            )
        ]
        report = reviewer_agent.verify(task="Export config", execution_results=results)
        assert report.verdict == "FAIL"
        assert report.safety_passed is False
        assert any("secret_key" in f for f in report.findings)

    def test_review_backward_compatibility(self):
        """ReviewerAgent.review() produces CriticReport with valid verdict."""
        crit_rep = reviewer_agent.review("Summarize architecture", "Comprehensive architecture summary.", use_llm=False)
        assert isinstance(crit_rep, CriticReport)
        assert crit_rep.verdict in (Verdict.PASS, Verdict.PASS_WITH_WARNINGS, Verdict.RETRY, Verdict.FAIL)

    @pytest.mark.asyncio
    async def test_reviewer_execute(self):
        """ReviewerAgent.execute() dispatches review."""
        task = AgentTask(goal="Audit draft", parameters={"output": "Solid draft text."})
        ctx = AgentContext()
        res = await reviewer_agent.execute(task, ctx)
        assert res.status == "SUCCESS"
        assert "verdict" in res.output


# ── Area 10: AgentRegistry ───────────────────────────────────────────────────


class TestAgentRegistry:
    def test_all_8_agents_registered(self):
        """AgentRegistry auto-registers all 8 specialist agents."""
        canonical_roles = [
            "researcher",
            "engineer",
            "academic_tutor",
            "career",
            "productivity",
            "communication",
            "desktop",
            "reviewer",
        ]
        for role in canonical_roles:
            agent = agent_registry.get_agent(role)
            assert agent is not None, f"Agent for role '{role}' not registered!"
            assert isinstance(agent, BaseSpecialistAgent)

    def test_alias_resolution(self):
        """AgentRegistry resolves standard aliases correctly."""
        assert agent_registry.get_agent("tutor") == academic_tutor_agent
        assert agent_registry.get_agent("coder") == engineer_agent
        assert agent_registry.get_agent("critic") == reviewer_agent
        assert agent_registry.get_agent("verifier") == reviewer_agent
        assert agent_registry.get_agent("email") == communication_agent
        assert agent_registry.get_agent("calendar") == productivity_agent

    def test_nonexistent_agent_returns_none(self):
        """AgentRegistry returns None for unknown agent names."""
        assert agent_registry.get_agent("unknown_agent_role_xyz") is None
        assert agent_registry.get_agent("") is None

    def test_list_agents_and_statuses(self):
        """list_agents and get_all_statuses return complete telemetry."""
        agents = agent_registry.list_agents()
        assert len(agents) >= 8

        statuses = agent_registry.get_all_statuses()
        for role, status in statuses.items():
            assert status in ("idle", "active", "error")
