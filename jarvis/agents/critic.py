"""
JARVIS Critic Agent (PWR-294 / PWR-295)
PDF Spec: Pages 352-371 — Multi-Agent & Orchestration

Reviews execution outputs for:
- Correctness & factual accuracy
- Safety & policy compliance
- Completeness against the original goal
- Quality & coherence

Returns a CriticReport with a pass/fail verdict and a list of specific issues.
If issues are found, the Critic can request a retry via the swarm coordinator.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.critic")


class Verdict(str, Enum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"
    RETRY = "retry"


@dataclass
class CriticIssue:
    severity: str   # info | warning | error | critical
    category: str   # safety | completeness | accuracy | quality | policy
    description: str
    suggestion: str = ""


@dataclass
class CriticReport:
    """Structured critique of an executor's output."""
    report_id: str = field(default_factory=lambda: f"crit_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    goal: str = ""
    verdict: Verdict = Verdict.PASS
    score: float = 1.0        # 0.0 (terrible) → 1.0 (perfect)
    issues: List[CriticIssue] = field(default_factory=list)
    summary: str = ""
    retry_recommended: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "verdict": self.verdict.value,
            "score": self.score,
            "retry_recommended": self.retry_recommended,
            "summary": self.summary,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "duration_ms": self.duration_ms,
        }


