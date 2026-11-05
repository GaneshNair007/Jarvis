# JARVIS Repository Audit & Architecture Inventory

## 1. Project Overview & Layout

JARVIS is a local-first, screen-first, voice-driven multi-agent personal operating system designed to run without paid external search APIs.

### Directory Structure & Responsibilities
- **`jarvis/`**: Core runtime package
  - `agents/`: Swarm coordination and multi-agent roles (`AgentSwarmCoordinator`)
  - `api/`: FastAPI server and route controllers (`/api/v1/system`, `/career`, `/browser`, `/desktop`, `/memory`, `/search`, `/tasks`, `/voice`)
  - `browser/`: Ephemeral Chromium session management, DOM extraction, SSRF protection, screenshot evidence
  - `career/`: ATS resume generator, cover letter builder, company research dossiers, contact finder, salary negotiation
  - `computer/`: Desktop See-Act-Verify worker with Win32 / headless fallback and SHA-256 screenshot evidence
  - `core/`: Model router, cost governor, cryptographic audit ledger, policy engine, policy gate, privacy gate, power registry
  - `memory/`: 5-layer memory vault (working, episodic, semantic, procedural, core directive), SQLite + Mem0
  - `powers/`: 355-power catalog divided into 22 domain modules
  - `voice/`: Wake word detector, local STT, local TTS WAV synthesis, full-duplex barge-in pipeline
- **`search/`**: Millisecond local search engine
  - SQLite FTS5 indexer, Tantivy / Meilisearch client, Qdrant / semantic vector search, deduplicating hybrid ranker
  - Ingestors: chat history, code repo, email, local files, markdown, notes, PDF, web cache
- **`dashboard/`**: Local HUD interface
  - Nginx configuration, Dockerfile, static HTML5/CSS3/vanilla JS HUD for system monitoring, career ops, swarm telemetry
- **`tests/`**: Comprehensive test suite (146 test cases across 21 test modules)
- **`.agents/skills/`**: Standard Antigravity agent skills (`browser`, `generative_ui`, `automation`, `plugin`, `migrate-workflows`, `jarvis-architecture`, `jarvis-policy-security`, `jarvis-power-implementation`, `jarvis-local-search`, `jarvis-ci-verification`)
- **`.github/workflows/`**: Hardened GitHub Actions CI/CD pipelines

---

## 2. Technology Stack & Runtime Dependencies

| Layer | Technologies |
|---|---|
| **Python Runtime** | Python 3.11 / Python 3.12 |
| **API Framework** | FastAPI, Uvicorn, Pydantic v2, HTTPX |
| **Database & Cache** | SQLite (with FTS5), PostgreSQL (psycopg3, SQLAlchemy 2.0), Redis |
| **Storage & Migrations** | Alembic database migrations |
| **Browser & Automation** | Playwright Chromium, PyAutoGUI, Pillow |
| **Search & Ingestion** | PyMuPDF, SQLite FTS5, scikit-learn (cosine similarity) |
| **Configuration & Parsing** | PyYAML, python-dotenv |
| **Quality & CI Tooling** | Ruff (linting & formatting), Pytest, Pytest-Asyncio, Pytest-Cov, Pytest-Timeout, Pip-Audit |

---

## 3. Entry Points & Operational Commands

### 3.1 Installation & Bootstrap
```bash
# Production dependencies
pip install -r requirements.txt

# Development and CI dependencies
pip install -r requirements-ci.txt

# Playwright browser binaries
python -m playwright install --with-deps chromium
```

### 3.2 Running the Application
```bash
# Start FastAPI backend
uvicorn jarvis.api.server:app --host 0.0.0.0 --port 8000 --reload

# Start CLI entry point
python -m jarvis.main
```

### 3.3 Running Verification & Quality Gates
```bash
# Format check
python -m ruff format --check .

# Linting
python -m ruff check .

# Full test suite with coverage
python -m pytest tests --cov=. --cov-config=.coveragerc --cov-report=term-missing
```

---

## 4. Current Test Suite Coverage

- **Total Test Cases**: 146
- **Pass Rate**: 100% (146 passed, 0 failed)
- **Coverage Target**: $\ge 75\%$ enforced via `.coveragerc` and `--cov-fail-under=75`.
- **Zero API Dependency**: 100% of unit and acceptance tests execute offline without requiring internet access or paid LLM/search API keys.

