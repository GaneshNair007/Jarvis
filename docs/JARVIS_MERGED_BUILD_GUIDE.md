# JARVIS Merged Build Guide: Every Line Upgraded

Prepared 1 November 2026 for the JARVIS project (private, single-user, local-first). This file merges five source files with your existing blueprint, Power Catalog (PWR-001 to PWR-355) and Antigravity master prompt.

Format used everywhere below: **what the source line says (short paraphrase) → the upgraded line for your JARVIS.** Short quotes are marked with quotation marks.

---

## 0. Verdict: do the files match your project?

| # | File | Match | What I used | What I dropped |
|---|------|-------|-------------|----------------|
| 1 | JARVIS Desktop App Only Guide (3 pp) | **Strong** | Whole flow: repo → Code session → localhost UI → "Hey Jarvis" | The "approve whatever is safe" mindset (replaced by rules) |
| 2 | JARVIS Stage 01 Ayman Guide (3 pp) | **Strong** | Voice base, ElevenLabs option, smart-room layer | Mac-only assumption, shell-exported key |
| 3 | JARVIS Stage 01 Build Guide (3 pp) | **Strong (overlaps #2)** | Download/run/voice/room steps (merged with #2, duplicates removed) | "Download ZIP" as the install method |
| 4 | Grok Bot Business Playbook (9 pp) | **Partial: method yes, product no** | Agent charter, read-only first, manual → skill → routine, source stamps, "never estimate", time ledger | The product itself, its ad/lead-sales framing, cloud-only storage |
| 5 | 200 AI Business Ideas (docx, 200 cards) | **Weak: 23 of 200 cards map to JARVIS** | 23 cards turned into powers (section 6) | The other 177 (client-service businesses in retail, health, legal, etc.) |

Why the split: files 1–3 describe the same thing you are building (a voice-first JARVIS with a local bridge and smart-room control). File 4 is a method guide for a different product, and its method matches your blueprint's approvals and skills. File 5 is a business catalogue; only the agent, IT and research ideas overlap.

**Not verified:** I could not open the repo `github.com/adewaskar/jarvis` (my fetch was blocked and a search did not surface it). Everything about what the repo contains (holographic UI, local bridge, port 5173, Node 20+, ElevenLabs fallback to browser speech) comes only from the three guides. Section 8 turns that into an audit step before you run anything.

---

## 1. Upgrade rules applied to every line

1. **Local-first.** Private audio, screens, files and memory stay on your machine unless a power says otherwise and labels where the data goes.
2. **Audit before run.** Third-party code is untrusted until reviewed.
3. **Deny by default; the policy gate decides**, never the browser, never the model.
4. **Approval bound to the exact action**, expiring in minutes.
5. **Evidence, not claims.** "Command sent" is not "device is on."
6. **Secrets in a keychain/vault**, never in chat, prompts, logs or git.
7. **Read-only first**, then draft, then act.
8. **One orchestrator, small concurrency**, kill switch always working.

---

## 2. Source 1: Desktop App Only Guide, line by line

| Source line | Upgraded line for your JARVIS | Maps to |
|---|---|---|
| "Build JARVIS from Claude Desktop." | Build JARVIS in a sandboxed workspace on a branch (Claude Desktop Code session in **Local** mode, or Antigravity), with every command visible to you. | Master prompt §3, §11 |
| "No cloning commands, no PowerShell, no Terminal." | You may skip *typing* commands, but not *reading* them. Approve each proposed command and keep a run log in `docs/runlog.md`. | PWR-285 audit |
| "Claude Code is available in Claude Desktop on supported paid plans." | Check your plan first. Your Claude account here is on the **free plan**, so if Code is unavailable, run the same steps in Antigravity with the master prompt. | Section 9, conflict 6 |
| Step 1: download Claude Desktop (claude.com/download) | Download only from the official site, typed by hand, not from an ad or a search result. | PWR-345 |
| Step 2: open, sign in | Use your own account; do not share the session with other people or other machines. | Rule 3 |
| Step 3: open the Code tab, New session | Name the session `jarvis-stage01-audit`. Choose the **Local** environment so `localhost` is your machine. If a session runs in the cloud, `localhost:5173` will not be your computer. | PWR-356 |
| "GitHub repo adewaskar/jarvis" | Record owner, license, last-commit date and the **pinned commit hash** in `docs/ADR-001-base-repo.md`. Unverified until you check it. | PWR-356 |
| "Claude Desktop can start a Code session with a GitHub repository selected." | Select the repo **read-only** for the audit. Fork it before you edit anything. | PWR-356 |
| "The repository is not installed by you manually… Claude Code is the thing you use." | The repo is still third-party code running with your permissions. Claude helps you inspect it; you own the risk. | Rule 2 |
| "Choose Code mode so Claude can inspect and edit." | Start in read-only/plan mode for the audit. Switch to edit mode only after the audit report is approved. | PWR-361 |
| Prompt 1: "Read the README first." | Read README, LICENSE, `package.json` (scripts and install hooks) and list every outbound network call and every tool the bridge can execute. | PWR-356 |
| Prompt 2: "Check the required Node.js version." | Check Node 20+ via a version manager (nvm/fnm) so you can pin it, and confirm a lockfile exists. | Stage 01 needs |
| Prompt 3: "Install the project dependencies." | Install with scripts disabled first (`npm ci --ignore-scripts`), run `npm audit`, review any package with install scripts, then enable them. | PWR-154 |
| Prompt 4: "Run the project's setup/check if needed." | Read what `npm run setup` does before running it (it may write config, fetch files or start services). | PWR-356 |
| Prompt 5: "Start the JARVIS UI locally." | Start it bound to `127.0.0.1` only and confirm nothing listens on all interfaces. | PWR-357 |
| Prompt 6: "Tell me exactly what I should click next." | Print a checklist with the expected result for each click and a stop condition if it differs. | PWR-026 |
| Prompt 7: "Do not make unrelated changes." | Edits only on a branch; show the diff before any commit; no change to bridge tool permissions without my approval. | PWR-175 |
| "Keep everything beginner-friendly." | Plain language, but always show the exact command and why, so the log is a real audit trail. | PWR-285 |
| "Claude should do the technical work; you follow the on-screen approvals." | Approvals are not rubber stamps. Deny anything touching `~/.ssh`, keychains, browser profiles, shell startup files or paths outside the project. | Rule 3 |
| "Review the request and approve the safe project actions." | Define "safe" in advance. Allow node/npm inside the project folder. Deny piped-to-shell installs, `sudo`, global installs and writes outside the project. | PWR-361 |
| "Switch to a normal Chrome or Edge window." | Use a **dedicated browser profile** for JARVIS: no signed-in accounts, no extensions, mic permission only for localhost. | PWR-357 |
| "The repo's standard URL is http://localhost:5173." | Trust the port the terminal prints. If it differs, or the host is not localhost/127.0.0.1, stop and check. | PWR-357 |
| "Do not use an embedded preview pane." | Keep this. Wake word and microphone need a real browser window, and it stops a preview pane from holding the mic. | PWR-001 |
| "Click INITIALISE." | Treat INITIALISE as the moment the bridge starts accepting commands. First run in **echo-only mode**, where every tool returns a dry-run result. | PWR-280 |
| "Allow microphone access." | Allow for `localhost` only. The HUD shows a mic indicator, and you revoke the permission after testing. | PWR-001 |
| "Say: Hey Jarvis." | Test 10 wake attempts including TV/other-voice noise; log false accepts/rejects; keep push-to-talk as fallback. | PWR-001, 002 |
| "Looks right but doesn't hear you." | Troubleshooting order: real browser → mic permission → OS input device → tab not muted → no other app holding the mic → extension conflicts. | PWR-001 |
| "Browser = holographic face + voice. Local bridge = brain + tools." | Browser = Zone 3 "face" with **zero authority**. Bridge = controller enforcing policy; tools run in a worker with an allow-list. The browser never holds secrets or decides permissions. | Architecture §4 |
| "Source check: README, docs, 06 Oct 2026." | Re-check README and docs on the day you build; store the check date in the ADR. Guides go stale quickly. | PWR-345 |

---

## 3. Source 2 + 3: Stage 01 guides (merged, duplicates removed)

Tags: **[A]** = Stage 01 Ayman Guide, **[B]** = Stage 01 Build Guide.

### 3.1 Overview and prerequisites

| Source line | Upgraded line | Tag |
|---|---|---|
| "Build your own J.A.R.V.I.S.: a beginner-friendly path from repo to a working voice assistant on your Mac, then into a smarter room." | Stage 01 = voice + local execution + room control, built as a **base**, not the final system. Policy, approvals and audit come right after (Milestone D). | A, B |
| "Mac / local machine." | The guides assume a Mac. Fill in your real OS in the master prompt; BroadLink and Wi-Fi plugs work on any OS, but startup and permissions steps differ on Windows/Linux. | A, B |
| "Claude Code: installed + signed in / brain-runtime." | Claude Code or Antigravity is the **builder**. At runtime the brain is your controller plus a model router, so building tools and running JARVIS stay separate. | A, B |
| "Node.js version 20+." | Pin Node 20+ with a version manager and commit a `.nvmrc`. | A, B |
| "Chrome / Edge: a real browser window." | Dedicated profile, no extensions, not an editor preview pane. | A, B |
| "ElevenLabs: optional, for the upgraded voice." | Make **voice provider a setting**, not a dependency: local (Piper/Kokoro) default for private text, ElevenLabs only for non-sensitive replies. | A, B |
| "Flow: Repo → Claude Code → ElevenLabs → Local Mac → Hey Jarvis." | Flow: **Audit repo → sandbox → base run (echo-only) → pick voice provider → harden bridge → wake test → lights-only room test.** | A, B |
| "Download the base repository: the one I used as a starting point." | The base is a starting point, not a product. The author's own build may have changed; pin the commit you audited. | B |

### 3.2 Get it running

| Source line | Upgraded line | Tag |
|---|---|---|
| "01 Open Claude Code: `claude`." | Open your agent workspace on a new branch and confirm the working tree is clean before touching anything. | A |
| "01 Download the GitHub repo: Code → Download ZIP, unzip." | A ZIP has no history, so you cannot diff future updates. Prefer a fork + clone at a pinned commit and note the hash. | B |
| "02 Give Claude the repo: set up this project, read the README, check prerequisites first." | Replace with an **audit-first prompt**: *"Audit github.com/adewaskar/jarvis read-only. Report license, last commit, dependencies with install scripts, every network call, every tool the bridge exposes and how it authenticates. Do not install or run anything until I approve the audit."* | A |
| "02 Open the unzipped folder in Claude Code; install dependencies, run the setup check." | After the audit passes: `npm ci --ignore-scripts`, review, then run setup. Log each command. | B |
| "03 Let Claude install it: `npm install`, `npm run setup`." | Same, with scripts disabled first and the lockfile respected. | A |
| "03/04 Connect/Add ElevenLabs: create an API key, add as `ELEVENLABS_API_KEY`." | Store the key in the OS keychain or a git-ignored `.env`; add pre-commit secret scanning; set a spend limit in the provider dashboard if it offers one; revoke and rotate if it ever appears in chat or a log. | A, B |
| "Copy it once. `export ELEVENLABS_API_KEY="PASTE_KEY_HERE"`." | Exporting in a shell can leave the key in shell history. Use a hidden prompt or keychain, and unset after the session. | B |
| "Keep this key private. Never commit it to GitHub." | Keep. Add: the key never appears in prompts, screenshots sent to a model, or the audit log (redact on write). | A, B |
| "The project can fall back to browser speech without it." | Label every voice path with where data goes: **browser speech** (often processed by the browser vendor's cloud; verify for this repo), **ElevenLabs** (your reply text is sent to a third party), **local Piper/Kokoro** (stays on the device). | A |
| "04/05 Start JARVIS: `npm start`, open the printed localhost URL." | Start bound to `127.0.0.1`, confirm the printed host, open in the dedicated profile. | A, B |
| "Final click: INITIALISE → allow microphone → say Hey Jarvis." | INITIALISE (echo-only) → allow mic for localhost → wake test x10 → push-to-talk check → kill-switch test. That is the Stage 01 gate. | A, B |
| "The one thing to remember: GitHub, ElevenLabs optional, Chrome/Edge normal window." | The one thing to remember: **nothing the browser says can authorise an action; the bridge decides.** | A |

### 3.3 Smart-room layer

| Source line | Upgraded line | Tag |
|---|---|---|
| "Now make the room smart. JARVIS runs on your Mac; the Mac is the local layer." | The control point must be **always on** for automations; a laptop sleeps. If it is offline, tasks show QUEUED and "has NOT run" (PWR-351). | A, B |
| "BroadLink handles IR/RF for the AC and projector/TV." | BroadLink is the IR/RF bridge. Check your model supports RF if you need it. Route it through **Home Assistant** (it has a BroadLink integration; verify your exact model) so JARVIS talks to one gateway with per-entity allow-lists. | A, B |
| "Smart plugs and bulbs handle Wi-Fi devices." | Prefer devices that work **locally** (no cloud account needed) through Home Assistant. Start with **lights only**. | A, B |
| AC row: "Turn on the AC." | Low risk, but add a minimum off-time and a max toggles-per-hour so the compressor is not cycled rapidly. | A |
| Projector/TV row: "Turn on the projector." | IR is **one-way**, so JARVIS cannot know the real state. Report "command sent (unconfirmed)", never "projector is on." | A |
| Smart plugs row: "Turn on the geyser." | **High-load device.** Use hardware rated above the geyser's current draw (many plugs are rated lower), a geyser with its own thermostat cut-off, an automatic max runtime, and approval for "on" when nobody is home. Never schedule it unattended. | A |
| Smart bulbs row: "Turn off the lights." | Safe to enable first. This is your **first real action** in Stage 01. | A |
| "Geyser + more: use the right rated hardware; one room-wide control layer." | Keep the one-layer idea. That layer is Home Assistant plus JARVIS's policy gate, with high-wattage devices disabled until Milestone D passes. | B |
| "Local brain: Mac / J.A.R.V.I.S. Control layer: BroadLink + plugs + bulbs." | Local brain = controller. Control layer = Home Assistant. Devices = allow-listed entities only. | A |
| "Stage 01 = the foundation: voice + local execution + room control. Next stages add tools, routines, automations, integrations." | Stage 01 gate: wake works; echo-only dry run passes; lights respond; audit log shows every command; kill switch stops everything. **Then** build Milestones A→D of the master prompt before any new power. | A |

---

## 4. Source 4: Grok Bot Business Playbook, upgraded for JARVIS

I kept the **method** and dropped the product. The guide says it is independent and not official, and I could not verify its product claims, so none are relied on.

### 4.1 Mental model

| Source line | Upgraded line | Maps to |
|---|---|---|
| "Three repeatable workflows to stop chasing leads, stop checking five dashboards, get recurring work off your plate." | JARVIS version: **Opportunity follow-up desk** (jobs, internships, hackathons, collaborations), **Morning Pulse** (servers, SSL, backups, markets, channel stats), **Weekly Ops Sweep**. | PWR-370, 368, 369 |
| "Think like a founder, not a prompt engineer." | Think like an operator: every agent gets a written **charter**. | PWR-360 |
| "Role + Access + Process + Review + Routine." | Agent charter fields: role, allowed tools/sources, procedure (skill), review gate, schedule. Stored as a file and enforced by the policy gate. | PWR-360 |
| "Bot = who, Skill = how, Routine = when." | Agent = who, Skill = how, Scheduled job = when. Same three objects in your registry. | PWR-339, 272 |
| "Read information across connected tools you can access." | Read only through vetted MCP servers with scoped credentials. | PWR-345 |
| "Organise, compare, summarise, draft and prepare work for review." | Drafts only until a power is promoted. Nothing is sent. | PWR-361 |
| "Not every app is guaranteed to connect. A site may block automation or need a human login." | Return `AWAITING_LOGIN` or `BLOCKED` and ask you. Never bypass a CAPTCHA or login check. | Rule 11 |
| "A routine does not mean everything happens unattended." | Three routine tiers: **observe-only** (can run unattended), **draft** (needs review), **action** (approval every run). | PWR-361 |
| "The Bot can make mistakes. Check important numbers against the source." | Every number carries a source link and timestamp, and you spot-check a sample. | PWR-363 |
| "Start by asking it to prepare something. Once reliable, save and schedule." | The promotion ladder: manual → saved skill → routine. | PWR-362 |

### 4.2 Setup and profile

| Source line | Upgraded line | Maps to |
|---|---|---|
| Access check: eligible paid plans, linked subscriptions. | Not applicable to JARVIS (no per-seat plan). Instead check model/API access and set a daily spend cap. | PWR-324 |
| 1: install the app, sign in. | Install only from official sources; pin versions. | PWR-345 |
| 2: "Create one focused Bot… avoid 'run my whole business'." | One focused agent at a time, e.g. `sysadmin-readonly`, before any "do everything" agent. | PWR-360 |
| 3: "Write its boundaries." | Boundaries live in `config/policy.yaml` and the agent charter, not only in prompt text. | PWR-279 |
| 4: "Connect only what it needs." | Per-agent tool allow-list. Unused connectors stay off. | PWR-345 |
| 5: "Run a small test first (no editing, sending, deleting)." | First test = a read-only daily server and SSL report. Verify it by hand. | PWR-368 |
| Profile starter prompt (read-only, approved sources, label uncertainty, never send/delete/buy without approval). | Charter template (below). | PWR-360 |

```text
AGENT CHARTER (save as agents/<name>.charter.md)
Role: <one job>
Allowed sources/tools: <named MCP servers, folders, domains>
Output format: <table/summary + source links + timestamp>
Mode: read-only until promoted
Never without approval: send, publish, submit, buy, delete, change settings
Unknown data: mark "unavailable"; never estimate or infer
Escalate to owner when: source fails, login needed, policy unclear
```

### 4.3 Workflow 01 (leads → your opportunity desk)

| Source line | Upgraded line | Maps to |
|---|---|---|
| Fields needed: name, source, date added, interest, last interaction, status, owner, opt-out. | Opportunity record: organisation, source URL, deadline, eligibility, status, next action, evidence link, **do-not-contact flag**. | PWR-347, 370 |
| Classify: New, Needs follow-up, Waiting, Won, Not a fit, Unclear. | New / Apply / Waiting / Done / Not a fit / **Unclear (must ask me)**. | PWR-193 |
| "Identify duplicates, missing data, leads with no activity for 5 days." | Dedup key + "idle N days" flag, with missing fields listed. | PWR-347 |
| "Draft a short follow-up using only known facts. Do not invent context or urgency." | Keep exactly. This is your no-fabrication rule for resumes, applications and emails. | Rule 7 |
| Return table: lead, status, why, draft, next action, source ID. | Same columns, plus **draft hash** so the approval is bound to the exact text. | PWR-349 |
| "Exclude opted-out. Do not send, edit, enroll or delete." | Do-not-contact list is checked in code before drafting. Sending is always a separate approved step. | PWR-279 |
| Routine: "Every weekday at 9:15 AM in [time zone]." | Weekdays 09:15 `Asia/Kolkata`, quiet hours respected, one notification. | PWR-272 |
| "Only schedule after the manual workflow is accurate on real sample records." | Keep. Minimum: 5 correct manual runs before scheduling. | PWR-362 |

### 4.4 Workflow 02 (ad pulse → Morning Pulse)

| Source line | Upgraded line | Maps to |
|---|---|---|
| "One clean daily report instead of dashboard-hopping." | Morning Pulse: servers (CPU/RAM/disk/uptime), SSL days left, container restarts, backup age, watchlist moves, channel stats. | PWR-368 |
| "Define reporting timezone, attribution window, what counts as a lead." | Define `Asia/Kolkata`, data vendor, adjusted vs unadjusted prices, and what counts as "down". | PWR-363 |
| "Compare with previous day and trailing 7-day average." | Same comparison for metrics where history exists. | PWR-103 |
| "Flag changes by rule (e.g. spend +25%)." | Your own thresholds in config: disk >85%, cert <21 days, price move >X%, volume spike. | PWR-217, 218 |
| Return: 5-bullet summary, table, 3 things to investigate, sources/date range/freshness. | Same structure, spoken and sent to Telegram. | PWR-009 |
| "Distinguish facts from hypotheses." | Keep. Label each line FACT or HYPOTHESIS. | PWR-364 |
| "Do not invent numbers, mix attribution windows, change campaigns, or send externally." | No invented figures; **no trades, ever**; no external send. | PWR-364 |
| "If any source fails, state which one and continue with verified data." | Keep, plus a `STALE` badge on cached values. | PWR-363 |
| "Post the report in this conversation only." | Deliver by voice and Telegram to you only. | PWR-203 |
| "Ad platforms can report conversions late." | Market data can be delayed or end-of-day; show the data time next to each number. | PWR-363 |

### 4.5 Workflow 03 (lifesaver → Weekly Ops Sweep)

| Source line | Upgraded line | Maps to |
|---|---|---|
| "Weekly Ops Sweep: overdue tasks, stalled leads, campaign flags, missing data, top 3 actions." | Overdue tasks, stalled opportunities, failed routines, cert/domain/backup expiries, YouTube upload checklist gaps, top 3 actions with owner and reason. | PWR-369 |
| "Separate verified facts from recommendations." | Keep. | PWR-364 |
| "Do not edit records, contact customers, pause campaigns, assign work or delete anything." | Read-only sweep. Any fix becomes a proposed task awaiting approval. | PWR-361 |
| Other lifesavers: invoice reminders, client updates, inventory, team updates, proposal follow-ups. | For you: backup verification, DNS/domain expiry, dependency updates, expense organisation, shoot checklists. | PWR-114, 122, 180, 198 |
| "Measure time back; repeat for two weeks." | Time ledger: (manual minutes − review minutes) × runs per week ÷ 60. Report after two weeks, not before. | PWR-366 |

### 4.6 From prompt to process

| Source line | Upgraded line | Maps to |
|---|---|---|
| "01 Run manually: review line by line and correct." | Corrections are saved as scoped rules with a test (your correction pipeline). | PWR-352 |
| "02 Save a skill: purpose, sources, steps, required fields, validation, output, missing-data behaviour, approval boundaries." | Skill spec adds: **version, test result, rollback version, permission list** (a skill can never grant itself new permissions). | PWR-339 |
| "03 Create a routine: days, time, sources, what to do if a source fails." | Scheduler entry with owner, timezone, next-run time, retry policy and dead-letter alert. | PWR-272, 277 |
| "Check the routine after creation: owner, time zone, next run, test run, history, fresh links; pause if the site changes." | Routine health panel on the HUD: last 10 runs, failures, drift warning, one-tap pause. | PWR-365 |
| "It can run background work while your laptop is closed." | Only if your **controller is always on** and the target device is online; otherwise QUEUED. | PWR-351 |

### 4.7 Safety, privacy, 7-day plan

| Source line | Upgraded line | Maps to |
|---|---|---|
| "Start read-only; grant only needed access." | Trust ramp: read-only → draft → act, per power. | PWR-361 |
| "Do not paste passwords, passkeys or one-time codes into chat; use secure handoff." | Vault only; you complete login/2FA yourself while JARVIS waits in `AWAITING_LOGIN`. | PWR-144 |
| "Require approval before sending, publishing, buying, deleting, changing budgets/settings." | Matches Tier 2/3. Approval is tied to a content hash and expires. | PWR-349 |
| "All Bots share the same cloud computer and sessions. Separate Bots are not a security boundary." | In JARVIS, separation is **enforced**: per-agent allow-lists, separate browser profiles, container or OS-user isolation. | PWR-360 |
| Troubleshooting: app access, wrong report, invented number, routine did not run, workflow changed. | Failure classes with fixed responses (SESSION_EXPIRED, TARGET_CHANGED, INSUFFICIENT_EVIDENCE, and so on). | Master prompt §6 |
| "Add: mark unavailable; never estimate or infer a metric." | Hard rule in every charter. | PWR-364 |
| Privacy: "requires cloud data storage; Privacy Mode not supported." | The opposite of your design. Do **not** feed private files, screens or memory to any cloud-only agent product. | Rule 1 |
| Day 1–7 plan. | See merged 7-day plan in section 8. | Section 8 |
| "Independent educational guide, not an official document." | Treat all product claims as unverified. | Section 10 |

---

## 5. How the five sources fit together

| Layer of JARVIS | Comes from | What it contributes |
|---|---|---|
| Face and voice (browser UI, wake word, speech) | Guides 1–3 | A working base to start from, after audit |
| Brain and tools (local bridge, controller) | Guides 1–3 + your blueprint | The bridge becomes the controller; the policy gate goes on top |
| Room control | Guides 2–3 | Lights first, then other devices via Home Assistant |
| Operating method (charters, ladder, stamps, ledger) | Grok playbook | How each agent is defined, tested and scheduled |
| Extra capabilities (eval, monitoring, research, voice forms) | 200-ideas book | 23 patterns turned into powers |
| Safety and governance | Your blueprint, catalog and master prompt | Overrides anything above that conflicts (section 9) |

---

## 6. Source 5: the 23 idea cards that match JARVIS

Each card is a business idea; here each becomes a **JARVIS power** (all keep human review and approval).

| Card | Idea in the book | Upgraded as a JARVIS power | Maps to | Priority |
|---|---|---|---|---|
| 43 | Email-to-task agent | Classify mail, draft tasks with owner/due date, link the source email, never act. | PWR-191, 196, 010 | P1 |
| 44 | Browser operations copilot | Low-risk browser steps automated; **pause for confirmation at sensitive steps**. | PWR-063 to 081 | P1 |
| 47 | AI agent testing and evaluation service | **Eval harness**: scenario suites, expected outcomes, tool-call checks, release scorecards for JARVIS itself. | PWR-367 | P1 |
| 48 | Workflow monitoring and alerting | Track run health, retries and outcomes; alert before impact grows. | PWR-278, 365 | P1 |
| 49 | Internal knowledge assistant | Answers from approved documents with citations, dates and escalation. | PWR-008 | P0 |
| 50 | AI approval-routing layer | Classify requests, route by policy, human approval for consequential actions. | PWR-279, 299, 349 | P0 |
| 161 | SOC alert enrichment assistant | For your homelab: correlate approved telemetry, pull runbooks, draft an evidence-linked triage note. | PWR-126, 158 | P2 |
| 163 | Cloud cost anomaly narrator | Explain unusual VPS/API/model spend with a source-linked brief. | PWR-324, 374 | P2 |
| 164 | IT helpdesk knowledge assistant | Answer from your runbooks and create structured tickets with device/environment details. | PWR-141, 143 | P1 |
| 165 | API documentation generator | Generate endpoint docs and examples from schemas and tests, checked in CI. | PWR-168, 169 | P2 |
| 166 | Incident log summariser | Timestamped timeline, impact, hypotheses, open questions. | PWR-126 | P1 |
| 167 | IT asset inventory normaliser | Deduplicate devices and software with confidence and evidence. | PWR-112, 138 | P2 |
| 169 | SaaS access review assistant | Review what has access to what; surface stale permissions. | PWR-157, 161 | P2 |
| 171 | Industry research brief subscription | Source-linked briefs on a schedule (tech, markets). | PWR-015, 236 | P1 |
| 172 | RFP and opportunity radar | Monitor approved portals, match your criteria, **deadline-aware briefs**. | PWR-347, 076 | P1 |
| 174 | Enterprise document Q&A | Permission-aware answers with citations and version info. | PWR-084 | P1 |
| 175 | Meeting decision tracker | Consented notes → decisions, owners, due dates, risks. | PWR-195, 196 | P1 |
| 178 | Research bibliography checker | Validate sources and map citations to claims; **fact-check nature-video scripts**. | PWR-238, 015 | P1 |
| 179 | Data-to-insight narrative service | Explain changes with approved metrics and traceable calculations. | PWR-234, 368 | P1 |
| 182 | Voice-to-form assistant | Speak answers into form fields with **read-back confirmation** before submit. | PWR-068, 371 | P2 |
| 185 | Video subtitle and caption service | Timestamped captions with correction workflow; Hindi/Marathi/English. | PWR-247, 249 | P2 |
| 188 | Public information assistant | Answer **only from whitelisted official sources** with citations and dates. | PWR-375 | P1 |
| 190 | Field-worker report summariser | Voice notes from a shoot or site visit → structured report with missing-field flags. | PWR-372 | P2 |

---

## 7. New powers created by this merge (PWR-356 to PWR-375)

These extend the 355-power catalog and keep the same template. Fill the remaining fields from the matching category profile when you build each one.

| ID | Power | Source | Priority | Value |
|---|---|---|---|---|
| PWR-356 | **Pre-run repo audit gate** (license, install scripts, network calls, exposed tools, auth) before running any third-party repo | Guides 1–3 | P0 | 10/10 |
| PWR-357 | **Local bridge hardening**: bind 127.0.0.1, auth token on every request, check the Origin header, no wildcard CORS | Guides 1–3 | P0 | 10/10 |
| PWR-358 | **Voice provider switch** with a visible data-flow label (browser / ElevenLabs / local) | Guides 2–3 | P1 | 8/10 |
| PWR-359 | **Smart-load safety interlock**: rated hardware check, max runtime, approval, no unattended schedule for high-wattage devices | Guides 2–3 | P0 | 9/10 |
| PWR-360 | **Agent charter**: role, tools, procedure, review gate, schedule, enforced by policy | Playbook | P0 | 9/10 |
| PWR-361 | **Trust ramp**: read-only → draft → act, per power and per routine tier | Playbook, guide 1 | P0 | 10/10 |
| PWR-362 | **Promotion ladder**: manual run → saved skill → routine, with a minimum of 5 correct runs | Playbook | P1 | 8/10 |
| PWR-363 | **Source stamp** on every report: sources, date range, timezone, data time, STALE badge | Playbook | P1 | 8/10 |
| PWR-364 | **Unavailable, never estimate** rule and FACT/HYPOTHESIS labels | Playbook | P0 | 9/10 |
| PWR-365 | **Routine health panel**: last runs, failures, drift warning, one-tap pause | Playbook, card 48 | P1 | 8/10 |
| PWR-366 | **Time-saved ledger** (manual − review minutes) | Playbook | P2 | 6/10 |
| PWR-367 | **Agent eval harness**: scenarios, expected outcomes, tool-call checks, scorecards | Card 47 | P1 | 9/10 |
| PWR-368 | **Morning Pulse** (servers, SSL, backups, watchlist, channel stats) | Playbook, card 179 | P1 | 9/10 |
| PWR-369 | **Weekly Ops Sweep** | Playbook | P1 | 8/10 |
| PWR-370 | **Opportunity follow-up desk** (drafts only, do-not-contact list) | Playbook, card 172 | P1 | 8/10 |
| PWR-371 | **Voice-to-form with read-back** | Card 182 | P2 | 6/10 |
| PWR-372 | **Field voice-note → structured report** (shoots, site visits) | Card 190 | P2 | 7/10 |
| PWR-373 | **One-way device state labelling**: "sent (unconfirmed)" vs "confirmed" | Guides 2–3 | P1 | 8/10 |
| PWR-374 | **Cloud/VPS/model cost anomaly narrator** | Card 163 | P2 | 6/10 |
| PWR-375 | **Whitelisted-source answer mode** | Card 188 | P1 | 8/10 |

---

## 8. The merged runbook (Stage 01 guides + playbook + master prompt)

### 8.1 Order of work

| Step | What | Gate to pass |
|---|---|---|
| **0. Decide** | Fill the `[FILL]` items in the master prompt (OS, RAM, GPU, always-on?, phone, model access). Create a dedicated browser profile. | All fields filled |
| **A0. Audit** | Run PWR-356 on `adewaskar/jarvis`: license, install scripts, network calls, exposed tools, auth. Write `ADR-001`. | You approve the audit report |
| **1a. Base run** | `npm ci --ignore-scripts`, review, setup, start on 127.0.0.1, INITIALISE in **echo-only** mode. | UI loads, no tool executes |
| **1b. Bridge hardening** | PWR-357: token + Origin check, localhost bind verified. | A request without the token is refused |
| **1c. Voice** | Wake test x10, push-to-talk fallback, pick provider (PWR-358), label data flow. | False-accept/reject logged |
| **1d. Room (lights only)** | Home Assistant + one bulb, per-entity allow-list, state read-back. | Light responds; audit log shows the command |
| **1e. Kill switch** | Stop everything by hotkey, CLI and button. | All three work |
| **Stage 01 done** | = the guides' "foundation". | All above pass |
| **Master A → D** | Controller, tasks, safe browser, desktop worker, then **policy, approvals, audit** (build D properly). | Master prompt gates |
| **High-load devices** | Geyser and AC only after D passes and PWR-359 is in place. | Interlock test passes |
| **E → G** | Memory, voice/phone, agents, then domain powers; each routine climbs the ladder (PWR-362). | Per-milestone gates |

### 8.2 Seven-day plan (merges the playbook's plan with your build)

| Day | Do |
|---|---|
| 1 | Fill the master prompt fields; install tools from official sources; run A0 audit (read-only). |
| 2 | Base run in echo-only mode; harden the bridge; kill-switch test. |
| 3 | Voice: wake test, push-to-talk, provider choice with data-flow label. |
| 4 | Lights-only room test through Home Assistant; confirm state read-back. |
| 5 | Write your first agent charter (`sysadmin-readonly`); run the Morning Pulse **manually** and verify numbers by hand. |
| 6 | Save it as a skill (versioned, tested); run it again. |
| 7 | Schedule it for 09:15 `Asia/Kolkata`, check the first run, log review minutes in the time ledger. Pause if results drift. |

### 8.3 Add this to your Antigravity prompt (paste after section 14, before "First actions")

```text
MILESTONE A0 (new, runs before Milestone A): BASE REPO AUDIT
Base repo to evaluate: https://github.com/adewaskar/jarvis (unverified; do not assume what it contains).
Work read-only. Report: license; last commit date; contributors; every dependency with install
scripts; every outbound network call and destination; every tool/command the bridge can execute;
how the bridge authenticates; which interface it binds to; where secrets are read from; whether
audio or text leaves the machine (browser speech, ElevenLabs, other).
Then propose changes: bind to 127.0.0.1 only, token on every request, Origin check, no wildcard CORS,
echo-only mode, voice provider switch with a data-flow label, secrets in keychain/.env (git-ignored).
Do not install, run or edit anything until I approve the audit report.
Room-control rule: only low-risk devices (lights) may be enabled in Stage 01, through Home Assistant
with a per-entity allow-list. Geyser, AC compressor and any high-wattage load stay disabled until
Milestone D passes and the load-safety interlock (PWR-359) is tested.
Device state rule: IR commands are one-way; report "sent (unconfirmed)", never "on".
Reports rule: every report carries sources, date range, timezone, data time and a STALE badge;
unknown numbers are marked "unavailable", never estimated.
```

---

## 9. Conflicts between the sources and the decision taken

| # | Topic | Sources say | Your blueprint says | Decision |
|---|---|---|---|---|
| 1 | Terminal | Desktop guide: none needed. Stage guides: run npm commands. | Every command logged and visible | Commands may be typed by the agent, but you read and approve each one. |
| 2 | Install method | Download ZIP | Pin versions, keep history | Fork/clone at a pinned commit. |
| 3 | Voice | ElevenLabs / browser speech | Local-first | Provider switch; local default for private text. |
| 4 | Real tools in Stage 01 | Room control in Stage 01 | No real tools until policy gate (rule 13) | Lights only in Stage 01; everything else after Milestone D. |
| 5 | Operating system | Mac | Unknown (you must fill it in) | Fill in your real OS before building. |
| 6 | Claude Code plan | Needs a paid plan (per the guide) | Your account here is on the free plan | Check availability; otherwise use Antigravity with the same steps. |
| 7 | Where data lives | Playbook product stores data in the cloud | Local-first | Use the method only. |
| 8 | Agent isolation | Playbook: separate bots are not a boundary | Policy gate plus per-agent scopes | Enforce separation in code (PWR-360). |
| 9 | Unattended routines | "Routine" implies hands-off | Approval for consequential actions | Three routine tiers (PWR-361). |
| 10 | "Approve the safe actions" | Desktop guide's tip | Deterministic deny-by-default policy | Pre-define safe vs unsafe commands; do not decide ad hoc. |
| 11 | Business vs personal | 200-ideas book sells services to clients | Private single-user | Only the capability patterns are used. |

---

## 10. What is unverified or limited

- **Repo not verified.** `adewaskar/jarvis` was not opened. Its contents, license, safety and whether it matches the guides are unknown until A0 is done. The relationship between the guide author (Ayman William) and the repo owner is also unknown.
- **Date-sensitive claims.** The guides cite sources dated 6 Oct 2026; product features and plan eligibility change quickly. Recheck on the day you build.
- **Browser speech data flow** is stated as "often cloud-processed" from general knowledge, not from this repo.
- **Home Assistant + BroadLink** compatibility depends on your exact model and firmware; check before buying.
- **Electrical safety** guidance for the geyser is general. Have a qualified electrician confirm ratings and wiring.
- **Grok Bot** product claims (plans, connectors, background running) were not verified; only the working method was reused.
- **Idea cards** were mapped by their titles and solution statements; their pricing and market claims were not evaluated.

---

## 11. File map

| This file's section | Built from |
|---|---|
| 2 | JARVIS Desktop App Only Guide |
| 3 | JARVIS Stage 01 Ayman Guide + Stage 01 Build Guide |
| 4 | Grok Bot Business Playbook |
| 6 | 200 AI Business Ideas (cards 43, 44, 47–50, 161, 163–167, 169, 171, 172, 174, 175, 178, 179, 182, 185, 188, 190) |
| 7–9 | Merge with your master PDF, Power Catalog and Antigravity prompt |

