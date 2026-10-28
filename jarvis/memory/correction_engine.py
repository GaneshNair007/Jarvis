"""
JARVIS User Correction Engine
Handles interactive and persistent user corrections.
Promotes explicit instructions into the procedural / directive memory layers,
ensuring Jarvis learns from mistakes and updates behavior across future sessions.
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from jarvis.memory.store import db_store
from jarvis.memory.layers import memory_manager
from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger

logger = get_logger("correction_engine")

class CorrectionEngine:
    """Manages the lifecycle of user behavioral corrections and directives."""

    def __init__(self):
        self.store = db_store
        self.memory = memory_manager

    def record_correction(
        self,
        user_quote: str,
        new_instruction: str,
        scope: str = "always",
        failure_id: Optional[str] = None,
        old_behavior: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records a user correction and promotes it into persistent memory
        based on the specified scope ('this_task', 'this_project', 'always').
        """
        scope_clean = scope.lower().strip()
        if scope_clean not in ("this_task", "this_project", "always"):
            raise ValueError(f"Invalid scope '{scope}'. Must be one of: 'this_task', 'this_project', 'always'")

        correction_id = f"corr_{uuid.uuid4().hex[:12]}"
        now = time.time()

        # Save into corrections table
        self.store.save_correction(
            correction_id=correction_id,
            user_quote=user_quote,
            new_instruction=new_instruction,
            scope=scope_clean,
            failure_id=failure_id,
            old_behavior=old_behavior
        )

        memory_node_id = None
        promoted_layer = None

        if scope_clean == "always":
            # Standing immutable directive
            promoted_layer = "DIRECTIVE"
            memory_node_id = self.memory.store_memory(
                layer="DIRECTIVE",
                content=f"USER DIRECTIVE: {new_instruction} (Derived from correction: '{user_quote}')",
                metadata={
                    "correction_id": correction_id,
                    "failure_id": failure_id,
                    "old_behavior": old_behavior,
                    "priority": "CRITICAL",
                    "origin": "user_correction"
                },
                is_hypothesis=False,
                confidence=1.0,
                evidence_count=1
            )
        elif scope_clean == "this_project":
            # Persistent procedural skill for this project
            promoted_layer = "PROCEDURAL"
            memory_node_id = self.memory.store_memory(
                layer="PROCEDURAL",
                content=f"PROJECT WORKFLOW: {new_instruction}",
                metadata={
                    "correction_id": correction_id,
                    "failure_id": failure_id,
                    "scope": "project"
                },
                is_hypothesis=False,
                confidence=1.0
            )
        else:
            # Task-specific working memory
            promoted_layer = "WORKING"
            memory_node_id = self.memory.store_memory(
                layer="WORKING",
                content=f"TASK OVERRIDE: {new_instruction}",
                metadata={
                    "correction_id": correction_id,
                    "failure_id": failure_id,
                    "scope": "task"
                },
                is_hypothesis=False,
                confidence=1.0
            )

        audit_ledger.record(
            actor="CorrectionEngine",
            action="USER_CORRECTION_RECORDED",
            target=correction_id,
            payload={
                "scope": scope_clean,
                "user_quote": user_quote,
                "new_instruction": new_instruction,
                "promoted_layer": promoted_layer,
                "memory_node_id": memory_node_id
            },
            result="PROMOTED"
        )

        logger.info("Correction %s recorded and promoted to %s memory", correction_id, promoted_layer)

        return {
            "correction_id": correction_id,
            "failure_id": failure_id,
            "user_quote": user_quote,
            "old_behavior": old_behavior,
            "new_instruction": new_instruction,
            "scope": scope_clean,
            "status": "ACTIVE",
            "promoted_layer": promoted_layer,
            "memory_node_id": memory_node_id,
            "created_at": now
        }

    def list_corrections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent user corrections."""
        return self.store.list_corrections(limit=limit)

# Singleton Correction Engine
correction_engine = CorrectionEngine()
