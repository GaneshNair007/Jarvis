"""
JARVIS Self-Improvement Pipeline
Coordinates the flow:
Reflection -> Capability Gap -> Improvement Request -> Engineering Backlog
Enforces strict invariants:
  1. NO automatic merges.
  2. NO production code modification.
  3. Improvement requests only.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.reflection import UnifiedReflectionReport
from jarvis.workflows.pr_workflow import WorkflowState, safe_pr_workflow_manager
from jarvis.core.logger import get_logger

logger = get_logger("self_improvement.service")


class BacklogItem(BaseModel):
    id: str
    title: str
    description: str
    category: str
    priority: str
    workflow_state: WorkflowState = WorkflowState.PROPOSED
    target_branch: str = "feature/autonomous-improvement"
    proposed_changes: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class ImprovementService:
    """
    Manages the backlog of self-improvement proposals.
    Never modifies production files or initiates merges automatically.
    """

    def __init__(self):
        self.backlog: Dict[str, BacklogItem] = {}

    def process_reflection(self, reflection: UnifiedReflectionReport) -> List[BacklogItem]:
        """
        Converts reflections into verified engineering backlog proposals.
        Guaranteed read-only with respect to production code.
        """
        created_items: List[BacklogItem] = []

        for proposal in reflection.improvement_proposals:
            branch_name = f"feature/imp-{proposal.id[:8]}"

            # Validate target branch against safety manager
            safe_pr_workflow_manager.validate_branch_target(branch_name, actor="improvement_service")

            item = BacklogItem(
                id=proposal.id,
                title=proposal.title,
                description=proposal.description,
                category=proposal.category,
                priority=proposal.priority,
                workflow_state=WorkflowState.PROPOSED,
                target_branch=branch_name,
                proposed_changes=proposal.proposed_changes,
            )
            self.backlog[item.id] = item
            created_items.append(item)
            logger.info(f"ImprovementService: Logged proposal '{item.title}' into Backlog (State: PROPOSED).")

        return created_items

    def get_backlog(self, state: Optional[WorkflowState] = None) -> List[BacklogItem]:
        """Returns pending backlog items."""
        items = list(self.backlog.values())
        if state:
            items = [i for i in items if i.workflow_state == state]
        return items

    def can_modify_production_code(self) -> bool:
        """Inviolable architecture safety check: always returns False."""
        return False


# Global Singleton Service
improvement_service = ImprovementService()
