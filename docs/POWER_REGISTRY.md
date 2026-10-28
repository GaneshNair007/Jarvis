# JARVIS Power Registry & Capability Specification

JARVIS organizes all autonomous operating capabilities into an extensible power registry. Each power declares strict metadata regarding permissions, danger level, approval requirements, triggers, inputs, and outputs.

---

## 1. Initial Milestone 1 Powers

| Power ID | Power Name | Category | Danger Level | Approval Required | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `PWR-CHAT` | `chat` | Core Assistant | None | No | Conversational turn with LangGraph & Mem0 recall |
| `PWR-MEM-SEARCH` | `memory_search` | Memory Vault | None | No | Searches long-term semantic memory and standing directives |
| `PWR-MEM-ADD` | `memory_add` | Memory Vault | Low | No | Stores user fact or preference into long-term vault |
| `PWR-MEM-DELETE` | `memory_delete` | Memory Vault | Medium | **Yes** | Deletes specific memory node or standing preference |
| `PWR-TASK-CREATE` | `task_create` | Task Engine | Low | No | Triages, plans, and queues an autonomous workflow task |
| `PWR-TASK-STATUS` | `task_status` | Task Engine | None | No | Retrieves execution status, logs, and artifacts of a task |
| `PWR-WEB-RESEARCH` | `web_research` | Research Engine | None | No | Autonomous multi-source web research with Markdown synthesis |
| `PWR-URL-READ` | `url_read` | Browser Automation | None | No | Extracts clean text & DOM layout from web page safely |
| `PWR-DOC-INGEST` | `document_ingest`| Memory Vault | Low | No | Ingests local PDF/TXT file and chunks for RAG |
| `PWR-DOC-QUERY` | `document_query` | Memory Vault | None | No | Retrieves exact page-cited answers from local document index |

---

## 2. Dynamic Integration Powers (Phase 1 Expansion)

Every integration loaded via `integrations/` dynamically registers its powers into `PowerRegistry`:

| Power ID | Power Name | Integration | Category | Danger Level | Approval Policy | Required Scopes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `system.health_probe` | System Health Probe | `system_diagnostics` | `system` | `low` | None (Tier 0) | `system.read` |
| `system.disk_diagnostics` | Disk Space Diagnostics | `system_diagnostics` | `system` | `low` | None (Tier 0) | `system.read` |
| `system.clear_temp_cache` | Clear Temporary Cache | `system_diagnostics` | `system` | `high` | **Tier 2 Approval** (SHA-256 bound) | `system.admin` |
| `github.list_repos` | List GitHub Repositories | `github` | `developer` | `low` | None (Tier 0) | `repo:read` |
| `github.search_code` | Search GitHub Code | `github` | `developer` | `low` | None (Tier 0) | `repo:read` |
| `github.create_issue_draft` | Draft GitHub Issue | `github` | `developer` | `low` | None (Tier 1) | `issues:write` |
| `github.create_issue` | Create GitHub Issue | `github` | `developer` | `medium` | **Tier 2 Approval** (SHA-256 bound) | `issues:write` |
| `github.merge_pr` | Merge Pull Request | `github` | `developer` | `extreme` | **Tier 3 Step-Up Auth** | `repo:admin` |

---

## 3. Power Master Catalog

In addition to initial and integration powers, JARVIS includes the complete **355-power catalog** indexed across 12 operational domains:
1. Core Assistant Powers (`PWR-001` to `PWR-015`)
2. Screen & Computer Awareness Powers (`PWR-016` to `PWR-035`)
3. Instant Local Command Powers (`PWR-036` to `PWR-065`)
4. Dictation & Writing Powers (`PWR-066` to `PWR-090`)
5. Browser & Web Automation Powers (`PWR-091` to `PWR-125`)
6. File & Document Intelligence Powers (`PWR-126` to `PWR-160`)
7. IT Administration & Server Powers (`PWR-161` to `PWR-195`)
8. Networking & Connectivity Powers (`PWR-196` to `PWR-225`)
9. Development & Code Engine Powers (`PWR-226` to `PWR-260`)
10. Multi-Agent Delegation Powers (`PWR-261` to `PWR-295`)
11. Personal Organization & Calendar Powers (`PWR-296` to `PWR-325`)
12. Security, Audit & Safety Powers (`PWR-326` to `PWR-355`)

---

## 4. Power Management Endpoints

- `GET /powers`: Lists active powers and catalog summary (including all integration powers).
- `GET /powers?search={query}`: Searches powers by keyword or trigger.
- `POST /powers/{power_id}/enable`: Enables a power.
- `POST /powers/{power_id}/disable`: Disables a power.
- `GET /integrations/{id}/powers`: Lists powers strictly scoped to an integration.
- `POST /integrations/{id}/powers/{power_id}/execute`: Executes an integration power behind rate limits and approval gates.
- `POST /integrations/{id}/powers/{power_id}/dry-run`: Simulates power execution with blast radius analysis and evidence.
