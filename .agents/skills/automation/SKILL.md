---
name: automation
description: Interactive guide to design and create a scheduled background automation. Use this skill when the user wants to create an automated or recurring scheduled task (e.g. "summarize my emails every morning", "every Monday send me a to-do list"). Also triggered by the /automation slash command.
metadata:
  icon: schedule
---

# Scheduled Automations Skill

A scheduled automation is a background sidecar (`"builtin": "schedule"`) that runs on a cron schedule and starts a fresh agent conversation on each run.

## Cadence Options
- **Hourly:** `0 * * * *`
- **Daily:** `0 9 * * *` (e.g., 9:00 AM)
- **Weekly:** `0 9 * * 1` (Monday mornings)
- **Custom cron:** Custom interval specification

## Configuration Format
Sidecar configuration is stored at `<configDir>/sidecars/<sidecar-id>/sidecar.json`:

```json
{
  "builtin": "schedule",
  "args": [
    "CRON_TZ=America/New_York 0 9 * * *",
    "agentapi",
    "new-conversation",
    "--",
    "Run daily morning brief: summarize system telemetry, new job matches, and pending calendar items."
  ],
  "restart_policy": "always",
  "display_name": "Daily Morning Brief",
  "description": "Every day at 9:00 AM, aggregates system status, career pipeline updates, and alerts."
}
```

## Security & Verification Guardrails
- Scoped permissions only: command grants require explicit prefixes (never generic wildcards like `command(*)`).
- Never auto-enable sidecars silently; always instruct the user to verify in the Automations dashboard.

