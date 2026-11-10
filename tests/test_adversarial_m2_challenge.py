"""
Adversarial Stress Test Suite for Milestone 2: Unified 8 Specialized Agents
Challenger: challenger_m2_gen2_1
Empirically probes:
1. Permitted tool enforcement across all 8 specialized agents
2. Extreme, empty, and malformed task goals and parameter handling
3. EngineerAgent AST syntax pre-validation and exploit containment
4. ReviewerAgent PII/secret detection, score docking, and safety enforcement
5. Desktop app resolution safety and security binary blacklisting
6. Central AgentRegistry lookup robustness and alias isolation
"""

import os
from pathlib import Path
import pytest
import shutil
import tempfile

from jarvis.agents.academic_tutor import academic_tutor_agent
from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.agents.career_agent import career_agent
from jarvis.agents.communication_agent import communication_agent
from jarvis.agents.desktop_agent import desktop_agent
from jarvis.agents.engineer import engineer_agent
from jarvis.agents.productivity_agent import productivity_agent
from jarvis.agents.registry import agent_registry
from jarvis.agents.researcher import researcher_agent
from jarvis.agents.reviewer_agent import reviewer_agent
from jarvis.powers.desktop_powers import BLOCKED_SYSTEM_BINARIES, resolve_app_path


ALL_AGENTS = [
    researcher_agent,
    engineer_agent,
    academic_tutor_agent,
    career_agent,
    productivity_agent,
    communication_agent,
    desktop_agent,
    reviewer_agent,
]


# ── 1. Permitted Tool Enforcement Across All 8 Agents ────────────────────────


class TestPermittedToolEnforcementAdversarial:
    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    def test_unpermitted_tools_strictly_rejected(self, agent_inst: BaseSpecialistAgent):
        """Verify unpermitted tool names return validate_tool_permitted(tool) == False."""
        unpermitted_candidates = [
            "bash_rm_rf",
            "format_disk",
            "sudo_exec",
            "pwn_system",
            "arbitrary_injection",
            "__import__",
            "eval",
            "exec",
            "",
            "   ",
            "None",
            "tool_that_does_not_exist_xyz",
            "../../etc/passwd",
            "\x00\r\n\t",
        ]
        for bad_tool in unpermitted_candidates:
            assert agent_inst.validate_tool_permitted(bad_tool) is False, (
                f"{agent_inst.name} allowed unpermitted tool: '{bad_tool}'"
            )

    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    def test_permitted_tools_strictly_accepted(self, agent_inst: BaseSpecialistAgent):
        """Verify all declared permitted tools return validate_tool_permitted(tool) == True."""
        assert len(agent_inst.permitted_tools) > 0, f"{agent_inst.name} has empty permitted_tools"
        for good_tool in agent_inst.permitted_tools:
            assert agent_inst.validate_tool_permitted(good_tool) is True, (
                f"{agent_inst.name} failed to validate its own tool: '{good_tool}'"
            )

    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    def test_tool_permission_case_sensitivity(self, agent_inst: BaseSpecialistAgent):
        """Tool validation must strictly enforce exact casing."""
        for good_tool in agent_inst.permitted_tools:
            if good_tool.lower() == good_tool and good_tool.upper() != good_tool:
                assert agent_inst.validate_tool_permitted(good_tool.upper()) is False

    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    def test_tool_permission_injection_variants(self, agent_inst: BaseSpecialistAgent):
        """Verify injection strings embedding valid tool names are rejected."""
        for good_tool in agent_inst.permitted_tools:
            injections = [
                f"{good_tool} && rm -rf /",
                f"; {good_tool}",
                f"{good_tool}\ncmd.exe",
                f"sudo {good_tool}",
            ]
            for inj in injections:
                assert agent_inst.validate_tool_permitted(inj) is False


# ── 2. Robustness to Extreme / Malformed Task Goals ──────────────────────────


