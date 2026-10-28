# JARVIS Target Architecture: Personal AI Operating System

> **Reference Blueprint**: `JARVIS_Master_Edition.pdf` (Pages 420–426: Part C-Ref Reference Architecture & Governance)  
> **Repository Target**: `https://github.com/GaneshNair007/Jarvis.git`  
> **Core Model**: Local-First, Policy-Gated, Multi-Agent Hybrid Inference

---

## 1. High-Level Target Topology

```text
                               ┌──────────────────────────────────────────────┐
                               │     USER INTERACTION SURFACES                │
                               │  Voice / Glassmorphic HUD / Mobile / CLI     │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │             JARVIS GATEWAY                   │
                               │        FastAPI Core Daemon (:8000)           │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
        ┌─────────────────────────────┐                               ┌─────────────────────────────┐
        │     POLICY & SAFETY GATE    │                               │     COGNITIVE ENGINE        │
        │  • 4-Tier Approval Gate     │                               │  • LangGraph StateGraph     │
        │  • HMAC Frozen Tokens       │                               │  • Mem0 7-Layer Memory      │
        │  • Hardware Kill Switch     │                               │  • Multi-Agent Coordinators │
        │  • Immutable Audit Chain    │                               │  • Context Checkpointing    │
        └──────────────┬──────────────┘                               └──────────────┬──────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │           HYBRID MODEL ROUTER                │
                               │          LiteLLM Gateway (:4000)             │
                               │  Tier 1: Ollama Local (Llama 3.1 / Qwen 2.5) │
                               │  Tier 2: Private Mid-Tier (vLLM / Mistral)   │
                               │  Tier 3: Cloud Escalation (Claude / GPT-4o)  │
                               └──────────────────────┬───────────────────────┘
                                                      │
         ┌───────────────────────────┬────────────────┴───────────┬───────────────────────────┐
         ▼                           ▼                            ▼                           ▼
┌──────────────────┐       ┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
│ DESKTOP WORKER   │       │ BROWSER WORKER   │         │ LOCAL SEARCH     │        │ INTEGRATION HUB  │
│ • See-Act-Verify │       │ • Playwright DOM │         │ • SQLite FTS5    │        │ • GitHub MCP     │
│ • OS UI Auto     │       │ • Ephemeral Ctx  │         │ • Meilisearch    │        │ • System Diag    │
│ • Failsafe Edge  │       │ • SSRF Firewall  │         │ • Qdrant Vectors │        │ • Rate Limiter   │
│ • Window Focus   │       │ • Proof Checksum │         │ • Redis Cache    │        │ • Retry Policies │
└──────────────────┘       └──────────────────┘         └──────────────────┘        └──────────────────┘
```

---

## 2. Invariant Safety & Security Rules

1. **Deny-by-Default Execution**: Unclassified powers, unregistered tools, and undeclared network calls fail closed.
2. **Frozen Content Hash Approvals**: Approvals for Tier 2 and Tier 3 actions bind to the SHA-256 digest of the exact action payload. Any mutated parameter automatically voids the approval.
3. **No Blind Clicks or Silent Successes**: Every desktop and browser action follows the See-Act-Verify cycle:
   - Capture pre-action state (DOM / screenshot).
   - Execute targeted action.
   - Wait for observable change.
   - Capture post-action evidence and record cryptographic checksum in audit ledger.
4. **Zero-API Search Default**: Queries first search local indexed documents (FTS5 + Meilisearch + Qdrant) in milliseconds. Web lookups via SearXNG only occur upon explicit fallback and are immediately cached locally.
5. **DLP Pre-Sanitization**: All credentials, private keys, JWTs, and payment card numbers are redacted before touching memory, SQLite tables, or search indices.
