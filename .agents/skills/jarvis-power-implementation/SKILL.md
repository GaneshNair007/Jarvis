---
name: jarvis-power-implementation
description: Standardized implementation methodology for JARVIS runtime operational powers (PWR-001 through PWR-355). Use when implementing, repairing, or registering operational tools, declaring input/output schemas, and wiring policy checks.
---

# JARVIS Power Implementation Standard

## Development Skill vs Runtime Power
- **Antigravity Skill (`SKILL.md`)**: Instructions guiding the developer or agent on how to build, test, and maintain code.
- **JARVIS Power (`PWR-xxx`)**: Concrete executable Python functions with schema validation, policy authorization, telemetry, and audit tracking.

## Implementation Checklist
When implementing or repairing a power:
1. **Catalog Entry (`data/powers_catalog.json`)**:
   - Ensure `power_id` (e.g. `PWR-025`), `name`, `category`, `risk_tier`, and description are unique and valid.
2. **Implementation Module (`jarvis/powers/*.py`)**:
   - Write deterministic, typed Python code.
   - Return structured dictionary containing `"power_id": "<ID>"` and status fields.
   - Catch and handle OS-specific exceptions gracefully (e.g. encoding fallbacks on Windows).
   - Async helper: Use `_safe_run_async()` when calling coroutines to prevent event-loop conflicts.
3. **Module Registration (`jarvis/powers/__init__.py`)**:
   - Import and export the power singleton.
4. **Policy & Permission Tiers (`config/policies/permissions.json`)**:
   - Register risk tier (Tier 0: safe read-only; Tier 1: local state mutation; Tier 2: outbound/network; Tier 3: destructive/financial).
5. **Unit Tests (`tests/test_*.py`)**:
   - Write pytest functions verifying expected outputs, parameter edge cases, and failure modes.

## Verification
```powershell
python -m pytest tests/test_power_registry.py tests/test_skills_and_plugins.py -v
```

