# JARVIS Verification & Test Plan

## Mandatory Automated Test Invariants
1. **Instant Command Bypass**: Commands like "Open VS Code", "volume up", or "disk usage" bypass LLMs with 0 tokens.
2. **Private Document Localization**: Tasks with sensitive documents or screen contexts stay strictly on Tier 1 (Ollama) or Tier 2 (vLLM).
3. **Secret Redaction**: API keys (`sk-...`), passwords, credit cards, and OTPs are redacted prior to cloud transmission.
4. **Deny-by-Default Policy Enforcement**: Level 3-5 operations (outbound emails, file deletes) are blocked without valid HMAC tokens.
5. **Cost Limit Blocking**: Calls exceeding per-task or daily budgets are blocked.
6. **Circuit Breaker Failover**: Provider failures trip breakers and route to local fallbacks.
7. **Audit Chain Cryptography**: Tampering with any log line invalidates the SHA-256 chain.
8. **Emergency Kill Switch**: Activating the kill switch immediately aborts tasks.
