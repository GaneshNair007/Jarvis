import json
import re
from pathlib import Path
from collections import Counter, defaultdict

def build_refined_powers_system():
    # Load current master powers
    master_path = Path("config/powers/master_powers_355.json")
    if not master_path.exists():
        master_path = Path("data/powers_catalog.json")
    
    with open(master_path, "r", encoding="utf-8") as f:
        powers = json.load(f)

    print(f"Loaded {len(powers)} base powers.")

    # 1. Resolve Duplicate Names
    renames = {
        ("PWR-053", "Message drafting"): "Dictation Message Drafting",
        ("PWR-209", "Message drafting"): "Communication Message Drafting",
        ("PWR-095", "Backup verification"): "File Backup Verification",
        ("PWR-115", "Backup verification"): "System Backup Verification",
        ("PWR-125", "Rollback planning"): "Infrastructure Rollback Planning",
        ("PWR-179", "Rollback planning"): "Deployment Rollback Planning",
        ("PWR-213", "Meeting copilot"): "Meeting Notes Copilot",
        ("PWR-311", "Meeting copilot"): "Tactical Meeting Copilot",
    }

    # Repository paths and primary repo handlers
    repo_sources = {
        "atticus-mac": {
            "source_dir": "repos/atticus-mac",
            "handler_module": "jarvis.powers.instant_local",
            "primary_file": "repos/atticus-mac/atticus.py"
        },
        "browser-use": {
            "source_dir": "repos/browser-use",
            "handler_module": "jarvis.browser.research_worker",
            "primary_file": "repos/browser-use/browser_use/agent/service.py"
        },
        "career-ops": {
            "source_dir": "repos/career-ops",
            "handler_module": "jarvis.integrations.career_ops",
            "primary_file": "repos/career-ops/skills"
        },
        "cua": {
            "source_dir": "repos/cua",
            "handler_module": "jarvis.computer.sandbox",
            "primary_file": "repos/cua/libs/core"
        },
        "hermes-agent": {
            "source_dir": "repos/hermes-agent",
            "handler_module": "jarvis.memory.hermes_vault",
            "primary_file": "repos/hermes-agent/agent/skills.py"
        },
        "mcp-servers": {
            "source_dir": "repos/mcp-servers",
            "handler_module": "jarvis.mcp_gateway",
            "primary_file": "repos/mcp-servers/src"
        },
        "open-interpreter": {
            "source_dir": "repos/open-interpreter",
            "handler_module": "jarvis.powers.desktop_powers",
            "primary_file": "repos/open-interpreter/interpreter"
        },
        "open-jarvis": {
            "source_dir": "repos/open-jarvis",
            "handler_module": "jarvis.graph.jarvis_graph",
            "primary_file": "repos/open-jarvis/configs"
        },
        "openclaw": {
            "source_dir": "repos/openclaw",
            "handler_module": "jarvis.integrations.openclaw",
            "primary_file": "repos/openclaw/skills"
        },
        "openhands": {
            "source_dir": "repos/openhands",
            "handler_module": "jarvis.powers.developer_powers",
            "primary_file": "repos/openhands/openhands"
        },
        "ui-tars-desktop": {
            "source_dir": "repos/ui-tars-desktop",
            "handler_module": "jarvis.powers.desktop_powers",
            "primary_file": "repos/ui-tars-desktop"
        }
    }

    # Core native executable powers
    core_executable_pids = {
        # Voice powers
        "PWR-001", "PWR-002", "PWR-003", "PWR-004", "PWR-005",
        # Desktop / Screen powers
        "PWR-016", "PWR-017", "PWR-018", "PWR-019", "PWR-020", "PWR-021", "PWR-022", "PWR-023", "PWR-024", "PWR-025", "PWR-026",
        # Local search & files
        "PWR-027", "PWR-028", "PWR-029", "PWR-030", "PWR-031", "PWR-032", "PWR-033",
        # Browser automation & research
        "PWR-063", "PWR-064", "PWR-065", "PWR-066", "PWR-067", "PWR-068", "PWR-069", "PWR-070",
        # Orchestrator & Task & System
        "PWR-288", "PWR-289", "PWR-290", "PWR-291", "PWR-292", "PWR-293", "PWR-294", "PWR-295",
        # Memory Vault
        "PWR-320", "PWR-339", "PWR-340",
        # MCP Gateway
        "PWR-013", "PWR-014", "PWR-345"
    }

    refined_powers = []
    source_inventory = []

    seen_ids = set()
    seen_names = set()
    seen_slugs = set()

    executable_count = 0
    config_required_count = 0
    reference_only_count = 0

    for p in powers:
        pid = p["power_id"]
        orig_name = p["power_name"]
        
        # Apply renaming if in rename list
        name = renames.get((pid, orig_name), orig_name)

        # Generate unique slug
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
        category = p.get("category", "General")
        repos = p.get("contributing_repos", ["openclaw"])
        primary_repo = repos[0] if repos else "openclaw"

        # Determine execution status and handler
        if pid in core_executable_pids:
            status = "executable"
            executable_count += 1
            if "Voice" in category:
                handler = "jarvis.powers.voice_powers"
            elif "Browser" in category:
                handler = "jarvis.browser.research_worker"
            elif "Screen" in category or "Instant Local" in category:
                handler = "jarvis.powers.desktop_powers"
            elif "Memory" in category:
                handler = "jarvis.memory"
            else:
                handler = "jarvis.core.power_registry"
        elif any(k in category for k in ["Advanced Iron Man", "Research-derived addition", "Multi-Agent"]):
            status = "reference_only"
            reference_only_count += 1
            handler = f"jarvis.blueprints.{primary_repo.replace('-', '_')}"
        else:
            status = "requires_configuration"
            config_required_count += 1
            handler = repo_sources.get(primary_repo, {}).get("handler_module", "jarvis.integrations")

        source_info = repo_sources.get(primary_repo, {
            "source_dir": f"repos/{primary_repo}",
            "primary_file": f"repos/{primary_repo}"
        })

        record = dict(p)
        record["power_id"] = pid
        record["power_name"] = name
        record["slug"] = slug
        record["category"] = category
        record["source_repo"] = primary_repo
        record["contributing_repos"] = repos
        record["repo_paths"] = [f"repos/{r}" for r in repos]
        record["execution_handler"] = handler
        record["status"] = status
        record["source_file"] = source_info.get("primary_file")
        record["danger_level"] = p.get("danger_level", "low").lower()
        record["approval_required"] = p.get("approval_required", False)
        record["enabled"] = True

        refined_powers.append(record)

        # Build inventory item
        source_inventory.append({
            "power_id": pid,
            "power_name": name,
            "slug": slug,
            "category": category,
            "description": p.get("one_line_description", ""),
            "source_repo": primary_repo,
            "contributing_repos": repos,
            "source_path": source_info.get("primary_file"),
            "execution_handler": handler,
            "status": status,
            "danger_level": record["danger_level"],
            "approval_required": record["approval_required"],
            "permissions_required": p.get("permissions_required", "tier_0_read"),
            "dependencies": p.get("dependencies", "")
        })

        seen_ids.add(pid)
        seen_names.add(name)
        seen_slugs.add(slug)

    print(f"Refined Powers count: {len(refined_powers)}")
    print(f"Unique IDs: {len(seen_ids)}")
    print(f"Unique Names: {len(seen_names)}")
    print(f"Unique Slugs: {len(seen_slugs)}")
    print(f"Executable: {executable_count}, Config-required: {config_required_count}, Reference-only: {reference_only_count}")

    # Write data/powers_catalog.json
    out_catalog = Path("data/powers_catalog.json")
    out_catalog.write_text(json.dumps(refined_powers, indent=2), encoding="utf-8")

    # Write config/powers/master_powers_355.json
    out_master = Path("config/powers/master_powers_355.json")
    out_master.write_text(json.dumps(refined_powers, indent=2), encoding="utf-8")

    # Write data/power_source_inventory.json
    out_inv = Path("data/power_source_inventory.json")
    out_inv.write_text(json.dumps(source_inventory, indent=2), encoding="utf-8")

    # Build ecosystem breakdown
    repo_counts = Counter()
    for p in refined_powers:
        for r in p["contributing_repos"]:
            repo_counts[r] += 1

    repo_breakdown = {}
    for r, count in repo_counts.items():
        sample_pids = [p["power_id"] for p in refined_powers if r in p["contributing_repos"]][:5]
        repo_breakdown[r] = {
            "name": r,
            "power_count": count,
            "sample_powers": sample_pids,
            "source_dir": f"repos/{r}",
            "repo_url": f"https://github.com/{r}"
        }

    ecosystem = {
        "formula": "JARVIS = atticus-mac + browser-use + career-ops + cua + hermes-agent + mcp-servers + open-interpreter + open-jarvis + openclaw + openhands + ui-tars-desktop",
        "mathematical_reconciliation": {
            "total_unique_powers": len(refined_powers),
            "total_repository_associations": sum(repo_counts.values()),
            "single_repo_powers": sum(1 for p in refined_powers if len(p["contributing_repos"]) == 1),
            "multi_repo_powers": sum(1 for p in refined_powers if len(p["contributing_repos"]) > 1),
            "reconciliation_formula": "Total Associations (427) = 285 (1 repo) + 68*2 (2 repos) + 2*3 (3 repos) = 355 Unique Powers"
        },
        "total_powers": len(refined_powers),
        "total_repos": len(repo_breakdown),
        "status_distribution": {
            "executable": executable_count,
            "requires_configuration": config_required_count,
            "reference_only": reference_only_count
        },
        "repositories": repo_breakdown
    }

    out_eco = Path("config/powers/ecosystem_composition.json")
    out_eco.write_text(json.dumps(ecosystem, indent=2), encoding="utf-8")

    print("SUCCESS: Updated all 4 power catalog files.")

if __name__ == "__main__":
    build_refined_powers_system()
