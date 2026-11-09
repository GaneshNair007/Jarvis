---
name: jarvis-policy-security
description: Enforces zero-trust policy decisions, cryptographic approval tokens, PII redaction, user isolation, emergency kill switch checks, and tamper-evident audit logging. Use when inspecting, modifying, or creating secure endpoints, outbound integrations, or sensitive data paths.
---

# JARVIS Policy and Security Framework

## Overview
Every operational power and user request in JARVIS passes through the security triad:
`PrivacyGate` -> `PolicyGate` -> `AuditLedger`.

## Core Security Requirements
1. **Zero-Trust Policy Enforcement (`jarvis/core/policy_gate.py`)**:
   - High-impact or destructive actions (Tier 2 and Tier 3) require explicit user approval.
   - Prohibited or unclassified actions must fail closed (`ALLOW_ACTION = False`).
   - Emergency kill switch must be evaluated before dispatching side effects: `policy_gate.is_kill_switch_active()`.
2. **Cryptographic Approval Binding**:
   - Approvals are cryptographically bound to the SHA-256 hash of the exact payload: `payload_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()`.
   - Any modification to task target, arguments, or parameters immediately invalidates the token.
3. **Data Loss Prevention & Redaction (`jarvis/core/privacy_gate.py`)**:
   - All text leaving or entering the system is scanned with regex rules for API keys, SSH secrets, credentials, and PII.
   - Sensitive findings are replaced with deterministic tags (`[REDACTED_API_KEY]`, `[REDACTED_EMAIL]`).
4. **User & Memory Isolation**:
   - User memory layers (`jarvis/memory/layers.py`) strictly partition data by `user_id`.
   - Cross-tenant or cross-user memory retrieval is blocked at the database and query layer.
5. **Tamper-Evident Audit Ledger (`jarvis/core/audit.py`)**:
   - Every action, approval, denial, and failure is recorded in a hash-chained ledger.
   - Hash chain integrity is verified via `audit_ledger.verify_chain_integrity()`.

## Verification Commands
```powershell
python -m pytest tests/test_policy_gate.py tests/test_privacy_gate.py tests/test_audit.py -v
```
Ensure all security assertions hold without mock bypasses.

