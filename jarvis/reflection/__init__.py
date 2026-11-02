"""
JARVIS Reflection Engine Package
Synthesizes Execution Analysis, Gap Detection, Opportunity Detection,
Improvement Generation, and Constitution Scoring into unified Retrospectives.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph
from jarvis.reflection.analyzer import ExecutionAnalyzer, ExecutionAnalysis
from jarvis.reflection.gap_detector import GapDetector, CapabilityGap
from jarvis.reflection.opportunity_detector import OpportunityDetector, Opportunity
from jarvis.reflection.improvement_generator import ImprovementGenerator, ImprovementProposal
from jarvis.reflection.scorer import ReflectionScorer, ConstitutionScore


class UnifiedReflectionReport(BaseModel):
    goal_id: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    analysis: ExecutionAnalysis
    constitution_score: ConstitutionScore
    gaps: List[CapabilityGap] = Field(default_factory=list)
    opportunities: List[Opportunity] = Field(default_factory=list)
    improvement_proposals: List[ImprovementProposal] = Field(default_factory=list)


class ReflectionEngine:
    """Unified engine coordinating all reflection sub-engines."""

    def __init__(self):
        self.analyzer = ExecutionAnalyzer()
        self.gap_detector = GapDetector()
        self.opportunity_detector = OpportunityDetector()
        self.improvement_generator = ImprovementGenerator()
        self.scorer = ReflectionScorer()

    def generate_reflection(self, graph: TaskGraph) -> UnifiedReflectionReport:
        analysis = self.analyzer.analyze_graph(graph)
        gaps = self.gap_detector.detect_gaps(graph)
        opportunities = self.opportunity_detector.detect_opportunities(graph)
        proposals = self.improvement_generator.generate_from_gaps(gaps, analysis)
        constitution_score = self.scorer.score_execution(graph, analysis)

        return UnifiedReflectionReport(
            goal_id=graph.goal_id,
            analysis=analysis,
            constitution_score=constitution_score,
            gaps=gaps,
            opportunities=opportunities,
            improvement_proposals=proposals,
        )


__all__ = [
    "ExecutionAnalyzer",
    "ExecutionAnalysis",
    "GapDetector",
    "CapabilityGap",
    "OpportunityDetector",
    "Opportunity",
    "ImprovementGenerator",
    "ImprovementProposal",
    "ReflectionScorer",
    "ConstitutionScore",
    "UnifiedReflectionReport",
    "ReflectionEngine",
]
