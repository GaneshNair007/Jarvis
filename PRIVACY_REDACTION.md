# JARVIS Local Search: Privacy & Sensitive Data Redaction Policy

## 1. Zero-Leakage Guarantee

JARVIS Local Search is engineered with strict data sanitation gates. 
Under **Non-Negotiable Rules 13, 14, and 15**:
- **Never index passwords, OTPs, API keys, private keys, or payment card numbers.**
- **Redact sensitive data BEFORE writing to SQLite, Meilisearch, or Qdrant.**
- **Respect `.gitignore`, allowed directory paths, and blocked directory paths.**

Because redaction occurs in memory *prior* to calculating the SHA-256 content hash and *prior* to inserting into any index or vector database, secrets are never written to disk, never vectorized, and never exposed in search snippets or citations.

---

## 2. Active Redaction Patterns

The ingestion pipeline (`search/ingestors/base_ingestor.py`) applies regular expression filters against every ingested stream:

| Secret Category | Matching Pattern | Redaction Token |
| :--- | :--- | :--- |
| **OpenAI / Anthropic Keys** | `(?i)sk-[A-Za-z0-9_-]{20,}` | `[REDACTED_API_KEY]` |
| **GitHub Personal Access Tokens** | `(?i)ghp_[A-Za-z0-9]{36}` | `[REDACTED_GITHUB_TOKEN]` |
| **AWS Access Key IDs** | `(?i)AKIA[0-9A-Z]{16}` | `[REDACTED_AWS_KEY]` |
| **JSON Web Tokens (JWT)** | `(?i)eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}` | `[REDACTED_JWT]` |
| **Private Keys (RSA/OpenSSH/EC)** | `-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` |
| **Credential Assignments** | `(?i)(password\|secret\|passwd\|token)\s*[:=]\s*["']?([^"'\s,;]{4,})["']?` | `$1: [REDACTED_SECRET]` |
| **Payment Card Numbers** | `\b(?:4[0-9]{12}(?:[0-9]{3})?\|5[1-5][0-9]{14}\|3[47][0-9]{13}\|6(?:011\|5[0-9]{2})[0-9]{12}\|(?:[0-9]{4}[ -]){3}[0-9]{4})\b` | `[REDACTED_CARD_NUMBER]` |

---

## 3. Directory & File Exclusion Policy

### Automatically Excluded Files
The repository and directory ingestors immediately drop any file matching:
- **Environment variables & secrets**: `.env`, `.env.*`, `*.pem`, `*.key`, `*.pkcs12`, `*.pfx`, `id_rsa`, `id_ed25519`
- **Binary executables & libraries**: `.exe`, `.dll`, `.so`, `.dylib`, `.bin`, `.iso`
- **Compressed archives**: `.zip`, `.tar`, `.gz`, `.7z`, `.rar`, `.bz2`
- **Package caches & build trees**: `node_modules/`, `target/`, `dist/`, `build/`, `.next/`, `vendor/`
- **VCS & metadata**: `.git/`, `.svn/`, `.hg/`, `.pytest_cache/`, `__pycache__/`

### Gitignore Respect
If a repository contains a `.gitignore` file, the `CodeRepoIngestor` parses the ignore rules using standard path matching and prevents any ignored file from being read or ingested.

---

## 4. Web Crawler Permission & Anti-Abuse Policies

Under Rules 16 and 17:
- **Permission Check**: JARVIS web cache and SearXNG clients only ingest user-provided URLs or explicitly permitted search queries.
- **No Anti-Bot Bypass**: JARVIS never attempts to bypass CAPTCHA, Cloudflare challenges, or anti-scraping countermeasures. If a page refuses standard HTTP retrieval, it is marked unreachable and skipped.
- **Local Cache**: Fetched web documents are stored locally with original source URLs, author timestamps, and content hashes for auditability.
