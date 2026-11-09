---
name: migrate-workflows
description: Automatically migrate legacy workflows to modern skills across global and workspace configurations. Scans for existing workflows, creates target SKILL.md files, and safely archives old workflow files as .md.bak.
metadata:
  icon: swap_horiz
---

# Migrate Workflows to Skills

Autonomously migrates legacy `.agents/workflows/*.md` and `~/.gemini/config/workflows/*.md` files into modern `.agents/skills/<name>/SKILL.md` structures.

## Migration Process
1. **Discover:** Scans workspace and global configuration directories for legacy workflow files and `workflows.json` manifests.
2. **Convert (Idempotent):**
   - Extracts workflow instructions, descriptions, and metadata.
   - Generates standard YAML frontmatter (`name`, `description`).
   - Writes destination `<target_skill_dir>/<name>/SKILL.md`.
   - Never overwrites existing `SKILL.md` files (preserves user customizations).
3. **Archive Safely:** Renames original workflow file to `<name>.md.bak` to ensure zero data loss.
4. **Report:** Emits structured markdown summary table with migration status and file paths.