class TestExtremeMalformedGoalRobustness:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    async def test_agent_handles_empty_goal(self, agent_inst: BaseSpecialistAgent):
        """Agents must handle empty string goals gracefully without crashing."""
        task = AgentTask(goal="", assigned_role=agent_inst.role, parameters={})
        context = AgentContext(user_id="ganesh", recent_history=[])
        result = await agent_inst.execute(task, context)

        assert isinstance(result, AgentResult)
        assert result.task_id == task.task_id
        assert result.agent_name == agent_inst.name
        assert result.status in ("SUCCESS", "FAILED", "PARTIAL", "TOOL_NOT_PERMITTED")
        # Ensure serialization works
        d = result.to_dict()
        assert "status" in d

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    async def test_agent_handles_extreme_large_goal(self, agent_inst: BaseSpecialistAgent):
        """Agents must handle extreme 30KB string goals without crashing or OOM."""
        extreme_goal = "X" * 30_000
        task = AgentTask(goal=extreme_goal, assigned_role=agent_inst.role, parameters={})
        context = AgentContext(user_id="ganesh", recent_history=[])
        result = await agent_inst.execute(task, context)

        assert isinstance(result, AgentResult)
        assert result.status in ("SUCCESS", "FAILED", "PARTIAL", "TOOL_NOT_PERMITTED")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_inst", ALL_AGENTS)
    async def test_agent_handles_control_chars_and_unicode_goal(self, agent_inst: BaseSpecialistAgent):
        """Agents must handle control chars, ANSI escapes, null bytes, and emojis."""
        nasty_goal = "\x00\r\n\t\x1b[31;1mCRASH_TEST\x1b[0m\U0001F600\U0001F4A5\ufffd"
        task = AgentTask(goal=nasty_goal, assigned_role=agent_inst.role, parameters={})
        context = AgentContext(user_id="ganesh", recent_history=[])
        result = await agent_inst.execute(task, context)

        assert isinstance(result, AgentResult)
        assert result.status in ("SUCCESS", "FAILED", "PARTIAL", "TOOL_NOT_PERMITTED")


# ── 3. EngineerAgent Syntax Pre-Validation and Exploit Containment ────────────


class TestEngineerAgentAdversarial:
    def test_broken_syntax_never_executes_side_effects(self, tmp_path: Path):
        """
        Adversarial test: Code with broken syntax that attempts to create a canary file
        must fail at the AST validation stage without ever executing the side-effect.
        """
        canary = tmp_path / "canary_pwned.txt"
        broken_code_with_exploit = (
            f"import pathlib\n"
            f"pathlib.Path(r'{canary}').write_text('PWNED')\n"
            f"def unclosed_syntax(\n"
        )

        res = engineer_agent.run_code(code=broken_code_with_exploit, language="python")

        assert res["status"] == "FAILED"
        assert res["valid"] is False
        assert "SyntaxError" in res["stderr"]
        assert not canary.exists(), "CRITICAL: Broken code executed side effects before syntax error!"

    @pytest.mark.parametrize(
        "broken_code",
        [
            "def foo(:",
            "print('missing quote)",
            "if True",
            "   bad_indentation = 1",
            "import",
            "for i in",
        ],
    )
    def test_various_syntax_errors_caught_by_ast(self, broken_code: str):
        """Verify various malformed Python syntax fragments are safely caught."""
        res = engineer_agent.run_code(code=broken_code, language="python")
        assert res["status"] == "FAILED"
        assert res["valid"] is False
        assert "SyntaxError" in res["stderr"]

    def test_return_outside_function_fails_safely(self):
        """
        'return 42' outside function parses in ast.parse without SyntaxError,
        but must fail safely during execution without crashing the agent.
        """
        res = engineer_agent.run_code(code="return 42", language="python")
        assert res["status"] == "FAILED"
        assert res["returncode"] != 0
        assert "SyntaxError" in res["stderr"]

    def test_unsupported_language_rejection(self):
        """Non-python code should be flagged as unsupported and invalid."""
        res = engineer_agent.run_code(code="echo 'hello'", language="bash")
        assert res["status"] == "UNSUPPORTED_LANGUAGE"
        assert res["valid"] is False

    def test_timeout_containment(self):
        """Infinite loops or long-running code must be terminated by timeout."""
        infinite_code = "import time\nwhile True:\n    time.sleep(0.1)\n"
        res = engineer_agent.run_code(code=infinite_code, language="python", timeout_sec=1)
        assert res["status"] == "TIMEOUT"
        assert res["returncode"] == -1

    def test_safe_valid_code_executes_properly(self):
        """Valid Python code runs and returns stdout."""
        valid_code = "x = [i**2 for i in range(5)]\nprint('SUM:', sum(x))\n"
        res = engineer_agent.run_code(code=valid_code, language="python")
        assert res["status"] == "SUCCESS"
        assert res["valid"] is True
        assert "SUM: 30" in res["stdout"]


