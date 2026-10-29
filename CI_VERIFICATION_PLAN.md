# CI Verification Plan for JARVIS Personal AI Operating System

This document specifies the exact command set used to verify code health, dependencies, security boundaries, and CI/CD readiness.

## 1. Verification Command Set

| Command | Purpose | Expected Result | Estimated Duration | Required Environment | Required Services | Failure Handling Approach |
|---|---|---|---|---|---|---|
| `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` | Critical syntax & undefined symbol linting | Exit code 0, 0 errors | ~3s | Standard Python | None | Inspect file, fix import/syntax error, re-run |
| `python -m py_compile ...` | Bytecode compilation across all Python packages | Exit code 0, all files compiled | ~5s | Python 3.11 / 3.12 | None | Identify file and line with syntax error and resolve |
| `pytest -v` | Complete acceptance and unit test suite | 105 passed, 0 failed | ~120s | `JARVIS_ENV=test`, `JARVIS_SECRET_KEY=test_key_32_bytes_ok`, `MEILISEARCH_MASTER_KEY=masterKey123` | Local mocks (Ollama/LiteLLM/Mem0/Redis) | Diagnose stack trace, verify mock/logic, re-run test isolated |
| `python -c "import json; from pathlib import Path; p = Path('config/policies/permissions.json'); assert p.exists(); data = json.loads(p.read_text('utf-8')); assert 'tiers' in data"` | Policy engine and permissions schema verification | Exit code 0, Permissions schema verified: OK | ~1s | None | None | Re-generate/validate permissions.json structure |
| `grep -rE "sk-ant-api03-[A-Za-z0-9_-]{80,}" jarvis/ search/ core/ tests/` | Outbound live Anthropic credential leak scan | 0 matches found | ~2s | None | None | Immediately flag key for rotation, remove from code |
| `grep -rE "sk-[A-Za-z0-9]{48}" jarvis/ search/ core/ tests/` | Outbound live OpenAI credential leak scan | 0 matches found | ~2s | None | None | Immediately flag key for rotation, remove from code |
| `docker compose config` | Docker Compose stack validation | Valid YAML configuration output | ~3s | `.env.example` copied to `.env` | Docker engine | Fix compose syntax, missing volume or environment mapping |
| `docker build -t jarvis-api:latest -f Dockerfile .` | Container build validation for JARVIS API | Successful image creation | ~90s | Docker engine | Docker engine | Check missing system packages in Dockerfile or pip deps |
| `docker build -t jarvis-dashboard:latest -f dashboard/Dockerfile dashboard/` | Container build validation for Nginx Dashboard | Successful image creation | ~15s | Docker engine | Docker engine | Check nginx.conf and index.html file paths |

## 2. Automated Trigger & Continuous Loop
Every git push to `main` or pull requests automatically trigger the 3 pipelines:
1. `CI Pipeline` (`ci.yml`) - Lint + Test Matrix (Python 3.11 & 3.12)
2. `Docker & Deployment Readiness` (`docker.yml`) - Compose config + API & Dashboard Docker builds
3. `Security & DLP Audit` (`security.yml`) - Permissions schema validation + Secret leak scanner