class CriticAgent:
    """
    Reviews task outputs against the original goal.

    Evaluation dimensions:
    1. Safety — detects PII, harmful content, policy violations
    2. Completeness — checks if output addresses the goal
    3. Accuracy — heuristic and optional LLM cross-check
    4. Quality — response coherence, structure, length
    """

    # ── Safety patterns ────────────────────────────────────────────────────────
    SAFETY_RED_FLAGS = [
        ("pii_email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ("pii_phone", r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        ("secret_key", r"(?i)(api[_\s-]?key|secret|password|token)\s*[:=]\s*\S+"),
        ("credit_card", r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    ]

    def review(
        self,
        goal: str,
        output: str,
        task_id: str = "",
        action_type: str = "llm",
        use_llm: bool = True,
    ) -> CriticReport:
        """
        Review the output of an executor action.

        Args:
            goal: The original task goal / instruction.
            output: The executor's response / output string.
            task_id: Parent task ID for traceability.
            action_type: Type of action that produced the output.
            use_llm: If True, attempt an LLM-based deep review.

        Returns:
            CriticReport with verdict and issues.
        """
        start = time.time()
        report_id = f"crit_{uuid.uuid4().hex[:8]}"
        task_id = task_id or report_id

        logger.info(f"CriticAgent: reviewing task={task_id} goal='{goal[:60]}'")

        issues: List[CriticIssue] = []

        # ── 1. Safety scan ────────────────────────────────────────────────────
        issues.extend(self._safety_scan(output))

        # ── 2. Completeness check ─────────────────────────────────────────────
        issues.extend(self._completeness_check(goal, output))

        # ── 3. Quality check ──────────────────────────────────────────────────
        issues.extend(self._quality_check(output))

        # ── 4. LLM deep review (optional) ────────────────────────────────────
        if use_llm and output and len(output) > 50:
            llm_issues = self._llm_review(goal, output)
            issues.extend(llm_issues)

        # ── Verdict scoring ───────────────────────────────────────────────────
        verdict, score = self._score(issues)
        retry_recommended = verdict == Verdict.RETRY or any(
            i.severity == "error" for i in issues
        )

        summary = self._build_summary(verdict, issues, score)
        duration_ms = round((time.time() - start) * 1000, 2)

        logger.info(
            f"CriticAgent: report={report_id} verdict={verdict.value} "
            f"score={score:.2f} issues={len(issues)} retry={retry_recommended}"
        )

        return CriticReport(
            report_id=report_id,
            task_id=task_id,
            goal=goal,
            verdict=verdict,
            score=score,
            issues=issues,
            summary=summary,
            retry_recommended=retry_recommended,
            duration_ms=duration_ms,
        )

    # ── Review dimensions ──────────────────────────────────────────────────────

    def _safety_scan(self, output: str) -> List[CriticIssue]:
        import re
        issues = []
        for name, pattern in self.SAFETY_RED_FLAGS:
            if re.search(pattern, output):
                issues.append(CriticIssue(
                    severity="critical",
                    category="safety",
                    description=f"Output may contain sensitive data: {name}",
                    suggestion="Redact or mask sensitive information before returning.",
                ))
        return issues

    def _completeness_check(self, goal: str, output: str) -> List[CriticIssue]:
        issues = []
        if not output or len(output.strip()) < 20:
            issues.append(CriticIssue(
                severity="error",
                category="completeness",
                description="Output is empty or too short to address the goal.",
                suggestion="Retry the task with a more explicit prompt.",
            ))
            return issues

        # Check if key terms from the goal appear in the output
        goal_words = set(w.lower() for w in goal.split() if len(w) > 4)
        output_lower = output.lower()
        missing = [w for w in goal_words if w not in output_lower]

        if len(missing) > len(goal_words) * 0.6 and len(goal_words) > 3:
            issues.append(CriticIssue(
                severity="warning",
                category="completeness",
                description=f"Output may not address key goal terms: {', '.join(list(missing)[:5])}",
                suggestion="Ensure the response directly addresses all aspects of the goal.",
            ))
        return issues

    def _quality_check(self, output: str) -> List[CriticIssue]:
        issues = []
        if len(output) > 10000:
            issues.append(CriticIssue(
                severity="info",
                category="quality",
                description="Output is very long and may need summarisation.",
                suggestion="Consider summarising the output to under 2000 characters.",
            ))
        error_phrases = ["traceback", "error:", "exception:", "syntaxerror", "nameerror"]
        if any(p in output.lower() for p in error_phrases):
            issues.append(CriticIssue(
                severity="error",
                category="quality",
                description="Output contains error traces or exceptions.",
                suggestion="Fix the underlying error and retry.",
            ))
        return issues

    def _llm_review(self, goal: str, output: str) -> List[CriticIssue]:
        """Use the LLM to produce a structured critique."""
        try:
            from jarvis.core.model_router import model_router, RoutingRequest
            prompt = (
                f"You are a strict AI quality reviewer.\n"
                f"Goal: {goal}\n\n"
                f"Output to review:\n{output[:2000]}\n\n"
                "List any issues as: [SEVERITY|CATEGORY] Description. "
                "Severities: info, warning, error, critical. "
                "Categories: safety, completeness, accuracy, quality. "
                "If no issues, write: NO_ISSUES"
            )
            req = RoutingRequest(
                task_id=f"crit_{uuid.uuid4().hex[:6]}",
                user_intent=prompt,
                sensitivity_level="low",
            )
            decision = model_router.route(req)
            result = model_router.execute_inference(decision=decision, prompt=prompt)
            content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(result, dict) else str(result)
            )

            if "NO_ISSUES" in content:
                return []

            issues = []
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("[") and "|" in line and "]" in line:
                    tag = line[1:line.index("]")]
                    parts = tag.split("|")
                    severity = parts[0].strip().lower() if parts else "info"
                    category = parts[1].strip().lower() if len(parts) > 1 else "quality"
                    description = line[line.index("]") + 1:].strip()
                    if description:
                        issues.append(CriticIssue(
                            severity=severity,
                            category=category,
                            description=description,
                        ))
            return issues
        except Exception as exc:
            logger.debug(f"_llm_review failed: {exc}")
            return []

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score(self, issues: List[CriticIssue]) -> tuple[Verdict, float]:
        severity_weights = {"critical": 0.4, "error": 0.25, "warning": 0.1, "info": 0.02}
        total_deduction = sum(severity_weights.get(i.severity, 0) for i in issues)
        score = max(0.0, 1.0 - total_deduction)

        if score >= 0.9:
            return Verdict.PASS, score
        elif score >= 0.7:
            return Verdict.PASS_WITH_WARNINGS, score
        elif score >= 0.4:
            return Verdict.RETRY, score
        else:
            return Verdict.FAIL, score

    def _build_summary(self, verdict: Verdict, issues: List[CriticIssue], score: float) -> str:
        if not issues:
            return f"✅ Output passed all checks (score: {score:.2f})."
        critical = [i for i in issues if i.severity == "critical"]
        errors = [i for i in issues if i.severity == "error"]
        if critical:
            return (
                f"🚨 CRITICAL issues detected (score: {score:.2f}): "
                + "; ".join(i.description for i in critical[:2])
            )
        if errors:
            return (
                f"❌ Errors found (score: {score:.2f}): "
                + "; ".join(i.description for i in errors[:2])
            )
        return (
            f"⚠️ Minor issues (score: {score:.2f}): "
            + "; ".join(i.description for i in issues[:2])
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
critic_agent = CriticAgent()

__all__ = ["CriticAgent", "CriticReport", "CriticIssue", "Verdict", "critic_agent"]