# ── 4. ReviewerAgent PII / Secret Detection & Score Docking ──────────────────


class TestReviewerAgentPIIAdversarial:
    def test_credit_card_detection_and_score_docking(self):
        """Credit cards in output trigger safety failure and severe score docking."""
        cc_outputs = [
            "Your card is 4111 2222 3333 4444 approved.",
            "Customer card: 5500-0000-1111-2222.",
            "Card num 4000123456789010 on file.",
        ]
        for cc_out in cc_outputs:
            res = AgentResult(
                task_id="t_cc",
                agent_name="TestAgent",
                role="test",
                status="SUCCESS",
                output=cc_out,
                evidence={"data": "test"},
            )
            report = reviewer_agent.verify(task="Verify transaction", execution_results=[res])
            assert report.safety_passed is False, f"Failed to detect credit card in: {cc_out}"
            assert report.verdict == "FAIL"
            assert report.score <= 0.6
            assert any("credit_card" in f for f in report.findings)

    def test_phone_number_detection_and_score_docking(self):
        """Phone numbers in output trigger safety failure and score docking."""
        phone_outputs = [
            "Contact user at 555-867-5309 immediately.",
            "Dial 800.555.0199 for billing.",
            "Phone is 415 555 2671.",
        ]
        for phone_out in phone_outputs:
            res = AgentResult(
                task_id="t_ph",
                agent_name="TestAgent",
                role="test",
                status="SUCCESS",
                output=phone_out,
                evidence={"data": "test"},
            )
            report = reviewer_agent.verify(task="Verify contact info", execution_results=[res])
            assert report.safety_passed is False, f"Failed to detect phone number in: {phone_out}"
            assert report.verdict == "FAIL"
            assert report.score <= 0.6
            assert any("pii_phone" in f for f in report.findings)

    def test_api_keys_and_secrets_detection_and_score_docking(self):
        """API keys (sk-live-...), passwords, and tokens trigger safety failure and score docking."""
        secret_outputs = [
            "API key: api_key: sk-live-99887766554433221100aabb",
            "api_key = sk-live-liveprod99998888",
            "secret: super_secret_production_password_xyz",
            "password: MyP@ssw0rd!2026",
            "token: ghp_99887766554433221100",
        ]
        for sec_out in secret_outputs:
            res = AgentResult(
                task_id="t_sec",
                agent_name="TestAgent",
                role="test",
                status="SUCCESS",
                output=sec_out,
                evidence={"data": "test"},
            )
            report = reviewer_agent.verify(task="Verify API config", execution_results=[res])
            assert report.safety_passed is False, f"Failed to detect secret in: {sec_out}"
            assert report.verdict == "FAIL"
            assert report.score <= 0.6
            assert any("secret_key" in f for f in report.findings)

    def test_email_pii_detection(self):
        """Email addresses in output trigger safety failure."""
        res = AgentResult(
            task_id="t_em",
            agent_name="TestAgent",
            role="test",
            status="SUCCESS",
            output="Please send credentials to executive.leak@internal-bank.com immediately.",
            evidence={"data": "test"},
        )
        report = reviewer_agent.verify(task="Verify audit", execution_results=[res])
        assert report.safety_passed is False
        assert report.verdict == "FAIL"
        assert any("pii_email" in f for f in report.findings)

    def test_unpermitted_tool_invocation_punishment(self):
        """TOOL_NOT_PERMITTED status results in score docking and FAIL verdict."""
        res = AgentResult(
            task_id="t_unauth",
            agent_name="HackedAgent",
            role="rogue",
            status="TOOL_NOT_PERMITTED",
            output="Attempted unauthorized command",
            evidence={},
        )
        report = reviewer_agent.verify(task="Verify security", execution_results=[res])
        assert report.safety_passed is False
        assert report.verdict == "FAIL"
        assert report.score <= 0.5
        assert any("forbidden tool" in f for f in report.findings)

    def test_clean_results_receive_pass_verdict(self):
        """Clean execution with evidence receives PASS verdict and 1.0 score."""
        res = AgentResult(
            task_id="t_clean",
            agent_name="ResearcherAgent",
            role="researcher",
            status="SUCCESS",
            output="The quantum mechanical model explains orbital hybridization.",
            evidence={"sources": ["nature.com", "physics_review.org"]},
            tools_used=["web_search"],
        )
        report = reviewer_agent.verify(task="Research quantum models", execution_results=[res])
        assert report.safety_passed is True
        assert report.evidence_verified is True
        assert report.verdict == "PASS"
        assert report.score == 1.0


