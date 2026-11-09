"""
JARVIS Reflection Engine - Capability Gap Detector
Detects missing capabilities, unsupported tool requirements, and repeated failures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskStatus


class CapabilityGap(BaseModel):
    gap_type: str  # e.g. "MISSING_TOOL", "REPEATED_FAILURE", "TIMEOUT"
    name: str
    description: str
    affected_tasks: List[str] = Field(default_factory=list)
    suggested_capability: str
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL


class GapDetector:
    """Inspects task failures and tool requirements to detect system capability gaps."""

    def __init__(self, known_capabilities: Set[str] = None):
        self.known_capabilities = known_capabilities or {
            "web_search",
            "ast_mapper",
            "git_cli",
            "data_filter",
            "doc_parser",
            "deep_reasoner",
            "decision_matrix",
            "roadmap_generator",
            "pytest",
            "dlp_scan",
            "system_health",
        }

    def detect_gaps(self, graph: TaskGraph) -> List[CapabilityGap]:
        gaps: List[CapabilityGap] = []
        missing_tools: Dict[str, List[str]] = {}

        for task_id, node in graph.nodes.items():
            # 1. Check for missing tool requirements
            for req_tool in node.tool_requirements:
                if req_tool not in self.known_capabilities:
                    if req_tool not in missing_tools:
                        missing_tools[req_tool] = []
                    missing_tools[req_tool].append(task_id)

            # 2. Check for task failure causes
            if node.status == TaskStatus.FAILED:
                err = node.metadata.get("last_error", "")
                if "timeout" in err.lower():
                    gaps.append(
                        CapabilityGap(
                            gap_type="TIMEOUT",
                            name=f"Execution Timeout in {node.name}",
                            description=f"Task '{node.name}' timed out repeatedly: {err}",
                            affected_tasks=[task_id],
                            suggested_capability=f"optimize_{node.department}_pipeline",
                            severity="HIGH",
                        )
                    )
                elif "unredacted" in err.lower() or "security" in err.lower():
                    gaps.append(
                        CapabilityGap(
                            gap_type="SECURITY_DLP_VIOLATION",
                            name=f"DLP Leak Prevention in {node.name}",
                            description=f"Task '{node.name}' failed DLP quality gate.",
                            affected_tasks=[task_id],
                            suggested_capability="enhanced_dlp_prefilter",
                            severity="CRITICAL",
                        )
                    )

        for missing_tool, task_ids in missing_tools.items():
            gaps.append(
                CapabilityGap(
                    gap_type="MISSING_TOOL",
                    name=f"Missing Tool: {missing_tool}",
                    description=f"Required tool '{missing_tool}' is not registered in system capability registry.",
                    affected_tasks=task_ids,
                    suggested_capability=f"tool_integration_{missing_tool}",
                    severity="HIGH" if len(task_ids) > 1 else "MEDIUM",
                )
            )

        return gaps
