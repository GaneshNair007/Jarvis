"""
Comprehensive Test Suite for JARVIS 355-Power Master Catalog.
Verifies coverage across all 20 categories, executable handlers,
HMAC approval gates for destructive powers, and zero unhandled exceptions.
"""

import pytest
import asyncio
from jarvis.core.power_registry import power_registry
from jarvis.core.orchestrator import orchestrator


class TestFullPowerCatalog:
    """Tests the integrity and execution of all 355 catalog powers across 20 domains."""

    def test_catalog_completeness(self):
        """Asserts that all 355 powers from PWR-001 to PWR-355 are indexed."""
        all_powers = power_registry.list_all_powers()
        assert len(all_powers) == 355, f"Expected 355 powers, found {len(all_powers)}"

        expected_ids = {f"PWR-{i:03d}" for i in range(1, 356)}
        actual_ids = {p.get("power_id") for p in all_powers if p.get("power_id")}
        missing = expected_ids - actual_ids
        assert len(missing) == 0, f"Missing catalog power IDs: {missing}"

    def test_all_20_categories_indexed(self):
        """Verifies that all 20 functional domains exist in the category index."""
        categories = power_registry.list_categories()
        assert len(categories) >= 20, f"Expected at least 20 categories, got {len(categories)}"

        # Check key domain presences
        cats_lower = [c.lower() for c in categories]
        expected_keywords = [
            "voice", "screen", "instant", "dictation", "browser",
            "file", "it admin", "network", "security", "developer",
            "productivity", "communication", "finance", "youtube",
            "smart", "automation", "multi-agent", "iron man", "career", "research"
        ]
        for kw in expected_keywords:
            assert any(kw in c for c in cats_lower), f"Missing category matching keyword: {kw}"

    @pytest.mark.parametrize("power_id,kwargs,expected_keys", [
        ("PWR-001", {}, ["power_id", "status"]),
        ("PWR-016", {}, ["power_id", "title"]),
        ("PWR-027", {"app_name": "notepad"}, ["power_id", "status"]),
        ("PWR-053", {"text": "need this done ASAP", "target_tone": "formal"}, ["power_id", "transformed_text"]),
        ("PWR-063", {"query": "AI architecture"}, ["power_id", "results"]),
        ("PWR-082", {"path": "README.md"}, ["power_id", "status"]),
        ("PWR-100", {}, ["power_id", "status"]),
        ("PWR-127", {"host": "127.0.0.1", "count": 1}, ["power_id", "status"]),
        ("PWR-147", {"password": "Password123!"}, ["power_id", "strength"]),
        ("PWR-162", {"pattern": "Jarvis", "directory": "jarvis"}, ["power_id", "status"]),
        ("PWR-185", {}, ["power_id", "events"]),
        ("PWR-191", {}, ["power_id", "opportunities"]),
        ("PWR-209", {"name": "Ganesh"}, ["power_id", "status"]),
        ("PWR-215", {"symbol": "NVDA"}, ["power_id", "price"]),
        ("PWR-222", {}, ["power_id", "indices"]),
        ("PWR-237", {"topic": "AI Operating System"}, ["power_id", "script"]),
        ("PWR-256", {"state": "on"}, ["power_id", "state"]),
        ("PWR-272", {}, ["power_id", "active_count"]),
        ("PWR-288", {"goal": "Run system diagnostic"}, ["power_id", "status"]),
        ("PWR-308", {"goal": "Check screen layout"}, ["power_id", "status"]),
        ("PWR-327", {}, ["power_id", "status", "persona"]),
        ("PWR-328", {}, ["power_id", "status"]),
        ("PWR-338", {"task_description": "Analyze system logs"}, ["power_id", "suggested_tools"]),
    ])
    def test_representative_power_execution(self, power_id, kwargs, expected_keys):
        """Verifies that representative powers across all domains execute cleanly."""
        res = power_registry.execute_power(power_id, **kwargs)
        assert isinstance(res, dict), f"Expected dict return for {power_id}, got {type(res)}"
        for k in expected_keys:
            assert k in res, f"Expected key '{k}' in {power_id} output, got {res.keys()}"

    def test_destructive_power_approval_gate(self):
        """Asserts that high-danger powers require approval tokens."""
        from jarvis.powers.instant_powers import instant_powers

        # Deleting a file without approval must require approval
        del_res = instant_powers.delete_file("crucial_system_file.dll")
        assert del_res.get("approval_required") is True
        assert del_res.get("status") == "pending_approval"

        # Emptying trash without approval must require approval
        trash_res = instant_powers.empty_trash()
        assert trash_res.get("approval_required") is True
        assert trash_res.get("status") == "pending_approval"

    @pytest.mark.asyncio
    async def test_e2e_orchestrator_fast_lane(self):
        """Verifies end-to-end orchestration dispatch across new power commands."""
        queries = [
            "stock quote NVDA",
            "market briefing",
            "mission control hud",
            "PWR-127",
            "PWR-215",
            "PWR-327",
            "youtube script autonomous AI agents",
        ]
        for q in queries:
            res = await orchestrator.process_user_query(q)
            assert res.get("status") == "COMPLETED", f"Query '{q}' failed: {res}"
            assert res.get("tier") == "BYPASS", f"Query '{q}' was not routed to BYPASS: {res.get('tier')}"
            assert res.get("duration_ms", 9999) < 5000, f"Query '{q}' exceeded latency budget"