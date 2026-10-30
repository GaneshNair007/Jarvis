---
name: plugin
description: How to manage and create plugins — namespaced bundles of skills, agents, rules, MCP servers and hooks that install, enable and disable as a single unit. Use this skill when the user wants to enable, disable, install or uninstall a plugin, or package new customizations into a plugin. Also triggered by the /plugin slash command.
metadata:
  icon: extension
---

# Plugins Management & Authoring Skill

A plugin is a namespaced bundle of customizations that ships, installs, and turns on as one unit. It can contain skills, agents, rules, MCP servers, and hooks. Disabling it takes the whole bundle down at once.

## Plugin Structure
```text
plugins/<name>/
├── plugin.json       # Required manifest (JSONC)
├── README.md         # User-facing documentation
├── mcp_config.json   # Optional MCP tool server bindings
├── skills/<skill>/SKILL.md
├── agents/<agent>.md
└── rules/AGENTS.md
```

## Manifest (`plugin.json`)
```json
{
  "name": "jarvis-career-ops",
  "displayName": "Career-Ops Subsystem",
  "version": "1.0.0",
  "description": "Local-first ATS job scanning, tailored resume and cover-letter generation, and interview prep.",
  "suggestedPrompts": [
    "/job-scan Principal AI Engineer at DeepTech",
    "/generate-resume Staff Distributed Architect",
    "/pipeline"
  ]
}
```

## Lifecycle Operations
- **Inventory:** List all registered workspace and global plugins.
- **Enable / Disable:** Toggle plugin enablement state dynamically.
- **Install / Uninstall:** Safely unpack or delete user-authored plugins while preserving configuration backups.

