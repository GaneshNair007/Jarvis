"""Workflow-to-Skill Migration Script (Per migrate-workflows skill).

Scans workspace and configuration directories for legacy .md workflows,
creates target SKILL.md files idempotently with YAML frontmatter,
and safely archives original workflow files to .md.bak.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def extract_metadata(content: str, fallback_name: str) -> Tuple[str, str, str]:
    """Extracts name, description, and body from a workflow markdown file."""
    # Check for existing YAML frontmatter
    yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if yaml_match:
        frontmatter, body = yaml_match.groups()
        name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else fallback_name
        description = desc_match.group(1).strip() if desc_match else f"Skill for {name}"
        return name, description, body.strip()

    # Fallback: extract title from first heading
    lines = content.splitlines()
    title = fallback_name
    desc = f"Skill migrated from {fallback_name} workflow."
    for line in lines:
        if line.startswith("# "):
            title = line.replace("# ", "").strip()
            desc = f"Executes the {title} workflow."
            break

    return fallback_name, desc, content.strip()


def migrate_workflows(
    workspace_dir: str = ".",
    archive_suffix: str = ".bak"
) -> List[Dict[str, str]]:
    """Discovers and migrates legacy workflows to skills."""
    ws = Path(workspace_dir)
    results = []

    legacy_dirs = [
        ws / ".agents" / "workflows",
        ws / "_agents" / "workflows",
        ws / ".agent" / "workflows",
        ws / "_agent" / "workflows",
    ]

    for leg_dir in legacy_dirs:
        if not leg_dir.exists():
            continue

        for wf_file in leg_dir.glob("*.md"):
            if wf_file.name.endswith(".bak") or wf_file.name.endswith(".md.bak"):
                continue

            slug = wf_file.stem
            target_skill_dir = ws / ".agents" / "skills" / slug
            target_skill_file = target_skill_dir / "SKILL.md"

            if target_skill_file.exists():
                results.append({
                    "workflow": wf_file.name,
                    "source": str(wf_file),
                    "target": str(target_skill_file),
                    "status": "Already Migrated"
                })
                continue

            # Read content
            raw_text = wf_file.read_text(encoding="utf-8")
            name, desc, body = extract_metadata(raw_text, slug)

            # Format target SKILL.md
            skill_text = f"""---
name: {slug}
description: {desc}
---

# {name.title()}

{body}
"""
            target_skill_dir.mkdir(parents=True, exist_ok=True)
            target_skill_file.write_text(skill_text, encoding="utf-8")

            # Safely archive original workflow
            archived_file = wf_file.with_name(f"{wf_file.name}{archive_suffix}")
            wf_file.rename(archived_file)

            results.append({
                "workflow": wf_file.name,
                "source": str(archived_file),
                "target": str(target_skill_file),
                "status": "Migrated"
            })

    return results


if __name__ == "__main__":
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    records = migrate_workflows(directory)
    print(f"Migration completed for {len(records)} workflows.")
    for r in records:
        print(f"[{r['status']}] {r['workflow']} -> {r['target']}")

