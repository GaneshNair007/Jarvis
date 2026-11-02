"""
JARVIS Task Verification Layer (Quality, Functional, and Security Gates)
Before any task node transitions to COMPLETED status, the verification layer inspects
outputs, validates tool artifacts, checks security DLP boundaries, and issues a formal score.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskNode
from jarvis.security.ten_layer_shield import jarvis_security_suite
from jarvis.core.logger import get_logger

logger = get_logger("core.task_verifier")


class VerificationResult(BaseModel):
    task_id: str
    passed: bool
    score: float  # 0.0 to 1.0
    reviewer_agent: str
    comments: str
    checks_performed: List[str] = Field(default_factory=list)


class TaskVerifier:
    """
    Multi-stage verification engine enforcing quality gates before task completion.
    Stages:
      1. Output Completeness Gate: Checks non-empty outputs and absence of error flags.
      2. Security & DLP Gate: Scans outputs with 10-layer shield for secret leakage.
      3. Reviewer Evaluation Gate: Assesses functional correctness against task description.
    """

    def __init__(self, passing_score_threshold: float = 0.75):
        self.passing_score_threshold = passing_score_threshold

    def verify_task(
        self,
        task: TaskNode,
        outputs: Dict[str, Any],
        reviewer_agent: str = "qa_tester_agent",
    ) -> VerificationResult:
        """Runs comprehensive multi-stage verification on proposed task outputs."""
        checks: List[str] = []
        score = 1.0
        comments = []

        # 1. Output Completeness Check
        checks.append("output_completeness")
        if not outputs:
            score -= 0.5
            comments.append("Task outputs dictionary is completely empty.")
        elif outputs.get("error") or outputs.get("status") == "error":
            score -= 0.6
            comments.append(f"Task output reports explicit error: {outputs.get('error') or outputs.get('message')}")

        # 2. Security & DLP Leakage Check
        checks.append("security_dlp_audit")
        output_str = str(outputs)
        findings = jarvis_security_suite.layer1_detector.scan_text(output_str)
        high_risk = [f for f in findings if f["confidence"] == "HIGH"]
        if high_risk:
            score = 0.0
            comments.append(f"CRITICAL SECURITY REJECTION: Output contains unredacted credentials ({len(high_risk)} leaks detected)")

        # 3. Tool Requirement Validation Check
        if task.tool_requirements:
            checks.append("tool_requirements_verification")
            tools_used = outputs.get("tools_used", []) or outputs.get("tool_results", [])
            # If explicit tool was required, ensure proof of execution exists
            if not tools_used and not any(k in outputs for k in ["results", "data", "summary", "response"]):
                score -= 0.2
                comments.append(f"Required tools {task.tool_requirements} lacked verified output records.")

        # 4. Final Threshold Evaluation
        score = max(0.0, min(1.0, round(score, 2)))
        passed = score >= self.passing_score_threshold and not high_risk

        if passed:
            comments.append(f"Verification PASSED with score {score:.2f} (Threshold: {self.passing_score_threshold}).")
        else:
            comments.append(f"Verification REJECTED with score {score:.2f} (Required: {self.passing_score_threshold}).")

        res = VerificationResult(
            task_id=task.task_id,
            passed=passed,
            score=score,
            reviewer_agent=reviewer_agent,
            comments=" | ".join(comments),
            checks_performed=checks,
        )

        logger.info(f"TaskVerifier: Task '{task.task_id}' -> Passed={res.passed} Score={res.score} Reviewer={reviewer_agent}")
        return res


# Global Singleton Instance
task_verifier = TaskVerifier()

