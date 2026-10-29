"""
JARVIS Power Catalog Integrity Validator
Validates strict mathematical consistency, unique identifiers,
repository source attribution, execution handlers, and permission schemas.
"""

import sys
import json
from pathlib import Path
from collections import Counter

KNOWN_REPOSITORIES = {
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

REQUIRED_FIELDS = [
    "power_id",
    "power_name",
    "slug",
    "category",
    "source_repo",
    "contributing_repos",
    "execution_handler",
    "status",
    "danger_level"
]

def validate_catalog() -> int:
    catalog_path = Path("data/powers_catalog.json")
    if not catalog_path.exists():
        print(f"Error: Catalog not found at {catalog_path}")
        return 1

    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error: Catalog JSON malformed: {e}")
        return 1

    total_loaded = len(data)
    seen_ids = set()
    seen_names = set()
    seen_slugs = set()
    duplicate_ids = 0
    duplicate_names = 0
    invalid_entries = 0
    unattributed_entries = 0
    
    executable_count = 0
    config_required_count = 0
    reference_only_count = 0

    discovered_source_repos = set()

    for item in data:
        pid = item.get("power_id")
        pname = item.get("power_name")
        slug = item.get("slug")
        srepo = item.get("source_repo")
        crepos = item.get("contributing_repos", [])
        status = item.get("status")

        # Required fields check
        missing_fields = [f for f in REQUIRED_FIELDS if not item.get(f)]
        if missing_fields:
            invalid_entries += 1

        # ID uniqueness
        if not pid or pid in seen_ids:
            duplicate_ids += 1
        else:
            seen_ids.add(pid)

        # Name uniqueness
        if not pname or pname in seen_names:
            duplicate_names += 1
        else:
            seen_names.add(pname)

        # Slug uniqueness
        if not slug or slug in seen_slugs:
            invalid_entries += 1
        else:
            seen_slugs.add(slug)

        # Repository attribution
        if not srepo or srepo not in KNOWN_REPOSITORIES:
            unattributed_entries += 1
        else:
            discovered_source_repos.add(srepo)

        for cr in crepos:
            if cr in KNOWN_REPOSITORIES:
                discovered_source_repos.add(cr)
            else:
                unattributed_entries += 1

        # Status tracking
        if status == "executable":
            executable_count += 1
        elif status == "requires_configuration":
            config_required_count += 1
        elif status == "reference_only":
            reference_only_count += 1
        else:
            invalid_entries += 1

    expected_total = 355
    missing_powers = max(0, expected_total - len(seen_ids))

    # Output formatted exactly as required
    print(f"Source repositories: {len(discovered_source_repos)}")
    print(f"Source powers discovered: {total_loaded}")
    print(f"Catalog powers loaded: {total_loaded}")
    print(f"Unique IDs: {len(seen_ids)}")
    print(f"Missing powers: {missing_powers}")
    print(f"Duplicate IDs: {duplicate_ids}")
    print(f"Invalid entries: {invalid_entries}")
    print(f"Unattributed entries: {unattributed_entries}")
    print(f"Executable powers: {executable_count}")
    print(f"Configuration-required powers: {config_required_count}")
    print(f"Reference-only powers: {reference_only_count}")

    passed = (
        len(discovered_source_repos) == 11 and
        total_loaded == 355 and
        len(seen_ids) == 355 and
        duplicate_ids == 0 and
        duplicate_names == 0 and
        invalid_entries == 0 and
        unattributed_entries == 0 and
        missing_powers == 0
    )

    if passed:
        print("Result: PASS")
        return 0
    else:
        print("Result: FAIL")
        return 1

if __name__ == "__main__":
    sys.exit(validate_catalog())
