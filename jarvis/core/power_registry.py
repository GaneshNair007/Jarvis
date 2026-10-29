"""
JARVIS Central Power Registry
Manages all 355 operational capabilities, metadata schemas,
danger levels, category profiles, and MCP tool bindings.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from jarvis.config import settings

INITIAL_POWERS = [
    {
        "power_id": "PWR-CHAT",
        "name": "chat",
        "category": "Core Assistant",
        "description": "Conversational turn with memory recall and hybrid routing",
        "triggers": ["chat", "talk", "ask", "explain"],
        "inputs": ["message: str", "user_id: str"],
        "outputs": ["response: str", "retrieved_memories: list"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["litellm", "mem0"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-MEM-SEARCH",
        "name": "memory_search",
        "category": "Memory Vault",
        "description": "Searches long-term semantic memory and standing directives",
        "triggers": ["remember", "recall", "find memory", "what is my"],
        "inputs": ["query: str", "layer: Optional[str]"],
        "outputs": ["memories: list[dict]"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["mem0", "sqlite/postgres"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-MEM-ADD",
        "name": "memory_add",
        "category": "Memory Vault",
        "description": "Stores user fact or preference into long-term vault",
        "triggers": ["remember that", "store fact", "my preference is"],
        "inputs": ["content: str", "layer: str"],
        "outputs": ["node_id: str", "status: str"],
        "required_permissions": ["tier_1_write"],
        "danger_level": "low",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["mem0"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-MEM-DELETE",
        "name": "memory_delete",
        "category": "Memory Vault",
        "description": "Deletes specific memory node or standing preference",
        "triggers": ["forget", "delete memory"],
        "inputs": ["node_id: str"],
        "outputs": ["status: str"],
        "required_permissions": ["tier_2_delete"],
        "danger_level": "medium",
        "approval_required": True,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["mem0"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-TASK-CREATE",
        "name": "task_create",
        "category": "Task Engine",
        "description": "Triages, plans, and queues an autonomous workflow task",
        "triggers": ["run task", "execute", "plan"],
        "inputs": ["title: str", "inputs: dict"],
        "outputs": ["task_id: str", "status: str"],
        "required_permissions": ["tier_1_write"],
        "danger_level": "low",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["task_engine"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-TASK-STATUS",
        "name": "task_status",
        "category": "Task Engine",
        "description": "Retrieves execution status, logs, and artifacts of a task",
        "triggers": ["task status", "is task done"],
        "inputs": ["task_id: str"],
        "outputs": ["task: dict"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["task_engine"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-WEB-RESEARCH",
        "name": "web_research",
        "category": "Research Engine",
        "description": "Autonomous multi-source web research with cited Markdown synthesis",
        "triggers": ["research", "investigate", "study"],
        "inputs": ["query: str", "max_sources: int"],
        "outputs": ["report: str", "sources: list"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["playwright", "duckduckgo"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-URL-READ",
        "name": "url_read",
        "category": "Browser Automation",
        "description": "Fetches and extracts clean text & DOM layout from web page",
        "triggers": ["read page", "fetch url", "open link"],
        "inputs": ["url: str"],
        "outputs": ["title: str", "content: str", "links: list"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["playwright"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-DOC-INGEST",
        "name": "document_ingest",
        "category": "Document Intelligence",
        "description": "Parses and indexes PDF, Markdown, and TXT files into RAG store",
        "triggers": ["ingest file", "index pdf", "parse doc"],
        "inputs": ["file_path: str"],
        "outputs": ["doc_id: str", "pages: int", "chunks: int", "sha256: str"],
        "required_permissions": ["tier_1_write"],
        "danger_level": "low",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["pymupdf", "tfidf"],
        "test_status": "verified"
    },
    {
        "power_id": "PWR-DOC-QUERY",
        "name": "document_query",
        "category": "Document Intelligence",
        "description": "Queries indexed documents returning exact page citations & provenance",
        "triggers": ["search pdf", "find in document", "query docs"],
        "inputs": ["query: str", "top_k: int"],
        "outputs": ["answer: str", "citations: list[dict]"],
        "required_permissions": ["tier_0_read"],
        "danger_level": "none",
        "approval_required": False,
        "enabled": True,
        "version": "1.0.0",
        "dependencies": ["document_rag"],
        "test_status": "verified"
    }
]

class PowerRegistry:
    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or settings.catalog_path
        self.powers: Dict[str, Dict[str, Any]] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.initial_powers: Dict[str, Dict[str, Any]] = {p["name"]: p for p in INITIAL_POWERS}
        for p in INITIAL_POWERS:
            self.initial_powers[p["power_id"]] = p
        self.repo_index: Dict[str, List[str]] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Loads power definitions from the JSON catalog."""
        if not self.catalog_path.exists():
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                for item in records:
                    pid = item.get("power_id") or item.get("id")
                    if not pid:
                        continue
                    self.powers[pid] = item
                    
                    # Category index (case-insensitive key mapping)
                    cat = item.get("category") or item.get("fields", {}).get("Category", "General")
                    cat_key = cat.strip().lower()
                    if cat_key not in self.category_index:
                        self.category_index[cat_key] = []
                    self.category_index[cat_key].append(pid)

                    # Repository index (JARVIS = a + b + c ... n)
                    repos = list(item.get("contributing_repos", []))
                    srepo = item.get("source_repo")
                    if srepo and srepo not in repos:
                        repos.insert(0, srepo)
                    for r in repos:
                        r_key = r.strip().lower()
                        if r_key not in self.repo_index:
                            self.repo_index[r_key] = []
                        if pid not in self.repo_index[r_key]:
                            self.repo_index[r_key].append(pid)
        except Exception as e:
            print(f"[PowerRegistry] Warning: Error loading catalog: {e}")

    def get_power(self, power_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves power definition by ID, slug, or name (e.g. 'PWR-001' or 'chat')."""
        if power_id in self.initial_powers:
            return self.initial_powers[power_id]
        
        pid_clean = power_id.strip()
        pid_upper = pid_clean.upper()
        if pid_upper in self.powers:
            return self.powers[pid_upper]
        if pid_clean in self.powers:
            return self.powers[pid_clean]
        
        # Search by slug or power_name
        query = pid_clean.lower()
        for p in self.powers.values():
            if p.get("slug") == query:
                return p
            if (p.get("power_name") or "").lower() == query:
                return p
        return None

    def enable_power(self, power_id: str) -> bool:
        p = self.get_power(power_id)
        if p:
            p["enabled"] = True
            return True
        return False

    def disable_power(self, power_id: str) -> bool:
        p = self.get_power(power_id)
        if p:
            p["enabled"] = False
            return True
        return False

    def register_power(self, power: Dict[str, Any]) -> None:
        """Registers a dynamic or integration power."""
        pid = power.get("power_id") or power.get("name")
        if pid:
            self.initial_powers[pid] = power

    def list_powers(self) -> List[Dict[str, Any]]:
        """Returns the roster of initial and integration-registered powers."""
        return list(self.initial_powers.values())

    def list_all_powers(self) -> List[Dict[str, Any]]:
        """Returns all 355 powers from the Master Catalog."""
        if self.powers:
            return list(self.powers.values())
        return list(self.initial_powers.values())

    def search_powers(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches powers by keyword across name, slug, description, and examples."""
        query_lower = query.lower()
        results = []

        # Check initial powers
        for p in INITIAL_POWERS:
            if query_lower in p["name"].lower() or query_lower in p["description"].lower():
                results.append(p)

        # Check catalog powers
        for p in self.powers.values():
            name = (p.get("power_name") or p.get("fields", {}).get("Power name") or p.get("name", "")).lower()
            slug = (p.get("slug") or "").lower()
            desc = (p.get("one_line_description") or p.get("fields", {}).get("One-line description") or "").lower()
            examples = (p.get("user_command_examples") or p.get("fields", {}).get("User command examples") or "").lower()

            if query_lower in name or query_lower in slug or query_lower in desc or query_lower in examples:
                results.append(p)
                if len(results) >= limit:
                    break

        return results[:limit]

    def list_categories(self) -> List[str]:
        # Return properly capitalized categories
        cats = set()
        for p in self.powers.values():
            c = p.get("category")
            if c:
                cats.add(c)
        return sorted(list(cats))

    def get_powers_by_category(self, category: str) -> List[Dict[str, Any]]:
        cat_key = category.strip().lower()
        pids = self.category_index.get(cat_key, [])
        return [self.powers[pid] for pid in pids if pid in self.powers]

    def get_powers_by_repo(self, repo_name: str) -> List[Dict[str, Any]]:
        r_key = repo_name.strip().lower()
        pids = self.repo_index.get(r_key, [])
        return [self.powers[pid] for pid in pids if pid in self.powers]

    def list_ecosystem_repos(self) -> List[str]:
        return sorted(list(self.repo_index.keys()))

    def get_ecosystem_formula(self) -> str:
        repos = self.list_ecosystem_repos()
        return "JARVIS = " + " + ".join(repos) + f" ({self.total_count()} powers)"

    def total_count(self) -> int:
        return len(self.powers) or len(INITIAL_POWERS)

# Singleton Power Registry
power_registry = PowerRegistry()