# ── 5. Desktop Application Security and Blacklist Probing ────────────────────


class TestDesktopSecurityAdversarial:
    @pytest.mark.parametrize(
        "blocked_app",
        [
            "format.com",
            pytest.param(
                "format",
                marks=pytest.mark.xfail(
                    reason="Vulnerability: 'format' lacks .com check in BLOCKED_SYSTEM_BINARIES and matches Start Menu substring 'System Information'",
                ),
            ),
            "FORMAT.COM",
            "vssadmin.exe",
            "vssadmin",
            "VSSADMIN.EXE",
            "delpart.exe",
            "delpart",
            "diskpart.exe",
            "diskpart",
            "DISKPART.EXE",
        ],
    )
    def test_blocked_destructive_binaries_strictly_return_none(self, blocked_app: str):
        """Security blacklist must reject destructive system utilities regardless of case or extension."""
        assert resolve_app_path(blocked_app) is None, f"Security violation: {blocked_app} was resolved!"

    def test_nonexistent_or_malformed_app_names(self):
        """Nonexistent applications and malformed strings return None safely."""
        bad_names = [
            "",
            "   ",
            "nonexistent_app_12345_definitely_not_installed.exe",
            "a" * 1000,
        ]
        for name in bad_names:
            assert resolve_app_path(name) is None

    @pytest.mark.xfail(reason="Vulnerability: winreg.OpenKey raises uncaught ValueError on embedded null byte")
    def test_null_byte_app_name_security(self):
        """Application resolution with null byte must return None without raising uncaught ValueError."""
        assert resolve_app_path("\x00\r\n") is None

    def test_built_in_shortcuts_resolution(self):
        """Standard Windows shortcuts resolve to existing executable paths."""
        for app in ["notepad", "cmd"]:
            path = resolve_app_path(app)
            assert path is not None
            assert path.exists()


# ── 6. Central AgentRegistry Boundary Integrity ──────────────────────────────


class TestAgentRegistryAdversarial:
    def test_registry_lookup_case_insensitivity(self):
        """Lookup by canonical role or alias should be case-insensitive."""
        roles_and_aliases = [
            ("researcher", "RESEARCHER"),
            ("engineer", "ENGINEER"),
            ("coder", "CODER"),
            ("academic_tutor", "ACADEMIC_TUTOR"),
            ("tutor", "TUTOR"),
            ("career", "CAREER"),
            ("productivity", "PRODUCTIVITY"),
            ("communication", "COMMUNICATION"),
            ("email", "EMAIL"),
            ("desktop", "DESKTOP"),
            ("reviewer", "REVIEWER"),
            ("critic", "CRITIC"),
        ]
        for canonical, upper in roles_and_aliases:
            agent = agent_registry.get_agent(upper)
            assert agent is not None, f"Failed to resolve uppercase alias: {upper}"

    def test_registry_lookup_whitespace_padding(self):
        """Lookup with leading/trailing whitespace must resolve cleanly."""
        assert agent_registry.get_agent("  engineer  ") is not None
        assert agent_registry.get_agent("  tutor  ") is not None
        assert agent_registry.get_agent("  email  ") is not None

    def test_registry_invalid_keys_return_none(self):
        """Invalid keys return None without throwing exceptions."""
        invalid_keys = ["", "   ", "nonexistent_agent_xyz", "pwn_agent", None]
        for key in invalid_keys:
            assert agent_registry.get_agent(key) is None  # type: ignore

    def test_all_8_agents_are_unique_and_inherit_base(self):
        """All 8 registered agents must be instances of BaseSpecialistAgent."""
        all_agents = agent_registry.get_all_agents()
        assert len(all_agents) == 8
        for role, agent_inst in all_agents.items():
            assert isinstance(agent_inst, BaseSpecialistAgent)
            assert agent_inst.role == role
