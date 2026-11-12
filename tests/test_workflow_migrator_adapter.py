"""Unit tests for WorkflowMigratorAdapter."""

import tempfile
from pathlib import Path
from jarvis.tools.adapters.workflow_migrator_adapter import WorkflowMigratorAdapter
from scripts.migrate_workflows import extract_metadata


def test_workflow_metadata_extraction():
    sample_content = "# Daily Briefing Routine\nExecutes morning telemetry checks."
    name, desc, body = extract_metadata(sample_content, "daily_briefing")
    assert name == "daily_briefing"
    assert "Daily Briefing Routine" in desc
    assert "Daily Briefing Routine" in body


def test_workflow_migration_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_dir = tmp / ".agents" / "workflows"
        wf_dir.mkdir(parents=True)
        test_wf = wf_dir / "test_flow.md"
        test_wf.write_text("# Test Workflow\nRuns unit tests.", encoding="utf-8")

        adapter = WorkflowMigratorAdapter(workspace_root=tmp)
        res = adapter.migrate()

        assert res["status"] == "success"
        assert res["migrated_count"] == 1
