"""
JARVIS Central Power Registry
Manages all 355 operational capabilities, metadata schemas,
danger levels, category profiles, and MCP tool bindings.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from jarvis.config import settings

class PowerRegistry:
    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or settings.catalog_path
        self.powers: Dict[str, Dict[str, Any]] = {}
        self.category_index: Dict[str, List[str]] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Loads power definitions from the JSON catalog."""
        if not self.catalog_path.exists():
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                for item in records:
                    pid = item.get("id")
                    if not pid:
                        continue
                    self.powers[pid] = item
                    cat = item.get("fields", {}).get("Category", "General")
                    if cat not in self.category_index:
                        self.category_index[cat] = []
                    self.category_index[cat].append(pid)
        except Exception as e:
            print(f"[PowerRegistry] Warning: Error loading catalog: {e}")

    def get_power(self, power_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves power definition by ID (e.g. 'PWR-001')."""
        return self.powers.get(power_id.upper())

    def search_powers(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches powers by keyword across name, description, and examples."""
        query_lower = query.lower()
        results = []

        for p in self.powers.values():
            name = (p.get("fields", {}).get("Power name") or p.get("name", "")).lower()
            desc = (p.get("fields", {}).get("One-line description") or "").lower()
            examples = (p.get("fields", {}).get("User command examples") or "").lower()

            if query_lower in name or query_lower in desc or query_lower in examples:
                results.append(p)
                if len(results) >= limit:
                    break

        return results

    def list_categories(self) -> List[str]:
        return sorted(list(self.category_index.keys()))

    def get_powers_by_category(self, category: str) -> List[Dict[str, Any]]:
        pids = self.category_index.get(category, [])
        return [self.powers[pid] for pid in pids if pid in self.powers]

    def total_count(self) -> int:
        return len(self.powers)

# Singleton Power Registry
power_registry = PowerRegistry()
