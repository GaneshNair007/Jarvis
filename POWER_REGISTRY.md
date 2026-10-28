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

## 2. Power Master Catalog

In addition to the 10 initial powers, JARVIS includes the complete **355-power catalog** indexed across 12 operational domains:
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

## 3. Power Management Endpoints

- `GET /powers`: Lists active powers and catalog summary.
- `GET /powers?search={query}`: Searches powers by keyword or trigger.
- `POST /powers/{power_id}/enable`: Enables a power.
- `POST /powers/{power_id}/disable`: Disables a power.
