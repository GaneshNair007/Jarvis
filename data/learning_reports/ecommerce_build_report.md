# E-commerce Build Report — Astra Store

**Date:** 2026-11-05
**Project:** `D:\jarvis\apps\ecommerce-astra\` (Astra Store)

## What I built
Single-deployable FastAPI app (`main.py`): SQLite-backed product catalog (8 seeded items), search + category filter, product detail pages, cart in localStorage, checkout form that POSTs to `/api/orders`, order history page, JSON API (`/api/products`, `/api/products/{id}`, `/api/orders`, `/api/orders/{id}`), `/health`, Jinja2 HTML pages + vanilla JS/CSS (no build step), `Procfile` (`web: python main.py`), `runtime.txt`, `requirements.txt`, `README.md`, pytest suite in `tests/test_app.py`.

## What worked
- FastAPI, uvicorn, pydantic, jinja2, pytest all already installed in the environment (verified versions before writing code) — zero installs needed.
- All 6 pytest tests passed first run: health, product list, search/filter, detail, order create+history, home page render (`6 passed in 0.82s`).
- Live smoke test via `Start-Job` + curl passed: `/health` → `{"status":"ok","service":"astra-store"}`, `/api/products` → 8 products, order POST → `{"id":1,"total":89.99,...}`.

## What failed
- Nothing failed. One hygiene step: removed test `astra.db`/`test.db` artifacts after runs so the repo ships clean (DB re-seeds on boot).

## How to run
```bash
pip install -r requirements.txt
python main.py   # http://localhost:8000, PORT env respected
python -m pytest -q
```
Deploy (Render, not done yet): Build `pip install -r requirements.txt`, Start `python main.py`, health check `/health`.

## Inferred playbook (next time)
1. Probe environment first (`python -c "import fastapi"`, versions) before assuming installs.
2. Build as ONE app: FastAPI mounts templates/static, SQLite file DB with seed-on-first-boot, `PORT`-aware `if __name__ == "__main__"` block.
3. Templates: `base.html` + one per page; cart logic in one small `app.js` (localStorage), checkout form posts to the same JSON API the tests exercise.
4. Tests first-class: TestClient hitting the real API (health, CRUD-ish order flow, page render smoke) — catches wiring bugs immediately.
5. Verify with a real server (`Start-Job` + curl) not just tests; capture verbatim output as proof.
6. Ship Render-ready artifacts from day one: Procfile, runtime.txt, PORT handling, `/health`, README with build/start commands.
7. Clean DB artifacts before finishing; leave deploy as the explicit next step.
