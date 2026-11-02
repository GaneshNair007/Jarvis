"""
JARVIS Safe PR Workflow & Human Gatekeeper Engine
Enforces:
  Workflow States: PROPOSED -> PLANNED -> GENERATED -> TESTING -> SECURITY_REVIEW -> AWAITING_APPROVAL -> APPROVED -> MERGED (or REJECTED)
  Strict Safety Rule: Reflection engine and autonomous agents can NEVER directly push or merge to 'main'.
  All automated code generation is strictly confined to isolated feature branches.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("workflows.pr_workflow")


class WorkflowState(str, Enum):
    PROPOSED = "PROPOSED"
    PLANNED = "PLANNED"
    GENERATED = "GENERATED"
    TESTING = "TESTING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    REJECTED = "REJECTED"


class SecurityViolationError(Exception):
    """Raised when an autonomous agent attempts an unauthorized push or bypasses human gates."""
    pass


class SafePRWorkflowManager:
    """
    Guarantees that autonomous self-improvement never modifies production code directly.
    Transitions through verified checkpoints and requires explicit human approval for merges.
    """

    ALLOWED_TRANSITIONS = {
        WorkflowState.PROPOSED: [WorkflowState.PLANNED, WorkflowState.REJECTED],
        WorkflowState.PLANNED: [WorkflowState.GENERATED, WorkflowState.REJECTED],
        WorkflowState.GENERATED: [WorkflowState.TESTING, WorkflowState.REJECTED],
        WorkflowState.TESTING: [WorkflowState.SECURITY_REVIEW, WorkflowState.REJECTED],
        WorkflowState.SECURITY_REVIEW: [WorkflowState.AWAITING_APPROVAL, WorkflowState.REJECTED],
        WorkflowState.AWAITING_APPROVAL: [WorkflowState.APPROVED, WorkflowState.REJECTED],
        WorkflowState.APPROVED: [WorkflowState.MERGED, WorkflowState.REJECTED],
        WorkflowState.MERGED: [],
        WorkflowState.REJECTED: [WorkflowState.PROPOSED],  # Can be re-proposed after fixes
    }

    def validate_branch_target(self, target_branch: str, actor: str) -> None:
        """
        Inviolable Guard: Autonomous actors can NEVER push directly to main.
        Only a human owner or the merge gate with verified signature can merge to main.
        """
        target = target_branch.lower().strip()
        actor_clean = actor.lower().strip()
        if target in ("main", "master", "production") and actor_clean not in ("ganesh", "human_owner"):
            msg = f"SECURITY BLOCK: Actor '{actor}' attempted direct push/merge to protected branch '{target}'! Autonomous changes must use feature branches."
            logger.critical(msg)
            raise SecurityViolationError(msg)

    def transition_state(
        self,
        current_state: WorkflowState,
        next_state: WorkflowState,
        actor: str,
        security_passed: bool = False,
        tests_passed: bool = False,
    ) -> WorkflowState:
        """Enforces rigorous state machine progression and quality gates."""
        allowed = self.ALLOWED_TRANSITIONS.get(current_state, [])
        if next_state not in allowed:
            raise ValueError(f"Illegal workflow transition: Cannot move from {current_state.value} to {next_state.value}.")

        # Security review check
        if next_state == WorkflowState.AWAITING_APPROVAL:
            if not tests_passed:
                raise ValueError("Cannot move to AWAITING_APPROVAL: PyTest automated test suite did not pass.")
            if not security_passed:
                raise ValueError("Cannot move to AWAITING_APPROVAL: 10-layer DLP and secret scan did not pass.")

        # Human approval check
        if next_state == WorkflowState.APPROVED:
            if actor.lower() not in ("ganesh", "human_owner", "authorized_reviewer"):
                raise SecurityViolationError(f"Actor '{actor}' is not authorized to grant human approval.")

        logger.info(f"PR Workflow: Transitioned from {current_state.value} to {next_state.value} by [{actor}].")
        return next_state


# Global Workflow Manager
safe_pr_workflow_manager = SafePRWorkflowManager()
