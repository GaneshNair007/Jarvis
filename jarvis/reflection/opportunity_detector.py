"""
JARVIS Reflection Engine - Opportunity Detector
Extracts strategic and technical advancement opportunities from task outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskStatus


class Opportunity(BaseModel):
    category: str  # e.g. "PRODUCT", "SKILL", "SPEED", "RESEARCH"
    title: str
    description: str
    source_task: str
    impact_level: str = "HIGH"  # LOW, MEDIUM, HIGH, TRANSFORMATIVE


class OpportunityDetector:
    """Discovers expansion opportunities and reusable skills from task execution outputs."""

    def detect_opportunities(self, graph: TaskGraph) -> List[Opportunity]:
        opportunities: List[Opportunity] = []

        for task_id, node in graph.nodes.items():
            if node.status == TaskStatus.COMPLETED:
                for key, val in node.outputs.items():
                    key_lower = key.lower()
                    if any(term in key_lower for term in ["opportunity", "suggest", "idea", "product", "export"]):
                        opportunities.append(
                            Opportunity(
                                category="PRODUCT" if "product" in key_lower else "SKILL",
                                title=f"Opportunity from {node.name}",
                                description=str(val),
                                source_task=task_id,
                                impact_level="HIGH",
                            )
                        )

                    if "repo_created" in key_lower:
                        opportunities.append(
                            Opportunity(
                                category="ENGINEERING",
                                title=f"Open Source Asset Created",
                                description=f"Automate CI/CD and GSoC alignment for created repository: {val}",
                                source_task=task_id,
                                impact_level="HIGH",
                            )
                        )

        # Overall Graph Opportunity
        if graph.is_completed() and len(graph.nodes) >= 5:
            opportunities.append(
                Opportunity(
                    category="WORKFLOW",
                    title=f"Synthesize Reusable Workflow Template",
                    description=f"Goal '{graph.goal_id}' completed with 100% success; package DAG topology into standard skill template.",
                    source_task="goal_graph",
                    impact_level="TRANSFORMATIVE",
                )
            )

        return opportunities
