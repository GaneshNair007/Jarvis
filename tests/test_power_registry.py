"""
Automated verification tests for Power Registry & Catalog Integrity.
"""

from jarvis.core.power_registry import power_registry
from jarvis.core.validate_powers import validate_catalog

def test_powers_catalog_loaded():
    assert power_registry.total_count() == 355
    all_powers = power_registry.list_all_powers()
    assert len(all_powers) == 355

    # Check ID uniqueness
    ids = [p["power_id"] for p in all_powers]
    assert len(ids) == len(set(ids)) == 355

    # Check Name uniqueness
    names = [p["power_name"] for p in all_powers]
    assert len(names) == len(set(names)) == 355

    # Check Slug uniqueness
    slugs = [p["slug"] for p in all_powers]
    assert len(slugs) == len(set(slugs)) == 355

def test_lookup_variations():
    # Uppercase ID
    p_upper = power_registry.get_power("PWR-001")
    assert p_upper is not None
    assert p_upper["power_name"] == "Wake-Word Activation"

    # Lowercase ID
    p_lower = power_registry.get_power("pwr-001")
    assert p_lower is not None
    assert p_lower["power_id"] == "PWR-001"

    # Lookup by slug
    p_slug = power_registry.get_power("wake-word-activation")
    assert p_slug is not None
    assert p_slug["power_id"] == "PWR-001"

    # Non-existent
    assert power_registry.get_power("PWR-999") is None

def test_ecosystem_repositories_and_formula():
    expected_repos = {
        "atticus-mac",
        "browser-use",
        "career-ops",
        "cua",
        "hermes-agent",
        "mcp-servers",
        "open-interpreter",
        "open-jarvis",
        "openclaw",
        "openhands",
        "ui-tars-desktop"
    }
    registered_repos = set(power_registry.list_ecosystem_repos())
    assert expected_repos == registered_repos

    formula = power_registry.get_ecosystem_formula()
    for r in expected_repos:
        assert r in formula
    assert "355 powers" in formula

    # Ensure every repo contributes at least 10 powers
    for r in expected_repos:
        repo_powers = power_registry.get_powers_by_repo(r)
        assert len(repo_powers) >= 10, f"Repo {r} has fewer than 10 powers: {len(repo_powers)}"

def test_search_powers():
    results = power_registry.search_powers("screenshot")
    assert len(results) > 0
    assert any(r.get("power_id") == "PWR-016" for r in results)

def test_category_filtering():
    categories = power_registry.list_categories()
    assert len(categories) == 22
    assert "Voice" in categories
    assert "Developer" in categories

    voice_powers = power_registry.get_powers_by_category("Voice")
    assert len(voice_powers) >= 5

    # Case-insensitive
    voice_lower = power_registry.get_powers_by_category("voice")
    assert len(voice_lower) == len(voice_powers)

def test_catalog_integrity_validation():
    result = validate_catalog()
    assert result == 0
