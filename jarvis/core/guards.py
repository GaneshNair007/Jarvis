"""
JARVIS Architecture Guards
Enforces hard system invariants:
  1. Agents cannot perform direct SQL (must access data via repositories).
  2. Agents must access data via repositories.
  3. Task execution must flow through Task Graph.
  4. Reflection engine cannot bypass approval workflow.
  5. Capability registry cannot modify production code.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from jarvis.core.logger import get_logger

logger = get_logger("core.guards")


class ArchitectureViolationError(Exception):
    """Raised when an architectural boundary or inviolable guardrail is breached."""
    pass


class ArchitectureGuard:
    """Enforces architectural segregation of concerns and data access boundaries."""

    # Disallowed raw SQL statements when called by agents
    RAW_SQL_PATTERNS = [
        re.compile(r"\bSELECT\b", re.IGNORECASE),
        re.compile(r"\bINSERT\b\s+INTO", re.IGNORECASE),
        re.compile(r"\bUPDATE\b\s+\w+\s+\bSET\b", re.IGNORECASE),
        re.compile(r"\bDELETE\b\s+FROM", re.IGNORECASE),
        re.compile(r"\bDROP\b\s+TABLE", re.IGNORECASE),
        re.compile(r"\bALTER\b\s+TABLE", re.IGNORECASE),
    ]

    @classmethod
    def check_agent_sql_access(cls, caller_agent_or_module: str, query: str) -> None:
        """
        Guard 1: Agents cannot execute direct SQL.
        Must access data via the Repository layer.
        """
        caller_lower = caller_agent_or_module.lower()
        if any(agent_tag in caller_lower for agent_tag in ["agent", "worker", "scout", "subagent", "llm"]):
            for pattern in cls.RAW_SQL_PATTERNS:
                if pattern.search(query):
                    msg = (
                        f"ARCHITECTURE VIOLATION: Agent '{caller_agent_or_module}' attempted direct raw SQL execution: "
                        f"'{query[:50]}...'. All database interactions must route through the Repository layer."
                    )
                    logger.critical(msg)
                    raise ArchitectureViolationError(msg)

    @classmethod
    def check_task_execution_flow(cls, task_metadata: dict) -> None:
        """
        Guard 2: Task execution must flow through the Task Graph engine.
        Tasks executing outside a validated TaskGraph context are disallowed.
        """
        if not task_metadata.get("parent_goal") or not task_metadata.get("task_id"):
            msg = "ARCHITECTURE VIOLATION: Task execution attempted outside a validated TaskGraph parent goal context."
            logger.critical(msg)
            raise ArchitectureViolationError(msg)

    @classmethod
    def check_reflection_approval_bypass(cls, current_workflow_state: str, attempted_action: str) -> None:
        """
        Guard 3: Reflection engine cannot bypass approval workflow.
        Cannot merge unless status is explicitly APPROVED.
        """
        if attempted_action.lower() in ("merge", "push_main", "deploy"):
            if current_workflow_state.upper() != "APPROVED":
                msg = (
                    f"ARCHITECTURE VIOLATION: Attempted action '{attempted_action}' while PR workflow is in "
                    f"'{current_workflow_state}' state. Merges require explicit human APPROVED status."
                )
                logger.critical(msg)
                raise ArchitectureViolationError(msg)

    @classmethod
    def check_capability_registry_write(cls, target_path: str) -> None:
        """
        Guard 4: Capability registry cannot modify production source code.
        Target paths in 'jarvis/', 'db/', 'app/' are read-only to capability registry.
        """
        path_lower = target_path.lower().replace("\\", "/")
        if any(path_lower.startswith(prefix) for prefix in ["jarvis/", "db/", "app/", "./jarvis/", "./db/", "./app/"]):
            if path_lower.endswith(".py"):
                msg = (
                    f"ARCHITECTURE VIOLATION: CapabilityRegistry attempted write to production code: '{target_path}'. "
                    f"Missing capabilities can only emit ImprovementRequests."
                )
                logger.critical(msg)
                raise ArchitectureViolationError(msg)

    @classmethod
    def validate_system_invariants(cls) -> bool:
        """Audit check confirming all 5 guards are functioning as intended."""
        # 1. Test SQL guard
        try:
            cls.check_agent_sql_access("worker_agent", "SELECT * FROM users")
            return False  # Should have raised
        except ArchitectureViolationError:
            pass

        # 2. Test Task flow guard
        try:
            cls.check_task_execution_flow({})
            return False  # Should have raised
        except ArchitectureViolationError:
            pass

        # 3. Test Approval bypass guard
        try:
            cls.check_reflection_approval_bypass("AWAITING_APPROVAL", "merge")
            return False  # Should have raised
        except ArchitectureViolationError:
            pass

        # 4. Test Capability write guard
        try:
            cls.check_capability_registry_write("jarvis/core/task_graph.py")
            return False  # Should have raised
        except ArchitectureViolationError:
            pass

        logger.info("Architecture Guards: All 5 inviolable system invariants verified successfully.")
        return True
