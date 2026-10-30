---
name: browser
description: Safe, privacy-preserving browser automation, URL content extraction, DOM reading, screenshot evidence capture, and autonomous multi-source deep web research without credential leakage. Triggered by /browser slash command.
metadata:
  icon: globe
---

# Browser & Safe Web Automation Skill

Use this skill to navigate the web safely, extract clean DOM text, capture verifiable screenshot artifacts with SHA-256 hashes, and conduct multi-document deep research with strict SSRF protection.

## Core Capabilities
- **URL Reading (`url_read` / PWR-014):** Extracts titles, headings, main content, and outbound links from any public HTTP/HTTPS webpage while blocking loopback or private subnet IP targets (SSRF protection).
- **Screenshot Evidence (`screenshot_capture` / PWR-015):** Captures high-resolution browser screenshots and writes cryptographic SHA-256 receipts to prevent tampering.
- **Deep Research (`deep_research` / PWR-063):** Queries web search engines, extracts evidence across multiple ranked sources, synthesizes Markdown reports with explicit citations, and caches results locally into the SQLite FTS5 search index.
- **Indirect Prompt Injection Containment:** Strips dangerous script tags, parses untrusted web input in sandboxed DOM readers, and logs injection markers into the cryptographic audit ledger.

## Usage Guide
Run via CLI or chat interface:
```bash
# Read and extract clean text from a URL
/browser read https://fastapi.tiangolo.com

# Deep research topic with verified citations
/browser research "Sub-millisecond local vector retrieval benchmarks"

# Take screenshot evidence of web application
/browser screenshot https://github.com/GaneshNair007/Jarvis
```

