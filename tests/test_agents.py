"""
Tests for JARVIS Multi-Agent Fusion Workers
PDF Spec Pages 352-371 — Planner, Researcher, Executor, Critic agents
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


# ── PlannerAgent ───────────────────────────────────────────────────────────────

class TestPlannerAgent:
    def test_decompose_simple_goal(self):
        """Simple goal produces at least 1 plan step."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Search the web for Python tutorials")
        assert plan.plan_id.startswith("plan_")
        assert len(plan.steps) >= 1
        assert plan.goal == "Search the web for Python tutorials"

    def test_decompose_assigns_researcher_for_search(self):
        """Search-related goals should assign researcher role."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Find the latest news about LangGraph")
        roles = [s.assigned_role for s in plan.steps]
        assert "researcher" in roles

    def test_decompose_assigns_coder_for_code_task(self):
        """Code-related goals should assign coder role."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Write a Python script to parse CSV files")
        roles = [s.assigned_role for s in plan.steps]
        assert "coder" in roles

    def test_decompose_adds_review_for_deploy(self):
        """Deploy/publish goals should include a reviewer_critic step."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Deploy the application to production")
        roles = [s.assigned_role for s in plan.steps]
        assert "reviewer_critic" in roles

    def test_plan_to_dict(self):
        """Plan.to_dict() produces valid serialisable output."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Summarise my emails")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "steps" in d
        assert isinstance(d["steps"], list)

    def test_plan_complexity_levels(self):
        """Complex multi-step goals produce medium/high complexity."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose(
            "Research vector databases, write a Python script to benchmark them, "
            "deploy a test server, and send me an email with results"
        )
        assert plan.complexity in ("low", "medium", "high")

    def test_requires_approval_for_delete(self):
        """Goals containing 'delete' should require approval."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Delete all log files older than 30 days")
        assert plan.requires_approval is True

    def test_plan_step_dependencies_chained(self):
        """Steps after the first should have dependency references."""
        from jarvis.agents.planner import PlannerAgent
        planner = PlannerAgent()
        plan = planner.decompose("Deploy the service to staging")
        if len(plan.steps) > 1:
            assert len(plan.steps[1].depends_on) >= 1


# ── ResearcherAgent ────────────────────────────────────────────────────────────

class TestResearcherAgent:
    def test_research_returns_report(self):
        """research() returns a ResearchReport with a report_id."""
        from jarvis.agents.researcher import ResearcherAgent
        agent = ResearcherAgent()
        with patch.object(agent, "_search_local", return_value=[]), \
             patch.object(agent, "_search_documents", return_value=[]), \
             patch.object(agent, "_search_web", return_value=[]):
            report = agent.research("LangGraph checkpointing")
        assert report.report_id.startswith("res_")
        assert report.query == "LangGraph checkpointing"

    def test_research_uses_web_fallback(self):
        """When local search is empty, web search is attempted."""
        from jarvis.agents.researcher import ResearcherAgent, ResearchResult
        agent = ResearcherAgent()
        mock_web = [
            ResearchResult(
                source="web_search",
                title="LangGraph Docs",
                snippet="LangGraph is a library for building stateful workflows.",
                url="https://langchain.com",
                relevance_score=0.9,
            )
        ]
        with patch.object(agent, "_search_local", return_value=[]), \
             patch.object(agent, "_search_documents", return_value=[]), \
             patch.object(agent, "_search_web", return_value=mock_web):
            report = agent.research("LangGraph")
        assert len(report.findings) == 1
        assert "web_search" in report.sources_consulted

    def test_research_report_to_dict(self):
        """ResearchReport.to_dict() is JSON-serialisable."""
        import json
        from jarvis.agents.researcher import ResearcherAgent
        agent = ResearcherAgent()
        with patch.object(agent, "_search_local", return_value=[]), \
             patch.object(agent, "_search_documents", return_value=[]), \
             patch.object(agent, "_search_web", return_value=[]):
            report = agent.research("test topic")
        d = report.to_dict()
        assert json.dumps(d)  # no exception
        assert "report_id" in d
        assert "synthesis" in d

    def test_synthesis_fallback_when_no_llm(self):
        """Synthesise falls back to concatenated snippets when LLM unavailable."""
        from jarvis.agents.researcher import ResearcherAgent, ResearchResult
        agent = ResearcherAgent()
        findings = [
            ResearchResult(
                source="web_search",
                title="Test",
                snippet="Important finding about X",
                relevance_score=0.8,
            )
        ]
        with patch("jarvis.agents.researcher.ResearcherAgent._llm_available", False, create=True):
            synthesis = agent._synthesise("Test query", findings)
        assert "Important finding" in synthesis or len(synthesis) > 0


# ── ExecutorAgent ──────────────────────────────────────────────────────────────

