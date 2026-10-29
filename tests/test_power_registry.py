"""
Automated verification tests for Power Registry.
"""

from jarvis.core.power_registry import power_registry

def test_powers_catalog_loaded():
    assert power_registry.total_count() >= 300
    p1 = power_registry.get_power("PWR-001")
    assert p1 is not None
    name = p1.get("power_name") or p1.get("fields", {}).get("Power name") or p1.get("name", "")
    assert "Wake-Word" in name

def test_search_powers():
    results = power_registry.search_powers("screenshot")
    assert len(results) > 0
    assert any("PWR-016" in (r.get("power_id") or r.get("id") or "") or "screenshot" in str(r).lower() for r in results)
