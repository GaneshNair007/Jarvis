"""JARVIS Workflow Migrator Adapter.

Integrates scripts/migrate_workflows.py into the Jarvis Tool Registry for system maintenance.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


class WorkflowMigratorAdapter:
    """Tool adapter for migrating legacy markdown workflows into validated skills."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()

    def migrate(self, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """Discovers and migrates legacy workflows to skills."""
        scan_dir = str(self.workspace_root / target_dir) if target_dir else str(self.workspace_root)

        # Import canonical script
        sys.path.insert(0, str(self.workspace_root))
        try:
            from scripts.migrate_workflows import migrate_workflows
            results = migrate_workflows(workspace_dir=scan_dir)
            return {
                "status": "success",
                "scanned_directory": scan_dir,
                "migrated_count": len(results),
                "migrations": results,
            }
        finally:
            if str(self.workspace_root) in sys.path:
                sys.path.remove(str(self.workspace_root))
