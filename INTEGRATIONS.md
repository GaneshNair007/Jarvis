# JARVIS Universal Integration Layer Specification & Architecture

## 1. Overview
The JARVIS Integration Layer transforms the local-first JARVIS Personal AI Operating System into an enterprise-grade, extensible integration hub. It connects JARVIS to model providers (LiteLLM, Ollama, vLLM, OpenAI, Anthropic, Gemini, Groq, Mistral), cloud services (Google, Meta, GitHub, GitLab), browser automation, search engines, documents, smart home (Home Assistant), workflow automation (n8n), and MCP servers.

All integrations strictly adhere to the **Absolute Invariants**:
1. **Local-First & Disabled by Default**: Integrations are dormant until explicitly enabled by the user.
2. **Deterministic Approval Gating**: All outward-facing actions require Tier 2 approval; irreversible actions require Tier 3 step-up authentication.
3. **Cryptographic Binding**: Approvals are bound to a frozen SHA-256 content hash of execution parameters. If parameters change or the token expires, execution is blocked.
4. **Credential Isolation**: Secrets are never hardcoded, committed, logged, or placed in prompts. Missing credentials return structured setup instructions and documentation links—never simulated or faked success.
5. **Rate Limiting & Resilient Retries**: Enforces per-minute sliding token bucket limits and exponential backoff with jitter on transient failures.
6. **Immutable Audit Ledger**: All connection events, configuration changes, power executions, and dry runs produce append-only SHA-256 audit entries.
7. **Emergency Kill Switches**: Every integration and power has an immediate kill switch that halts all sub-processes instantly.

---

## 2. Architecture & Base Contracts

```
integrations/
├── __init__.py                  # Auto-discovery & registry initialization
├── base/
│   ├── __init__.py              # Base exports
│   ├── base_integration.py      # Abstract BaseIntegration contract
│   ├── integration_registry.py  # Central IntegrationRegistry singleton
│   ├── credential_manager.py    # Environment & secret vault lookup, redaction & setup guides
│   ├── oauth_manager.py         # Anti-CSRF OAuth lifecycle and token manager
│   ├── rate_limiter.py          # Sliding-window RPM rate limiter
│   ├── retry_policy.py          # Exponential backoff with jitter & error classification
│   └── integration_health.py    # HealthStatus enum and standardized Pydantic models
├── system/
│   └── system_diagnostics.py    # Zero-credential local diagnostics integration
├── github/
│   └── github_integration.py    # Developer integration with Tier 0-3 approval gates
└── [Phases 2-12 Modules...]     # Model providers, Google, Meta, Search, MCP, Home Assistant
```

### 2.1 The `BaseIntegration` Contract
Every integration inherits from `BaseIntegration` and must implement:
- `connect() -> Dict[str, Any]`: Verifies credentials and establishes connection.
- `disconnect() -> Dict[str, Any]`: Gracefully severs connection and revokes temporary state.
- `health_check() -> IntegrationHealth`: Reports `HEALTHY`, `DEGRADED`, `UNCONFIGURED`, `DISABLED`, or `KILL_SWITCHED`.
- `list_powers() -> List[Power]`: Declares all powers registered under this integration.
- `execute_power(power_id, params, approval_token) -> Dict[str, Any]`: Enforces kill-switch, status, rate-limit, policy gate (with frozen hash verification), and retry policy.
- `dry_run(power_id, params) -> Dict[str, Any]`: Simulates execution without performing external mutation, estimating blast radius, impact, and required approval tier.

---

## 3. Registered Integrations (Phase 1 Baseline)

| Integration ID | Display Name | Category | Status Default | Required Credentials | Powers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `system_diagnostics` | Local System Diagnostics | `system` | Enabled (`HEALTHY`) | None (Local host) | `system.health_probe`<br>`system.disk_diagnostics`<br>`system.clear_temp_cache` (Tier 2) |
| `github` | GitHub Platform | `developer` | Disabled (`UNCONFIGURED`) | `GITHUB_TOKEN` | `github.list_repos`<br>`github.search_code`<br>`github.create_issue_draft`<br>`github.create_issue` (Tier 2)<br>`github.merge_pr` (Tier 3) |

---

## 4. Phase-by-Phase Roadmap

- **Phase 1 (Complete)**: Integration Foundation (BaseIntegration, Registry, Credential Manager, OAuth Manager, Rate Limiter, Retry Policy, Health Checks, Kill Switch, Cryptographic Audit, Dynamic Power Registration, REST APIs, and HUD Integrations Tab).
- **Phase 2 (Pending Approval)**: Model Providers (LiteLLM unified gateway: Ollama, vLLM, OpenAI, Claude, Gemini, Mistral, Groq, Hugging Face, circuit breakers, fallback routing).
- **Phase 3**: Search and Research (DuckDuckGo, SearXNG, Wikipedia, arXiv, PubMed, GitHub search, Tavily/Brave optional, citation engine).
- **Phase 4**: Google Integrations (Google Drive, Calendar, Gmail, Sheets, Tasks, YouTube via official APIs and MCP).
- **Phase 5**: Developer Integrations (GitLab, Docker daemon, Linux server SSH/diagnostics).
- **Phase 6**: File and Document Intelligence (PDF, DOCX, XLSX, CSV, Tesseract OCR, faster-whisper, local RAG).
- **Phase 7**: Productivity Integrations (Notion, Obsidian, Todoist, Markdown knowledge base).
- **Phase 8**: Messaging Integrations (Slack, Discord, Telegram, Matrix, email drafts).
- **Phase 9**: Media Integrations (Whisper, ffmpeg, image generation, video brief generator).
- **Phase 10**: Smart Home (Home Assistant devices, scenes, climate, security alerts).
- **Phase 11**: Automation (n8n, Node-RED, cron scheduler, authenticated webhooks).
- **Phase 12**: Universal MCP Gateway (Universal client connecting to filesystem, Playwright, GitHub, and custom MCP servers).
