# JARVIS Internship Application Automation

This is a local-first discovery and application-preparation workflow. It does not mass-apply.

## Capabilities

- Public job-board discovery for explicitly configured Greenhouse, Lever and Ashby boards.
- Manual opportunity import for company career pages, startup websites, Wellfound, Internshala and LinkedIn.
- Deterministic keyword fit scoring. A fit score is alignment, not a probability of selection.
- Candidate profile extraction from a local PDF resume.
- Draft preparation and a human approval gate bound to the exact draft hash.
- SQLite persistence under the local data directory.
- Optional Ollama summaries of public job descriptions. Only job text is sent to the local Ollama daemon; candidate PII is not sent to the model.
- Daily ATS discovery through a Windows Task Scheduler task at 08:15 local machine time.

## Important limitations

- LinkedIn is manual-review only. JARVIS does not scrape LinkedIn or automate LinkedIn applications.
- Internshala and Wellfound are manual import/review sources. Do not use unofficial scraping or browser automation against their restrictions.
- Company careers and startup websites can be imported manually. Automatic crawling of arbitrary sites is not enabled.
- The initial version does not click the final external Submit button. After reviewing and approving a draft, the candidate completes the employer's form and final submission manually. The API never reports an application as submitted.
- CAPTCHA, MFA and anti-bot controls are not bypassed.
- Job-board discovery only runs for ATS board identifiers explicitly configured by the user.

## Windows setup

Run from the JARVIS repository root in PowerShell:

```powershell
git checkout feat/internship-application-automation
python -m pip install -e .
```

Import the resume. Use the actual path where the PDF is stored on this laptop:

```powershell
python scripts/import_candidate_resume.py "C:\path\to\Ganesh_Nair_Resume.pdf"
```

The script writes `data/candidate_profile.json`. That file is gitignored. Inspect it and correct any extraction errors before continuing. It includes contact information and a local resume path; do not commit or share it.

Set a unique local approval secret in the repository's `.env`. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add the output as `JARVIS_SECRET_KEY=...` in `.env`, replacing any existing value. Do not paste the secret into chat or commit it.

## Configure public ATS boards

Edit `config/internship_sources.yml` and add only board identifiers:

```yaml
boards:
  - provider: greenhouse
    board: example-company
  - provider: lever
    board: example-company
  - provider: ashby
    board: example-company
```

Remove unused examples. These are public endpoints; no account credentials are needed. Empty configuration safely performs no discovery.

## Start and verify

```powershell
python -m jarvis.main serve
```

Open the FastAPI documentation at `http://127.0.0.1:8000/docs`.

Check:

- `GET /api/v1/internships/status`
- `GET /scheduler/status`

Run a discovery pass:

- `POST /api/v1/internships/discover` with `{"boards":[{"provider":"greenhouse","board":"your-board"}]}`
- Or `POST /scheduler/trigger/internship_ats_discovery` after configuring `config/internship_sources.yml`.

Register the Windows task once from an elevated or normal PowerShell session (whichever permissions your Windows account allows):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_internship_task.ps1
```

The task runs daily at 08:15 according to the laptop's local clock. Its runner starts JARVIS if the local API is not already responding, triggers only the internship discovery job, and writes a timestamped result under `data/logs/`. It fails visibly if the API does not start, ATS boards are not configured or discovery returns errors. It does not submit applications.

## Manual source import

Use `POST /api/v1/internships/opportunities/manual` with a source value of:

- `company_careers`
- `startup_website`
- `wellfound`
- `internshala`
- `linkedin_manual`

Provide the company, title, HTTPS job URL, location and description. For LinkedIn, paste a job URL and details you are permitted to access manually.

## Prepare and approve

1. Review `GET /api/v1/internships/opportunities`.
2. Call `POST /api/v1/internships/applications/prepare` with an opportunity ID.
3. Inspect every field and cover letter in the returned draft.
4. If correct, call `POST /api/v1/internships/applications/{application_id}/approve` with the returned `review_hash` and `confirm: true`.
5. The API marks the draft `APPROVED_FOR_MANUAL_SUBMISSION`. Open the employer's official form, attach the resume and submit it yourself.
6. After the employer confirmation appears, optionally call `POST /api/v1/internships/applications/{application_id}/mark-submitted` with the one-time approval token, `confirm: true`, and a brief confirmation reference. This records a user attestation only; it is not independent proof and does not mean JARVIS submitted the form.

Approval is short-lived and tied to the exact draft hash. Editing the draft invalidates the approval. Rejection or stale approval does not submit anything.

## Troubleshooting

- `profile_configured: false`: rerun the PDF importer and verify the resume path exists.
- Approval fails due to secret: ensure `.env` contains a unique `JARVIS_SECRET_KEY` with at least 32 characters; restart JARVIS after changing it.
- Ollama unavailable: the workflow falls back to deterministic matching; local summaries are optional.
- No jobs discovered: verify the ATS board slug and provider; inspect errors returned by the discovery endpoint.
- Scheduled discovery not running: inspect Windows Task Scheduler task `JARVIS-Internship-Discovery` and the timestamped logs under `data/logs/`.

## Verification status

Repository changes are code/configuration only. They are not proof of installation on the Windows laptop. Run the checks above and the test suite locally before using the workflow.
