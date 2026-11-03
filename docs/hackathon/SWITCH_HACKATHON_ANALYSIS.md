# WeMakeDevs x DevTools Academy "Flip the Switch" Hackathon Analysis

**Target URL:** `https://www.wemakedevs.org/hackathons/switch`  
**Powered by:** Switch AI (`switchagents.ai` | GitHub: `sandbox-quantum/switch`)  
**Dates:** November 4–7, 2026 (Starts Tomorrow!)  
**Prize Pool:** $10,000 USD  
**Format:** Online / Global (Solo or Teams of up to 4)  
**Host Organizations:** WeMakeDevs & DevTools Academy  

---

## 1. Hackathon Core Theme & Problem Statement

### The Industry Problem: The "Terminal & IDE Silo"
In 2026, developers heavily rely on autonomous AI coding agents:
- **Claude Code** running in one terminal.
- **OpenAI Codex** running in another shell.
- **Cursor / OpenCode / Antigravity** editing in IDE panes.

However, all of these agents operate in **total isolation**:
1. **Context Blindness:** Alice's agent refactors an API in her local shell while Bob's agent generates frontend code calling the deprecated endpoint.
2. **Context Copy-Pasting:** Developers are forced to constantly copy terminal logs, error traces, and diffs from their CLI into Slack/Discord to show their team.
3. **Absence of Team Governance:** High-privilege agent actions (database migrations, AWS deployment, deleting files) happen on individual developer machines without team review or single-use cryptographic authorization.

### The Challenge: "Flip the Switch"
The hackathon tasks developers with **"Flipping the Switch"** using the **Switch tool (`sandbox-quantum/switch`)** to:
1. Bring isolated AI agents out of local terminals and into team communication platforms (Slack, Discord, Microsoft Teams, Telegram).
2. Create shared **"Rooms"** where humans and multiple AI agents collaborate on real software engineering workflows.
3. Build functional, high-value workflows (e.g. cross-agent code review, autonomous incident triage, distributed sprint execution).

---

## 2. Platform Architecture & Developer Tools: Switch (`switchagents.ai`)

- **Open Source Core:** `sandbox-quantum/switch`
- **MCP Server Support:**
  - Claude Code: `claude mcp add switch-docs --transport http https://docs.switchagents.ai/mcp`
  - Codex / Antigravity: MCP endpoint `https://docs.switchagents.ai/mcp`
- **Supported Chat Interfaces:** Slack, Discord, Microsoft Teams, Telegram, Mattermost.
- **Core Abstractions:**
  - **Rooms:** Shared workspaces mapped to Slack channels or Discord threads.
  - **Agents:** Named autonomous participants with assigned roles, system prompts, and tool sets.
  - **Governance (Switch Trust & Switch ROI):** Tracking costs, monitoring safety guardrails, and enforcing action permissions.

---

## 3. The Judging Rubric & How to Avoid "AI Slop"

### What 90% of Hackathon Teams Will Build (The "AI Slop" Trap):
- *Team A:* A Slack bot that answers questions using OpenAI GPT-4o.
- *Team B:* A Discord bot that runs `git commit` when tagged with `@bot commit`.
- *Team C:* A bot that summarizes Jira tickets and posts them every morning.

**Why Judges Reject This:**
Judges have seen thousands of basic API wrappers. They lack architectural novelty, fail to solve multi-agent context collisions, and break immediately under real team conditions.

### The Winning Vector:
To win the **$10,000 Grand Prize**, an entry must demonstrate:
1. **Multi-Agent Swarm Orchestration:** Connecting distinct agents (e.g. Antigravity + Claude Code + Codex) in one shared room where they cross-review and debate plans.
2. **Dynamic Rate-Limit Failover ("Hydra Swarm"):** Seamlessly switching between model providers (Claude -> DeepSeek -> Gemini -> Local Ollama) when rate limits hit, with zero context drop.
3. **Cryptographic Human Governance:** Interactive approval cards rendered in Discord/Slack with single-use HMAC tokens and Merkle audit logging.
4. **Verifiable Truth (First Law):** Zero fabricated claims — every action posted to the team chat contains forensic evidence hashes.

