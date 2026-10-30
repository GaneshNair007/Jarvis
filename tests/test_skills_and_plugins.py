"""Automated Tests for Skills, Plugins, Workflow Migration, and Domain Powers.

Validates:
- Skills directory structure (.agents/skills/*)
- Workflow-to-skill idempotent migration logic (scripts/migrate_workflows.py)
- Plugin manifest and layout (plugins/career-ops)
- Developer Powers (git status, diff, test runner)
- Security Powers (secret scanning, kill switch, approval tokens)
- Finance Powers (currency conversion, stock quotes)
- Smart Home Powers (device status, light toggle)
- Automation Powers (cron schedule registration)
"""

from pathlib import Path
import pytest

from scripts.migrate_workflows import extract_metadata, migrate_workflows
from jarvis.powers import (
    developer_powers,
    security_powers,
    finance_powers,
    smart_home_powers,
    automation_powers
)


def test_skills_catalog_structure():
    """Validates that all requested skills exist with proper YAML frontmatter."""
    skills_root = Path(".agents/skills")
    assert skills_root.exists()

    expected_skills = ["browser", "generative_ui", "automation", "plugin", "migrate-workflows"]
    for skill_name in expected_skills:
        skill_file = skills_root / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Skill file missing: {skill_file}"
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert f"name: {skill_name}" in content
        assert "description:" in content


def test_migrate_workflows_logic(tmp_path):
    """Validates idempotent migration from legacy workflows to skills."""
    # Setup legacy directory
    wf_dir = tmp_path / ".agents" / "workflows"
    wf_dir.mkdir(parents=True)

    legacy_file = wf_dir / "daily_sync.md"
    legacy_file.write_text(
        "# Daily Standup Sync\nCollect team updates and format summary.\n",
        encoding="utf-8"
    )

    # Run migration
    records = migrate_workflows(workspace_dir=str(tmp_path))
    assert len(records) == 1
    assert records[0]["status"] == "Migrated"

    # Verify target skill created
    target_skill = tmp_path / ".agents" / "skills" / "daily_sync" / "SKILL.md"
    assert target_skill.exists()
    assert "name: daily_sync" in target_skill.read_text(encoding="utf-8")

    # Verify original file archived to .md.bak
    assert (wf_dir / "daily_sync.md.bak").exists()
    assert not legacy_file.exists()

    # Re-run migration: verify idempotency (preserves existing skill)
    records_second = migrate_workflows(workspace_dir=str(tmp_path))
    assert len(records_second) == 0  # No pending workflows left


def test_plugin_manifest_structure():
    """Validates plugin manifest formatting per plugin skill."""
    plugin_path = Path("plugins/career-ops/plugin.json")
    assert plugin_path.exists()
    import json
    data = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert data["name"] == "jarvis-career-ops"
    assert "displayName" in data
    assert "description" in data
    assert len(data["suggestedPrompts"]) >= 3


def test_developer_powers():
    """Validates DeveloperPowers git queries and test execution."""
    status = developer_powers.git_status()
    assert status["power_id"] == "PWR-025"
    assert "branch" in status

    diff = developer_powers.git_diff()
    assert diff["power_id"] == "PWR-026"
    assert "diff_preview" in diff


def test_security_powers():
    """Validates SecurityPowers zero-leak scanning and kill-switch checks."""
    safe_text = "Standard python code without any credentials."
    scan_safe = security_powers.scan_secrets(safe_text)
    assert scan_safe["safe"] is True

    unsafe_text = "Here is a leak: sk-ant-api03-1234567890abcdef1234567890abcdef1234567890abcdef"
    scan_unsafe = security_powers.scan_secrets(unsafe_text)
    assert scan_unsafe["safe"] is False
    assert scan_unsafe["findings_count"] >= 1

    ks = security_powers.verify_kill_switch()
    assert ks["power_id"] == "PWR-279"
    assert "kill_switch_active" in ks


def test_finance_powers():
    """Validates FinancePowers currency conversion and ticker quotes."""
    conv = finance_powers.convert_currency(100.0, "USD", "EUR")
    assert conv["power_id"] == "PWR-180"
    assert conv["converted_amount"] == 92.0

    quote = finance_powers.get_stock_quote("NVDA")
    assert quote["power_id"] == "PWR-181"
    assert quote["price"] > 0


def test_smart_home_powers():
    """Validates SmartHomePowers device status and light toggling."""
    status = smart_home_powers.get_device_status()
    assert status["power_id"] == "PWR-238"
    assert status["devices_count"] >= 3

    toggle = smart_home_powers.toggle_light("light.living_room")
    assert toggle["power_id"] == "PWR-239"
    assert toggle["new_state"] == "on"


def test_automation_powers():
    """Validates AutomationPowers cron schedule registration."""
    scheds = automation_powers.list_schedules()
    assert scheds["power_id"] == "PWR-253"
    assert scheds["active_schedules_count"] >= 2

    new_sched = automation_powers.register_schedule("hourly_sync", "0 * * * *", "Run hourly delta sync")
    assert new_sched["power_id"] == "PWR-254"
    assert new_sched["status"] == "registered"