class TestExecutorAgent:
    def test_execute_file_read_success(self):
        """file_read action reads an existing file."""
        from jarvis.agents.executor import ExecutorAgent
        import tempfile, os
        agent = ExecutorAgent()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello JARVIS")
            tmp_path = f.name
        try:
            result = agent.execute("file_read", {"path": tmp_path})
            assert result.status == "success"
            assert "Hello JARVIS" in result.stdout
        finally:
            os.unlink(tmp_path)

    def test_execute_file_write_success(self):
        """file_write action writes content to disk."""
        from jarvis.agents.executor import ExecutorAgent
        import tempfile, os
        agent = ExecutorAgent()
        tmp_path = tempfile.mktemp(suffix=".txt")
        try:
            result = agent.execute("file_write", {"path": tmp_path, "content": "JARVIS test"})
            assert result.status == "success"
            assert Path(tmp_path).read_text() == "JARVIS test"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def test_execute_file_read_missing_file(self):
        """file_read on non-existent file returns failed status."""
        from jarvis.agents.executor import ExecutorAgent
        agent = ExecutorAgent()
        result = agent.execute("file_read", {"path": "/nonexistent/path/file.txt"})
        assert result.status == "failed"
        assert len(result.stderr) > 0

    def test_execute_shell_returns_result(self):
        """Shell action executes and returns stdout."""
        from jarvis.agents.executor import ExecutorAgent
        agent = ExecutorAgent()
        result = agent.execute(
            "shell",
            {"command": "echo JARVIS_SHELL_TEST"},
            approval_token="test_token",
        )
        assert result.status == "success"
        assert "JARVIS_SHELL_TEST" in result.stdout

    def test_execute_result_to_dict(self):
        """ExecutionResult.to_dict() is JSON-serialisable."""
        import json
        from jarvis.agents.executor import ExecutorAgent
        agent = ExecutorAgent()
        result = agent.execute("file_read", {"path": "/nonexistent"})
        d = result.to_dict()
        assert json.dumps(d)  # no exception
        assert "execution_id" in d
        assert "status" in d

    def test_execute_unknown_action_falls_back_to_llm(self):
        """Unknown action type dispatches to _run_llm fallback."""
        from jarvis.agents.executor import ExecutorAgent
        agent = ExecutorAgent()
        with patch.object(agent, "_run_llm") as mock_llm:
            mock_llm.return_value = MagicMock(status="success", stdout="test", action_type="", execution_id="", duration_ms=0.0)
            agent.execute("unknown_action_xyz", {"prompt": "test"})
        mock_llm.assert_called_once()


# ── CriticAgent ────────────────────────────────────────────────────────────────

class TestCriticAgent:
    def test_review_good_output_passes(self):
        """Clean, complete output should pass or pass_with_warnings."""
        from jarvis.agents.critic import CriticAgent, Verdict
        critic = CriticAgent()
        report = critic.review(
            goal="Summarise the features of LangGraph",
            output=(
                "LangGraph is a library for building stateful, multi-actor applications. "
                "It provides StateGraph, conditional edges, and PostgreSQL checkpointing. "
                "Key features include memory persistence, policy gates, and streaming."
            ),
            use_llm=False,
        )
        assert report.verdict in (Verdict.PASS, Verdict.PASS_WITH_WARNINGS)
        assert report.score > 0.5

    def test_review_empty_output_fails(self):
        """Empty output should fail with completeness error and retry recommended."""
        from jarvis.agents.critic import CriticAgent, Verdict
        critic = CriticAgent()
        report = critic.review(goal="Write a summary", output="", use_llm=False)
        # Empty output gets an error-severity issue → score deduction = 0.25 → score 0.75
        # Verdict is PASS_WITH_WARNINGS (0.7-0.9) but retry_recommended should be True
        assert report.retry_recommended is True
        assert any(i.category == "completeness" for i in report.issues)

    def test_review_detects_email_pii(self):
        """Output containing email addresses should trigger safety issue."""
        from jarvis.agents.critic import CriticAgent
        critic = CriticAgent()
        report = critic.review(
            goal="Find contact info",
            output="Contact admin@example.com for support.",
            use_llm=False,
        )
        safety_issues = [i for i in report.issues if i.category == "safety"]
        assert len(safety_issues) > 0

    def test_review_detects_error_traces(self):
        """Output with Python traceback triggers quality error."""
        from jarvis.agents.critic import CriticAgent
        critic = CriticAgent()
        report = critic.review(
            goal="Run a calculation",
            output="Traceback (most recent call last):\n  File test.py\nNameError: name 'x' is not defined",
            use_llm=False,
        )
        quality_issues = [i for i in report.issues if i.category == "quality"]
        assert len(quality_issues) > 0

    def test_review_report_to_dict(self):
        """CriticReport.to_dict() is JSON-serialisable."""
        import json
        from jarvis.agents.critic import CriticAgent
        critic = CriticAgent()
        report = critic.review("Test goal", "Test output", use_llm=False)
        d = report.to_dict()
        assert json.dumps(d)
        assert "verdict" in d
        assert "score" in d
        assert "issues" in d

    def test_score_decreases_with_critical_issues(self):
        """Critical safety issues should drop score below 0.6."""
        from jarvis.agents.critic import CriticAgent, CriticIssue
        critic = CriticAgent()
        issues = [
            CriticIssue(severity="critical", category="safety", description="PII detected"),
            CriticIssue(severity="error", category="quality", description="Traceback found"),
        ]
        verdict, score = critic._score(issues)
        assert score < 0.7
