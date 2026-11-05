"""
JARVIS Reflection Engine - Constitution & Quality Scorer
Compares real execution metrics and artifacts against the Constitution daily.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List
import yaml
from pydantic import BaseModel, Field

from jarvis.reflection.analyzer import ExecutionAnalysis
from jarvis.core.task_graph import TaskGraph, TaskStatus


class ConstitutionScore(BaseModel):
    overall_score: float  # 0.0 to 1.0
    values_score: float
    constraints_score: float
    violations: List[str] = Field(default_factory=list)
    compliances: List[str] = Field(default_factory=list)


class ReflectionScorer:
    """Evaluates task execution against Constitution pillars and constraints."""

    def __init__(self, constitution_dir: str = "jarvis/constitution"):
        self.constitution_dir = Path(constitution_dir)
        self.constraints = self._load_yaml("constraints.yaml")
        self.values = self._load_yaml("values.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = self.constitution_dir / filename
        if path.exists():
            try:
                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                return {}
        return {}

    def score_execution(self, graph: TaskGraph, analysis: ExecutionAnalysis) -> ConstitutionScore:
        violations: List[str] = []
        compliances: List[str] = []

        # 1. Constraint: Mandatory Verification Gate
        all_verified = True
        for tid, node in graph.nodes.items():
            if node.status == TaskStatus.COMPLETED:
                verif = node.metadata.get("verification")
                if not verif or not verif.get("passed"):
                    all_verified = False
                    violations.append(f"Task '{tid}' marked COMPLETED without verified QA gate.")

        if all_verified and analysis.completed_tasks > 0:
            compliances.append("100% of completed tasks passed multi-stage QA & DLP verification gates.")

        # 2. Value: Verifiable Truth (Reliability over Illusion)
        if analysis.completion_rate_pct >= 90.0:
            compliances.append(f"High verifiable completion rate ({analysis.completion_rate_pct}%).")
        elif analysis.failed_tasks > 0 and analysis.completed_tasks == 0:
            violations.append("Zero successful completions in goal execution.")

        # 3. Compute Scores
        constraints_score = 1.0 if not violations else max(0.0, 1.0 - (len(violations) * 0.3))
        values_score = round(min(1.0, analysis.completion_rate_pct / 100.0), 2)
        overall_score = round((constraints_score * 0.6) + (values_score * 0.4), 2)

        return ConstitutionScore(
            overall_score=overall_score,
            values_score=values_score,
            constraints_score=constraints_score,
            violations=violations,
            compliances=compliances,
        )
