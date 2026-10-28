# JARVIS Security & Governance Policy

## Invariant 1: Deny-by-Default
No power or tool may execute without explicit clearance from the `PolicyGate`. Unregistered actions or ambiguous parameters are rejected immediately.

## Invariant 2: Privilege Levels
- **Level 0 (Public Read)**: Public web information. Zero approval required.
- **Level 1 (Local Non-Sensitive Read)**: Local files and performance metrics. Zero approval required.
- **Level 2 (Approved Local Write)**: Appending to local notes, writing scratch files. Logged.
- **Level 3 (Outbound Communication)**: Sending emails, posting messages, webhooks. **Mandatory Human Approval**.
- **Level 4 (System Modifications)**: Modifying network, installing system packages. **Mandatory Human Approval**.
- **Level 5 (Irreversible Operations)**: Deleting files, code deployment, financial transactions. **Mandatory Cryptographic Approval (HMAC-SHA256)**.

## Invariant 3: Data Loss Prevention (DLP)
The `PrivacyGate` intercepts all prompt text and context attachments:
- Passwords, OTPs, API keys, private keys, credit cards, and PII are redacted prior to model transmission.
- Unredacted private documents and raw screenshots are strictly prohibited from external cloud routes.

## Invariant 4: Fail-Safe Kill Switch
- Triggering `kill_switch_active` halts all active sub-processes and blocks all pending tasks within 50ms.
