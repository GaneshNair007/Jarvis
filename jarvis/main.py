"""
JARVIS Unified CLI & Server Entry Point
Usage:
  python -m jarvis.main serve       # Run production FastAPI & WebSocket server
  python -m jarvis.main chat "text" # Process a single query via terminal
  python -m jarvis.main health      # Print live host health metrics
  python -m jarvis.main audit       # Verify cryptographic audit chain integrity
  python -m jarvis.main powers      # List catalog power statistics
"""

import sys
import asyncio
import json
import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from jarvis.config import settings
from jarvis.core.orchestrator import orchestrator
from jarvis.core.audit import audit_ledger
from jarvis.core.power_registry import power_registry
from jarvis.powers.it_admin_powers import it_admin_powers

def run_server():
    print(f"🚀 Starting JARVIS Operating System on http://{settings.jarvis_host}:{settings.jarvis_port}")
    uvicorn.run("jarvis.api.server:app", host=settings.jarvis_host, port=settings.jarvis_port, reload=settings.jarvis_debug)

def run_cli_chat(query: str):
    print(f"\n[USER]: {query}")
    result = asyncio.run(orchestrator.process_user_query(query))
    print(f"[JARVIS ({result.get('tier')})]: {json.dumps(result.get('response'), indent=2)}\n")

def run_health():
    report = it_admin_powers.system_health_report()
    print("\n══════════════════════ JARVIS SYSTEM HEALTH ══════════════════════")
    print(f"Status      : {report['status'].upper()}")
    print(f"CPU Usage   : {report['cpu']['percent']}% ({report['cpu']['cores_logical']} cores)")
    print(f"Memory Usage: {report['memory']['percent']}% ({report['memory']['used_gb']} GB / {report['memory']['total_gb']} GB)")
    print(f"Disk Usage  : {report['disk']['percent']}% ({report['disk']['used_gb']} GB / {report['disk']['total_gb']} GB)")
    print("═════════════════════════════════════════════════════════════════\n")

def run_audit_verify():
    valid, count, msg = audit_ledger.verify_integrity()
    status_icon = "✅" if valid else "❌"
    print(f"\n{status_icon} Audit Ledger Verification: {msg}")

def run_powers_summary():
    total = power_registry.total_count()
    cats = power_registry.list_categories()
    print(f"\n⚡ JARVIS Power Registry: {total} powers across {len(cats)} categories.")
    for cat in cats:
        p_count = len(power_registry.get_powers_by_category(cat))
        print(f"  - {cat:30}: {p_count} powers")
    print()

def cli_entrypoint():
    args = sys.argv[1:]
    if not args or args[0] == "serve":
        run_server()
    elif args[0] == "chat":
        if len(args) < 2:
            print("Error: Please provide a query string. Example: python -m jarvis.main chat 'System health'")
            sys.exit(1)
        run_cli_chat(args[1])
    elif args[0] == "health":
        run_health()
    elif args[0] == "audit":
        run_audit_verify()
    elif args[0] == "powers":
        run_powers_summary()
    else:
        print(f"Unknown command '{args[0]}'. Use: serve, chat, health, audit, powers")

if __name__ == "__main__":
    cli_entrypoint()
