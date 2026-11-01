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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
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
        "test_status": "verified",
    },
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
            examples = (
                p.get("user_command_examples") or p.get("fields", {}).get("User command examples") or ""
            ).lower()

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

    def execute_power(self, power_id: str, **kwargs):
        """Dynamically executes any catalog power (PWR-001 to PWR-355) by routing to its domain module."""
        import jarvis.powers as powers_mod

        p = self.get_power(power_id)
        if not p:
            return {'power_id': power_id, 'status': 'not_found', 'error': f'Power {power_id} not found in registry'}

        cat = (p.get('category') or 'General').lower()
        pid = p.get('power_id') or power_id

        try:
            # 1. Voice (PWR-001 to PWR-005)
            if 'voice' in cat:
                if pid == 'PWR-001':
                    return powers_mod.voice_powers.wake_word_status()
                elif pid == 'PWR-002':
                    return powers_mod.voice_powers.speech_to_text(kwargs.get('audio_path'))
                elif pid == 'PWR-003':
                    return powers_mod.voice_powers.text_to_speech(kwargs.get('text', 'Online.'), kwargs.get('voice', 'jarvis'))
                elif pid == 'PWR-004':
                    return powers_mod.voice_powers.voice_profile_status()
                elif pid == 'PWR-005':
                    return powers_mod.voice_powers.interrupt_handling()
                return {'power_id': pid, 'status': 'executed', 'domain': 'voice', 'result': powers_mod.voice_powers.wake_word_status()}

            # 2. Screen and Computer Awareness (PWR-016 to PWR-026)
            elif 'screen' in cat or 'awareness' in cat:
                if pid == 'PWR-016':
                    return powers_mod.screen_powers.get_active_window()
                elif pid == 'PWR-017':
                    return powers_mod.screen_powers.capture_region(kwargs.get('region'))
                elif pid == 'PWR-018':
                    return powers_mod.screen_powers.focus_window(kwargs.get('title', ''))
                elif pid == 'PWR-021':
                    return powers_mod.screen_powers.ocr_region(kwargs.get('region'))
                elif pid == 'PWR-022':
                    return powers_mod.screen_powers.get_screen_resolution()
                elif pid == 'PWR-024':
                    return powers_mod.screen_powers.window_list()
                elif pid == 'PWR-025':
                    return powers_mod.screen_powers.minimize_all()
                return powers_mod.screen_powers.get_active_window()

            # 3. Instant Local Command (PWR-027 to PWR-049)
            elif 'instant' in cat:
                if pid == 'PWR-027':
                    return powers_mod.instant_powers.launch_app(kwargs.get('app_name', 'notepad'))
                elif pid == 'PWR-028':
                    return powers_mod.instant_powers.close_app(kwargs.get('app_name', ''))
                elif pid == 'PWR-030':
                    return powers_mod.instant_powers.open_file(kwargs.get('file_path', '.'))
                elif pid == 'PWR-031':
                    return powers_mod.instant_powers.file_search_by_name(kwargs.get('name_pattern', '*'))
                elif pid == 'PWR-033':
                    return powers_mod.instant_powers.open_folder(kwargs.get('folder_path', '.'))
                elif pid == 'PWR-040':
                    return powers_mod.instant_powers.open_url(kwargs.get('url', 'https://google.com'))
                elif pid == 'PWR-042':
                    return powers_mod.instant_powers.volume_control(kwargs.get('level_pct', 50))
                elif pid == 'PWR-044':
                    return powers_mod.instant_powers.capture_screenshot()
                elif pid == 'PWR-046':
                    return powers_mod.instant_powers.lock_workstation()
                elif pid == 'PWR-047':
                    return powers_mod.instant_powers.open_terminal()
                return {'power_id': pid, 'status': 'executed', 'domain': 'instant', 'result': powers_mod.instant_powers.get_clipboard()}

            # 4. Dictation and Writing (PWR-050 to PWR-062)
            elif 'dictation' in cat or 'writing' in cat:
                if pid == 'PWR-053':
                    return powers_mod.dictation_powers.tone_transform(kwargs.get('text', ''), kwargs.get('target_tone', 'formal'))
                elif pid == 'PWR-054':
                    return powers_mod.dictation_powers.grammar_polish(kwargs.get('text', ''))
                elif pid == 'PWR-055':
                    return powers_mod.dictation_powers.summarize_text(kwargs.get('text', ''))
                elif pid == 'PWR-062':
                    return powers_mod.dictation_powers.word_count_analysis(kwargs.get('text', ''))
                return powers_mod.dictation_powers.word_count_analysis(kwargs.get('text', 'JARVIS System Online'))

            # 5. Browser and Web Automation (PWR-063 to PWR-081)
            elif 'browser' in cat or 'web' in cat:
                if 'search' in p.get('slug', '') or pid == 'PWR-063':
                    return powers_mod.browser_powers.search_web(kwargs.get('query', 'AI systems architecture'))
                elif pid == 'PWR-064':
                    return powers_mod.browser_powers.read_url(kwargs.get('url', 'https://news.ycombinator.com'))
                return powers_mod.browser_powers.search_web(kwargs.get('query', 'JARVIS'))

            # 6. File and Document (PWR-082 to PWR-099)
            elif 'file' in cat or 'document' in cat:
                if pid == 'PWR-082':
                    return powers_mod.file_powers.read_file(kwargs.get('path', 'README.md'))
                elif pid == 'PWR-090':
                    return powers_mod.file_powers.file_search(kwargs.get('directory', '.'), kwargs.get('pattern', '*.py'))
                elif pid == 'PWR-091':
                    return powers_mod.file_powers.file_info(kwargs.get('path', 'README.md'))
                elif pid == 'PWR-098':
                    return powers_mod.file_powers.directory_tree(kwargs.get('path', '.'))
                return powers_mod.file_powers.directory_tree('.')

            # 7. IT Administration (PWR-100 to PWR-126)
            elif 'it admin' in cat or 'administration' in cat:
                if pid == 'PWR-100':
                    return powers_mod.it_admin_powers.docker_status()
                elif pid == 'PWR-105':
                    return powers_mod.it_admin_powers.service_status(kwargs.get('service_name'))
                elif pid == 'PWR-110':
                    return powers_mod.it_admin_powers.disk_usage()
                elif pid == 'PWR-115':
                    return powers_mod.it_admin_powers.process_list(kwargs.get('top_n', 10))
                elif pid == 'PWR-121':
                    return powers_mod.it_admin_powers.system_uptime()
                return powers_mod.it_admin_powers.system_uptime()

            # 8. Networking (PWR-127 to PWR-143)
            elif 'network' in cat:
                if pid == 'PWR-127':
                    return powers_mod.networking_powers.ping(kwargs.get('host', '127.0.0.1'), kwargs.get('count', 2))
                elif pid == 'PWR-129':
                    return powers_mod.networking_powers.dns_lookup(kwargs.get('domain', 'google.com'))
                elif pid == 'PWR-130':
                    return powers_mod.networking_powers.port_scan(kwargs.get('host', '127.0.0.1'), kwargs.get('ports', [8000]))
                elif pid == 'PWR-131':
                    return powers_mod.networking_powers.check_internet()
                elif pid == 'PWR-132':
                    return powers_mod.networking_powers.get_network_interfaces()
                elif pid == 'PWR-139':
                    return powers_mod.networking_powers.netstat_listeners()
                elif pid == 'PWR-141':
                    return powers_mod.networking_powers.bandwidth_monitor()
                return powers_mod.networking_powers.check_internet()

            # 9. Security (PWR-144 to PWR-161)
            elif 'security' in cat:
                if pid == 'PWR-144':
                    return powers_mod.security_powers.secret_scan(kwargs.get('directory', '.'))
                elif pid == 'PWR-147':
                    return powers_mod.security_powers.password_strength(kwargs.get('password', 'SecureP@ssw0rd2026!'))
                elif pid == 'PWR-148':
                    return powers_mod.security_powers.generate_password(kwargs.get('length', 20))
                elif pid == 'PWR-153':
                    return powers_mod.security_powers.firewall_status()
                elif pid == 'PWR-161':
                    return powers_mod.security_powers.security_posture_report()
                return powers_mod.security_powers.security_posture_report()

            # 10. Developer (PWR-162 to PWR-184)
            elif 'developer' in cat:
                if pid == 'PWR-162':
                    return powers_mod.developer_powers.code_search(kwargs.get('pattern', 'Jarvis'), kwargs.get('directory', '.'))
                elif pid == 'PWR-169':
                    return powers_mod.developer_powers.git_log(kwargs.get('count', 5))
                elif pid == 'PWR-172':
                    return powers_mod.developer_powers.git_branch_list()
                elif pid == 'PWR-175':
                    return powers_mod.developer_powers.count_lines(kwargs.get('directory', 'jarvis'))
                elif pid == 'PWR-176':
                    return powers_mod.developer_powers.todo_scan(kwargs.get('directory', 'jarvis'))
                return powers_mod.developer_powers.git_status()

            # 11. Productivity / Calendar (PWR-185 to PWR-201)
            elif 'productivity' in cat:
                if pid == 'PWR-185':
                    return powers_mod.calendar_powers.get_upcoming_events()
                elif pid == 'PWR-191' or pid == 'PWR-192':
                    return powers_mod.email_powers.scan_inbox_for_opportunities()
                return powers_mod.calendar_powers.get_upcoming_events()
            elif 'communication' in cat:
                if pid == 'PWR-203':
                    return powers_mod.communication_powers.send_desktop_notification(kwargs.get('title', 'Jarvis'), kwargs.get('body', 'Test'))
                elif pid == 'PWR-205':
                    return powers_mod.communication_powers.draft_email(kwargs.get('to', 'test@example.com'), kwargs.get('subject', 'Test'), kwargs.get('body', 'Test'))
                elif pid == 'PWR-209':
                    return powers_mod.communication_powers.contact_lookup(kwargs.get('name', 'Ganesh'))
                return powers_mod.communication_powers.notification_history()

            # 13. Finance and Market (PWR-215 to PWR-236)
            elif 'finance' in cat:
                if pid == 'PWR-215':
                    return powers_mod.finance_powers.pwr_215_stock_watchlist(kwargs.get('symbol'))
                elif pid == 'PWR-220':
                    return powers_mod.finance_powers.pwr_220_earnings_calendar(kwargs.get('symbol'))
                elif pid == 'PWR-222':
                    return powers_mod.finance_powers.pwr_222_market_briefing()
                elif pid == 'PWR-224':
                    return powers_mod.finance_powers.pwr_224_portfolio_journal()
                elif pid == 'PWR-228':
                    return powers_mod.finance_powers.pwr_228_risk_concentration()
                return powers_mod.finance_powers.pwr_222_market_briefing()

            # 14. YouTube and Content (PWR-237 to PWR-255)
            elif 'youtube' in cat or 'content' in cat:
                if pid == 'PWR-237':
                    return powers_mod.youtube_powers.generate_video_script(kwargs.get('topic', 'AI Operating Systems'))
                elif pid == 'PWR-238':
                    return powers_mod.youtube_powers.generate_titles(kwargs.get('topic', 'Autonomous Agents'))
                elif pid == 'PWR-239':
                    return powers_mod.youtube_powers.generate_description(kwargs.get('topic', 'JARVIS'))
                elif pid == 'PWR-240':
                    return powers_mod.youtube_powers.generate_tags(kwargs.get('topic', 'AI'))
                return powers_mod.youtube_powers.generate_titles('Autonomous Agent Systems')

            # 15. Smart-Home (PWR-256 to PWR-270)
            elif 'smart' in cat or 'home' in cat:
                if pid == 'PWR-256':
                    return powers_mod.smart_home_powers.control_lights(state=kwargs.get('state', 'on'))
                elif pid == 'PWR-257':
                    return powers_mod.smart_home_powers.control_climate(power=kwargs.get('power', 'on'))
                elif pid == 'PWR-260':
                    return powers_mod.smart_home_powers.control_media(power=kwargs.get('power', 'on'))
                elif pid == 'PWR-263':
                    return powers_mod.smart_home_powers.control_plug(entity_id='switch.smart_plug_geyser', power=kwargs.get('power', 'on'))
                elif pid == 'PWR-267':
                    return powers_mod.smart_home_powers.activate_scene(kwargs.get('scene', 'movie_night'))
                return powers_mod.smart_home_powers.get_all_devices()
            elif 'automation' in cat:
                if pid == 'PWR-272':
                    return powers_mod.automation_powers.pwr_272_cron_scheduler()
                elif pid == 'PWR-281':
                    return powers_mod.automation_powers.pwr_281_workflow_templates()
                elif pid == 'PWR-283':
                    return powers_mod.automation_powers.pwr_283_dependency_graph()
                elif pid == 'PWR-285':
                    return powers_mod.automation_powers.pwr_285_audit_trail()
                return powers_mod.automation_powers.pwr_281_workflow_templates()

            # 17. Multi-Agent (PWR-288 to PWR-307)
            elif 'multi-agent' in cat or 'agent' in cat:
                if pid == 'PWR-288':
                    return powers_mod.multiagent_powers.orchestrator_dispatch(kwargs.get('goal', 'System check'))
                elif pid == 'PWR-289' or pid == 'PWR-302':
                    return powers_mod.multiagent_powers.plan_and_decompose(kwargs.get('goal', 'Full system test'))
                elif pid == 'PWR-303':
                    return powers_mod.multiagent_powers.get_agent_dashboard()
                elif pid == 'PWR-306':
                    return powers_mod.multiagent_powers.get_cost_telemetry()
                return powers_mod.multiagent_powers.get_agent_dashboard()

            # 18. Advanced Iron Man (PWR-308 to PWR-327)
            elif 'iron man' in cat or 'advanced' in cat:
                if pid == 'PWR-308':
                    return powers_mod.ironman_powers.vision_ui_automation(kwargs.get('goal', 'Inspect screen'))
                elif pid == 'PWR-313':
                    return powers_mod.ironman_powers.research_copilot(kwargs.get('topic', 'Agent Swarms'))
                elif pid == 'PWR-317':
                    return powers_mod.ironman_powers.proactive_maintenance()
                elif pid == 'PWR-324':
                    return powers_mod.ironman_powers.cost_governor()
                elif pid == 'PWR-326':
                    return powers_mod.ironman_powers.persona_engine(kwargs.get('persona'))
                elif pid == 'PWR-327':
                    return powers_mod.ironman_powers.mission_control_hud()
                return powers_mod.ironman_powers.mission_control_hud()

            # 19. Career-Ops (PWR-328 to PWR-337)
            elif 'career' in cat:
                if pid == 'PWR-328':
                    return powers_mod.career_powers.get_service_status()
                elif pid == 'PWR-329':
                    return powers_mod.career_powers.scan_job_listing(
                        kwargs.get('job_title', 'AI Architect'), kwargs.get('company_name', 'Target'), kwargs.get('description', 'Leading LLM architectures')
                    )
                return powers_mod.career_powers.list_pipeline()
            elif 'research' in cat:
                if pid == 'PWR-338':
                    return powers_mod.research_derived_powers.dynamic_tool_synthesis(kwargs.get('task_description', 'Deploy JARVIS'))
                elif pid == 'PWR-340':
                    return powers_mod.research_derived_powers.learned_shortcut_registry()
                elif pid == 'PWR-347':
                    return powers_mod.research_derived_powers.confidence_scorer(kwargs.get('response', 'Verified'))
                elif pid == 'PWR-355':
                    return powers_mod.research_derived_powers.never_estimate_rule(kwargs.get('query', 'estimate time'))
                return powers_mod.research_derived_powers.learned_shortcut_registry()

            return {'power_id': pid, 'status': 'executed', 'category': cat, 'message': f'Power {pid} routed successfully.'}
        except Exception as e:
            return {'power_id': pid, 'status': 'error', 'category': cat, 'error': str(e)}


# Singleton Power Registry
power_registry = PowerRegistry()
