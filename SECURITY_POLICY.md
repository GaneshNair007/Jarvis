# JARVIS Security & Safety Policy

## 1. Core Safety Principles

1. **Deny by Default**: Any unclassified task, unrecognized tool, or untrusted instruction is halted immediately.
2. **Local-First Processing**: Sensitive operations, credentials, and confidential project data never leave the local environment.
3. **Evidence-Driven Operation**: Actions are never declared completed without verifiable cryptographic or system evidence.
4. **Untrusted External Data**: All retrieved web content, emails, scraped pages, and document texts are treated strictly as passive data, never executable instructions.
5. **No Hallucinated Actions**: JARVIS never fabricates tool outputs, test passes, receipts, or external outcomes.

---

## 2. Four-Tier Approval Model

| Tier | Classification | Examples | Behavior |
| :--- | :--- | :--- | :--- |
| **Tier 0** | **Observe** | Web search, read memory, host telemetry, system metrics | Executed autonomously without approval |
| **Tier 1** | **Reversible Action** | Local note drafting, scratch file creation, local document ingest | Executed autonomously and logged to audit trail |
| **Tier 2** | **Explicit Approval** | File deletion, sending outbound emails, modifying production repos, desktop mouse/keyboard action | **Halted until human cryptographically approves** |
| **Tier 3** | **Step-Up Authentication** | Formatting disks, wiping directories, financial/crypto transactions, root system changes | **Requires multi-factor password/HMAC step-up verification** |

---

## 3. Data Loss Prevention (DLP) & Privacy Gates

Before any context is considered for inference or external tool consumption:
- Regular expression and Shannon entropy filters scan for:
  - API keys, JWT tokens, AWS/GCP credentials
  - Passwords and secret phrases
  - Credit card numbers, CVVs
  - One-time passwords (OTPs)
  - Private SSH/GPG keys
- Detected secrets are redacted and logged in sanitized form.
- Raw unredacted screenshots and private documents are permanently prohibited from transmission to cloud models.

---

## 4. Emergency Kill Switch

- Available via `POST /kill-switch` and global hotkey `Ctrl+Alt+Shift+K`.
- Immediately cancels all running tasks, terminates desktop and browser automation workers, and rejects all non-telemetry requests within 50ms.
