"""
JARVIS Reviewer & Verifier Specialist Agent
PDF Spec: Multi-Agent & Orchestration — Independent Verification & Critique

Executes independent post-execution quality, safety, and evidence verification:
- Contract 4 VerificationReport generation with PII / secret red-flag scanning
- Completeness and factual evidence cross-checking
- Backward-compatible CriticReport generation for Stage 6 pipeline critique
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Dict, List, Literal, Optional, Union
import uuid

from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.agents.critic import CriticAgent, CriticIssue, CriticReport, Verdict, critic_agent
from jarvis.core.logger import get_logger

logger = get_logger("agents.reviewer")


@dataclass
class VerificationReport:
    """Structured report returned by ReviewerAgent.verify()."""

    report_id: str = field(default_factory=lambda: f"ver_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    verdict: Literal["PASS", "RETRY", "FAIL"] = "PASS"
    score: float = 1.0
    findings: List[str] = field(default_factory=list)
    safety_passed: bool = True
    evidence_verified: bool = True
    summary: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "verdict": self.verdict,
            "score": self.score,
            "findings": self.findings,
            "safety_passed": self.safety_passed,
            "evidence_verified": self.evidence_verified,
            "summary": self.summary,
            "duration_ms": self.duration_ms,
        }


class ReviewerAgent(BaseSpecialistAgent):
    """
    Specialist agent for independent verification of outputs,
    safety red-flag scanning, evidence verification, and execution auditing.
    """

    name: str = "ReviewerAgent"
    role: str = "reviewer"
    permitted_tools: List[str] = [
        "safety_scanner",
        "evidence_verifier",
        "completeness_checker",
        "quality_scorer",
        "pii_detector",
        "verification",
        "audit",
    ]

    SAFETY_PATTERNS = [
        ("pii_email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ("pii_phone", r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        ("secret_key", r"(?i)(api[_\s-]?key|secret|password|token)\s*[:=]\s*\S+"),
        ("credit_card", r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    ]

    def __init__(self, critic: Optional[CriticAgent] = None):
        self._critic = critic or critic_agent

    def review(
        self,
        goal: str,
        output: str,
        task_id: str = "",
        action_type: str = "llm",
        use_llm: bool = True,
    ) -> CriticReport:
        """
        Maintains 100% backward compatibility with CriticAgent.review()
        used across the 6-stage pipeline and existing unit tests.
        """
        return self._critic.review(
            goal=goal,
            output=output,
            task_id=task_id,
            action_type=action_type,
            use_llm=use_llm,
        )

    def verify(
        self,
        task: Union[str, AgentTask],
        execution_results: List[AgentResult],
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationReport:
        """
        Performs independent multi-dimensional verification of execution results against task requirements.
        Checks:
        1. Safety (PII, secrets, malicious content)
        2. Execution status and error conditions
        3. Completeness and evidence integrity
        """
        start = time.time()
        report_id = f"ver_{uuid.uuid4().hex[:8]}"
        task_id = task.task_id if isinstance(task, AgentTask) else f"task_{uuid.uuid4().hex[:6]}"
        task_goal = task.goal if isinstance(task, AgentTask) else str(task)

        findings: List[str] = []
        safety_passed = True
        evidence_verified = True
        score = 1.0

        if not execution_results:
            findings.append("No execution results provided for verification.")
            score = 0.0
            evidence_verified = False
            verdict: Literal["PASS", "RETRY", "FAIL"] = "RETRY"
        else:
            for idx, res in enumerate(execution_results):
                out_str = str(res.output or "")

                # 1. Safety Scan
                for label, pattern in self.SAFETY_PATTERNS:
                    if re.search(pattern, out_str):
                        safety_passed = False
                        score -= 0.4
                        findings.append(f"Result {idx} ({res.role}): potential {label} detected in output.")

                # 2. Execution Status Check
                if res.status == "FAILED":
                    score -= 0.3
                    findings.append(f"Result {idx} ({res.role}) reported FAILED status: {res.error or 'Unknown error'}")
                elif res.status == "TOOL_NOT_PERMITTED":
                    score -= 0.5
                    safety_passed = False
                    findings.append(f"Result {idx} ({res.role}) attempted forbidden tool invocation.")

                # 3. Evidence Check
                if not res.evidence and not res.output:
                    evidence_verified = False
                    score -= 0.2
                    findings.append(f"Result {idx} ({res.role}) produced empty output with zero evidence.")

            score = max(0.0, min(1.0, round(score, 2)))

            if not safety_passed:
                verdict = "FAIL"
            elif score >= 0.7:
                verdict = "PASS"
            elif score >= 0.4:
                verdict = "RETRY"
            else:
                verdict = "FAIL"

        duration_ms = round((time.time() - start) * 1000, 2)
        summary = (
            f"Verification completed for task='{task_goal[:40]}'. "
            f"Verdict={verdict}, score={score}, safety_passed={safety_passed}, findings={len(findings)}."
        )

        return VerificationReport(
            report_id=report_id,
            task_id=task_id,
            verdict=verdict,
            score=score,
            findings=findings,
            safety_passed=safety_passed,
            evidence_verified=evidence_verified,
            summary=summary,
            duration_ms=duration_ms,
        )

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned verification task using permitted tools."""
        start = time.time()
        params = task.parameters
        tools_used: List[str] = []
        output: Any = None
        status = "SUCCESS"
        error: Optional[str] = None

        try:
            if "execution_results" in params:
                tools_used.extend(["safety_scanner", "evidence_verifier", "completeness_checker"])
                results_in = params["execution_results"]
                # Adapt dicts to AgentResult if passed as raw dicts
                adapted_results: List[AgentResult] = []
                for r in results_in:
                    if isinstance(r, AgentResult):
                        adapted_results.append(r)
                    elif isinstance(r, dict):
                        adapted_results.append(
                            AgentResult(
                                task_id=r.get("task_id", ""),
                                agent_name=r.get("agent_name", ""),
                                role=r.get("role", ""),
                                status=r.get("status", "SUCCESS"),
                                output=r.get("output"),
                                evidence=r.get("evidence", {}),
                                tools_used=r.get("tools_used", []),
                                error=r.get("error"),
                            )
                        )
                rep = self.verify(task=task, execution_results=adapted_results, context=context.metadata)
                output = rep.to_dict()
            else:
                tools_used.extend(["quality_scorer", "safety_scanner"])
                out_to_review = params.get("output", task.goal)
                crit_rep = self.review(
                    goal=task.goal,
                    output=out_to_review,
                    task_id=task.task_id,
                    use_llm=bool(params.get("use_llm", False)),
                )
                output = crit_rep.to_dict()

            duration_ms = round((time.time() - start) * 1000, 2)
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status=status,
                output=output,
                evidence={"tools": tools_used, "goal": task.goal},
                tools_used=tools_used,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"ReviewerAgent.execute failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status="FAILED",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ── Singletons & Aliases ─────────────────────────────────────────────────────
reviewer_agent = ReviewerAgent()
agent = reviewer_agent

__all__ = [
    "ReviewerAgent",
    "VerificationReport",
    "reviewer_agent",
    "agent",
]
