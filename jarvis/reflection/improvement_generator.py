"""
JARVIS Reflection Engine - Improvement Generator
Converts capability gaps and bottlenecks into formal ImprovementRequests.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from jarvis.reflection.gap_detector import CapabilityGap
from jarvis.reflection.analyzer import ExecutionAnalysis


class ImprovementProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str
    priority: str
    status: str = "PROPOSED"
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)


class ImprovementGenerator:
    """Generates structured Improvement proposals ready for Human Review in the Backlog."""

    def generate_from_gaps(self, gaps: List[CapabilityGap], analysis: ExecutionAnalysis) -> List[ImprovementProposal]:
        proposals: List[ImprovementProposal] = []

        for gap in gaps:
            priority = "CRITICAL" if gap.severity == "CRITICAL" else ("HIGH" if gap.severity == "HIGH" else "MEDIUM")
            prop = ImprovementProposal(
                title=f"Resolve Gap: {gap.name}",
                description=gap.description,
                category="capability",
                priority=priority,
                proposed_changes={
                    "gap_type": gap.gap_type,
                    "suggested_capability": gap.suggested_capability,
                    "affected_tasks": gap.affected_tasks,
                    "action_required": f"Implement and register '{gap.suggested_capability}' in CapabilityRegistry.",
                },
            )
            proposals.append(prop)

        # Bottlenecks
        for bottleneck in analysis.bottlenecks:
            prop = ImprovementProposal(
                title=f"Optimize Bottleneck: {bottleneck[:60]}",
                description=bottleneck,
                category="performance",
                priority="MEDIUM",
                proposed_changes={
                    "action_required": "Refine agent prompts, increase timeouts, or optimize tool calling."
                },
            )
            proposals.append(prop)

        return proposals
