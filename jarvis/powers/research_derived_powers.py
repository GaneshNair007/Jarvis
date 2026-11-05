"""JARVIS Research-Derived Powers (PWR-338 to PWR-355).

Provides meta-cognitive capabilities: tool synthesis, retry logic,
shortcut management, context optimization, approval tokens,
confidence scoring, task decomposition, quality gates, and time tracking.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("powers.research_derived")

_DATA_DIR = Path(os.environ.get(
    "JARVIS_DATA_DIR",
    Path(__file__).resolve().parents[2] / "data"
))
_SHORTCUTS_FILE = _DATA_DIR / "shortcuts.json"
_TIME_LEDGER_FILE = _DATA_DIR / "time_ledger.json"
_HMAC_SECRET = os.environ.get("JARVIS_HMAC_SECRET", "jarvis-default-secret-change-me")


class ResearchDerivedPowers:
    """Implementations for research-derived meta-cognitive capabilities."""

    # ------------------------------------------------------------------
    # PWR-338: Dynamic Tool Synthesis
    # ------------------------------------------------------------------
    def dynamic_tool_synthesis(self, task_description: str) -> Dict[str, Any]:
        """PWR-338: Suggests which tools/powers to chain for a task."""
        task_lower = task_description.lower()

        # Keyword-to-power mapping heuristics
        tool_map: Dict[str, List[str]] = {
            "email":    ["PWR-205 (draft_email)", "PWR-206 (send_email)"],
            "schedule": ["PWR-208 (schedule_message)", "PWR-160 (calendar)"],
            "file":     ["PWR-100 (file_read)", "PWR-101 (file_write)"],
            "search":   ["PWR-120 (web_search)", "PWR-121 (local_search)"],
            "stock":    ["PWR-215 (stock_quote)", "PWR-181 (get_stock_quote)"],
            "expense":  ["PWR-230 (expense_log)", "PWR-231 (expense_summary)"],
            "deploy":   ["PWR-300 (git_status)", "PWR-310 (docker_build)"],
            "notify":   ["PWR-203 (desktop_notification)", "PWR-202 (telegram)"],
            "convert":  ["PWR-180 (convert_currency)", "PWR-218 (currency_convert)"],
            "backup":   ["PWR-140 (backup_create)", "PWR-353 (rollback_plan)"],
            "security": ["PWR-344 (hash_bound_approval)", "PWR-345 (verify_approval)"],
        }

        suggested: List[str] = []
        for keyword, tools in tool_map.items():
            if keyword in task_lower:
                suggested.extend(tools)

        if not suggested:
            suggested = ["PWR-349 (task_decomposer) — break it down first"]

        return {
            "power_id": "PWR-338",
            "status": "success",
            "task": task_description,
            "suggested_tools": suggested,
            "note": "Chain these powers in the listed order for best results.",
        }

    # ------------------------------------------------------------------
    # PWR-339: Retry with Backoff
    # ------------------------------------------------------------------
    def retry_with_backoff(
        self, func: Callable[..., Any], max_retries: int = 3, **kwargs: Any
    ) -> Dict[str, Any]:
        """PWR-339: Exponential backoff retry wrapper.

        Parameters
        ----------
        func : callable
            The function to invoke.
        max_retries : int
            Maximum number of retry attempts (default 3).
        **kwargs
            Forwarded to *func*.
        """
        last_error: Optional[str] = None
        for attempt in range(1, max_retries + 1):
            try:
                result = func(**kwargs)
                return {
                    "power_id": "PWR-339",
                    "status": "success",
                    "attempt": attempt,
                    "result": result,
                }
            except Exception as exc:
                last_error = str(exc)
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "PWR-339 attempt %d/%d failed: %s — retrying in %ds",
                    attempt, max_retries, last_error, wait,
                )
                time.sleep(wait)

        return {
            "power_id": "PWR-339",
            "status": "failed",
            "attempts": max_retries,
            "last_error": last_error,
        }

    # ------------------------------------------------------------------
    # PWR-340: Learned Shortcut Registry (read)
    # ------------------------------------------------------------------
    def learned_shortcut_registry(self) -> Dict[str, Any]:
        """PWR-340: Returns all learned user shortcuts."""
        try:
            if _SHORTCUTS_FILE.exists():
                shortcuts = json.loads(_SHORTCUTS_FILE.read_text(encoding="utf-8"))
            else:
                shortcuts = []
            return {
                "power_id": "PWR-340",
                "status": "success",
                "shortcuts": shortcuts,
                "count": len(shortcuts),
            }
        except Exception as exc:
            return {"power_id": "PWR-340", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-341: Register Shortcut
    # ------------------------------------------------------------------
    def register_shortcut(self, trigger: str, action: str) -> Dict[str, Any]:
        """PWR-341: Registers a new shortcut mapping."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            shortcuts: List[Dict[str, Any]] = []
            if _SHORTCUTS_FILE.exists():
                shortcuts = json.loads(_SHORTCUTS_FILE.read_text(encoding="utf-8"))

            entry = {
                "id": str(uuid.uuid4())[:8],
                "trigger": trigger,
                "action": action,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            shortcuts.append(entry)
            _SHORTCUTS_FILE.write_text(
                json.dumps(shortcuts, indent=2), encoding="utf-8"
            )
            return {
                "power_id": "PWR-341",
                "status": "success",
                "registered": entry,
            }
        except Exception as exc:
            return {"power_id": "PWR-341", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-342: Adaptive Response Format
    # ------------------------------------------------------------------
    def adaptive_response_format(self, query: str) -> Dict[str, Any]:
        """PWR-342: Determines best output format (table/list/prose)."""
        q = query.lower()

        if any(kw in q for kw in ["compare", "vs", "versus", "table", "breakdown"]):
            fmt = "table"
        elif any(kw in q for kw in ["list", "steps", "how to", "enumerate", "top"]):
            fmt = "list"
        elif any(kw in q for kw in ["explain", "why", "describe", "summary", "essay"]):
            fmt = "prose"
        elif "?" in q and len(q.split()) < 8:
            fmt = "short_answer"
        else:
            fmt = "prose"

        return {
            "power_id": "PWR-342",
            "status": "success",
            "query": query,
            "recommended_format": fmt,
        }

    # ------------------------------------------------------------------
    # PWR-343: Context Window Optimizer
    # ------------------------------------------------------------------
    def context_window_optimizer(
        self, messages: List[Dict[str, str]], max_tokens: int = 120_000
    ) -> Dict[str, Any]:
        """PWR-343: Trims context to fit token limits.

        Uses a simple heuristic of ~4 chars per token.
        """
        CHARS_PER_TOKEN = 4
        max_chars = max_tokens * CHARS_PER_TOKEN

        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars <= max_chars:
            return {
                "power_id": "PWR-343",
                "status": "success",
                "action": "no_trim_needed",
                "original_messages": len(messages),
                "estimated_tokens": total_chars // CHARS_PER_TOKEN,
            }

        # Keep system messages + most recent messages, trim from middle
        trimmed: List[Dict[str, str]] = []
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        budget = max_chars - sum(len(m.get("content", "")) for m in system_msgs)
        kept_tail: List[Dict[str, str]] = []
        used = 0
        for m in reversed(non_system):
            c = len(m.get("content", ""))
            if used + c > budget:
                break
            kept_tail.insert(0, m)
            used += c

        trimmed = system_msgs + kept_tail
        return {
            "power_id": "PWR-343",
            "status": "success",
            "action": "trimmed",
            "original_messages": len(messages),
            "kept_messages": len(trimmed),
            "estimated_tokens": (total_chars - (total_chars - used)) // CHARS_PER_TOKEN,
            "trimmed_messages": trimmed,
        }

    # ------------------------------------------------------------------
    # PWR-344: Hash-Bound Approval Token
    # ------------------------------------------------------------------
    def hash_bound_approval(self, action: str, payload: str) -> Dict[str, Any]:
        """PWR-344: Generate HMAC-bound approval token for an action."""
        try:
            message = f"{action}:{payload}"
            token = hmac.new(
                _HMAC_SECRET.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            return {
                "power_id": "PWR-344",
                "status": "success",
                "action": action,
                "token": token,
            }
        except Exception as exc:
            return {"power_id": "PWR-344", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-345: Verify Approval Token
    # ------------------------------------------------------------------
    def verify_approval(self, token: str, action: str, payload: str) -> Dict[str, Any]:
        """PWR-345: Verify HMAC approval token."""
        try:
            message = f"{action}:{payload}"
            expected = hmac.new(
                _HMAC_SECRET.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            valid = hmac.compare_digest(token, expected)
            return {
                "power_id": "PWR-345",
                "status": "success",
                "valid": valid,
                "action": action,
            }
        except Exception as exc:
            return {"power_id": "PWR-345", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-346: Source Stamp
    # ------------------------------------------------------------------
    def source_stamp(self, content: str, source: str) -> Dict[str, Any]:
        """PWR-346: Add provenance stamp to content."""
        stamp_id = str(uuid.uuid4())[:8]
        ts = datetime.now(timezone.utc).isoformat()
        stamped = (
            f"{content}\n\n---\n"
            f"[Source: {source} | Stamp: {stamp_id} | {ts}]"
        )
        return {
            "power_id": "PWR-346",
            "status": "success",
            "stamp_id": stamp_id,
            "source": source,
            "timestamp": ts,
            "stamped_content": stamped,
        }

    # ------------------------------------------------------------------
    # PWR-347: Confidence Scorer
    # ------------------------------------------------------------------
    def confidence_scorer(self, response: str) -> Dict[str, Any]:
        """PWR-347: Score response confidence (0-1).

        Heuristic scoring based on hedging language, length, specificity.
        """
        text = response.lower()
        score = 0.75  # baseline

        # Hedge words reduce confidence
        hedges = ["maybe", "perhaps", "might", "possibly", "i think",
                  "not sure", "uncertain", "could be", "it depends"]
        hedge_count = sum(1 for h in hedges if h in text)
        score -= hedge_count * 0.08

        # Specificity markers increase confidence
        specifics = ["because", "specifically", "according to", "data shows",
                     "measured", "verified", "confirmed"]
        spec_count = sum(1 for s in specifics if s in text)
        score += spec_count * 0.05

        # Very short answers are less confident
        if len(text.split()) < 5:
            score -= 0.15

        score = round(max(0.0, min(1.0, score)), 2)

        return {
            "power_id": "PWR-347",
            "status": "success",
            "confidence": score,
            "hedge_words_found": hedge_count,
            "specificity_markers": spec_count,
        }

    # ------------------------------------------------------------------
    # PWR-348: Fallback Chain
    # ------------------------------------------------------------------
    def fallback_chain(
        self, primary: Callable[..., Any], fallbacks: List[Callable[..., Any]]
    ) -> Dict[str, Any]:
        """PWR-348: Try primary, fall through fallbacks on failure."""
        chain = [primary] + fallbacks
        errors: List[str] = []

        for idx, fn in enumerate(chain):
            try:
                result = fn()
                return {
                    "power_id": "PWR-348",
                    "status": "success",
                    "resolved_by": f"{'primary' if idx == 0 else f'fallback_{idx}'}",
                    "attempts": idx + 1,
                    "result": result,
                }
            except Exception as exc:
                errors.append(f"Step {idx}: {exc}")
                logger.warning("PWR-348 step %d failed: %s", idx, exc)

        return {
            "power_id": "PWR-348",
            "status": "all_failed",
            "attempts": len(chain),
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # PWR-349: Task Decomposer
    # ------------------------------------------------------------------
    def task_decomposer(self, complex_task: str) -> Dict[str, Any]:
        """PWR-349: Break task into subtasks via heuristic analysis."""
        parts = [s.strip() for s in complex_task.replace(" and ", "\n").replace(
            " then ", "\n").replace(", ", "\n").split("\n") if s.strip()]

        subtasks = []
        for i, part in enumerate(parts, 1):
            subtasks.append({
                "id": f"SUB-{i:03d}",
                "description": part,
                "estimated_complexity": (
                    "high" if len(part.split()) > 12 else
                    "medium" if len(part.split()) > 5 else "low"
                ),
                "dependencies": [f"SUB-{i-1:03d}"] if i > 1 else [],
            })

        return {
            "power_id": "PWR-349",
            "status": "success",
            "original_task": complex_task,
            "subtasks": subtasks,
            "count": len(subtasks),
        }

    # ------------------------------------------------------------------
    # PWR-350: Parallel Dispatch Plan
    # ------------------------------------------------------------------
    def parallel_dispatch_plan(self, subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """PWR-350: Plan parallel execution of subtasks.

        Groups subtasks into waves based on dependencies.
        """
        completed: set[str] = set()
        waves: List[List[Dict[str, Any]]] = []
        remaining = list(subtasks)

        max_iterations = len(remaining) + 1
        for _ in range(max_iterations):
            if not remaining:
                break
            wave: List[Dict[str, Any]] = []
            still_remaining: List[Dict[str, Any]] = []
            for st in remaining:
                deps = set(st.get("dependencies", []))
                if deps.issubset(completed):
                    wave.append(st)
                else:
                    still_remaining.append(st)
            if not wave:
                # Deadlock — force remaining into last wave
                wave = still_remaining
                still_remaining = []
            completed.update(st.get("id", "") for st in wave)
            waves.append(wave)
            remaining = still_remaining

        return {
            "power_id": "PWR-350",
            "status": "success",
            "waves": [
                {"wave": i + 1, "tasks": [t.get("id", "") for t in w]}
                for i, w in enumerate(waves)
            ],
            "total_waves": len(waves),
            "max_parallelism": max(len(w) for w in waves) if waves else 0,
        }

    # ------------------------------------------------------------------
    # PWR-351: Result Merger
    # ------------------------------------------------------------------
    def result_merger(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """PWR-351: Merge results from parallel tasks."""
        merged_data: Dict[str, Any] = {}
        errors: List[str] = []
        success_count = 0

        for r in results:
            task_id = r.get("id", r.get("power_id", f"unknown_{id(r)}"))
            status = r.get("status", "unknown")
            if status in ("success", "ok"):
                success_count += 1
                merged_data[task_id] = {
                    k: v for k, v in r.items() if k not in ("id", "status")
                }
            else:
                errors.append(f"{task_id}: {r.get('error', status)}")

        return {
            "power_id": "PWR-351",
            "status": "success" if not errors else "partial",
            "total_results": len(results),
            "successful": success_count,
            "failed": len(errors),
            "merged_data": merged_data,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # PWR-352: Quality Gate
    # ------------------------------------------------------------------
    def quality_gate(self, result: Dict[str, Any], criteria: Dict[str, Any]) -> Dict[str, Any]:
        """PWR-352: Check if result meets quality criteria.

        Criteria keys: min_length, required_fields, max_errors, min_confidence.
        """
        passed = True
        checks: List[Dict[str, Any]] = []

        if "min_length" in criteria:
            content = str(result.get("content", result.get("result", "")))
            ok = len(content) >= criteria["min_length"]
            checks.append({"check": "min_length", "passed": ok, "value": len(content)})
            if not ok:
                passed = False

        if "required_fields" in criteria:
            missing = [f for f in criteria["required_fields"] if f not in result]
            ok = len(missing) == 0
            checks.append({"check": "required_fields", "passed": ok, "missing": missing})
            if not ok:
                passed = False

        if "max_errors" in criteria:
            errs = len(result.get("errors", []))
            ok = errs <= criteria["max_errors"]
            checks.append({"check": "max_errors", "passed": ok, "error_count": errs})
            if not ok:
                passed = False

        if "min_confidence" in criteria:
            conf = result.get("confidence", 0)
            ok = conf >= criteria["min_confidence"]
            checks.append({"check": "min_confidence", "passed": ok, "confidence": conf})
            if not ok:
                passed = False

        return {
            "power_id": "PWR-352",
            "status": "pass" if passed else "fail",
            "passed": passed,
            "checks": checks,
        }

    # ------------------------------------------------------------------
    # PWR-353: Rollback Plan
    # ------------------------------------------------------------------
    def rollback_plan(self, action: str) -> Dict[str, Any]:
        """PWR-353: Generate rollback steps for an action."""
        rollback_templates: Dict[str, List[str]] = {
            "file_write":    ["Restore file from backup", "Verify file integrity"],
            "file_delete":   ["Restore from recycle bin or backup", "Verify restoration"],
            "deploy":        ["Revert to previous deployment", "Run health checks",
                              "Notify team of rollback"],
            "database":      ["Restore from snapshot", "Verify data consistency",
                              "Run integrity checks"],
            "config_change": ["Restore previous config", "Restart affected services",
                              "Verify service health"],
            "email_send":    ["Send correction/retraction email",
                              "Log incident for audit"],
            "install":       ["Uninstall package", "Restore previous version",
                              "Verify system stability"],
        }

        action_lower = action.lower()
        steps: List[str] = []
        for key, template_steps in rollback_templates.items():
            if key in action_lower:
                steps = template_steps
                break

        if not steps:
            steps = [
                f"Document what '{action}' changed",
                "Identify affected systems/files",
                "Restore to pre-action state from backup",
                "Verify restoration",
                "Log rollback for audit trail",
            ]

        return {
            "power_id": "PWR-353",
            "status": "success",
            "action": action,
            "rollback_steps": [
                {"step": i, "description": s} for i, s in enumerate(steps, 1)
            ],
        }

    # ------------------------------------------------------------------
    # PWR-354: Time Ledger Entry
    # ------------------------------------------------------------------
    def time_ledger_entry(self, task: str, duration_min: float) -> Dict[str, Any]:
        """PWR-354: Log time spent on task."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            ledger: List[Dict[str, Any]] = []
            if _TIME_LEDGER_FILE.exists():
                ledger = json.loads(_TIME_LEDGER_FILE.read_text(encoding="utf-8"))

            entry = {
                "id": str(uuid.uuid4())[:8],
                "task": task,
                "duration_min": round(duration_min, 2),
                "logged_at": datetime.now(timezone.utc).isoformat(),
            }
            ledger.append(entry)
            _TIME_LEDGER_FILE.write_text(
                json.dumps(ledger, indent=2), encoding="utf-8"
            )

            total_today = sum(
                e["duration_min"] for e in ledger
                if e["logged_at"][:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")
            )
            return {
                "power_id": "PWR-354",
                "status": "success",
                "entry": entry,
                "total_today_min": round(total_today, 2),
            }
        except Exception as exc:
            return {"power_id": "PWR-354", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-355: Never Estimate Rule
    # ------------------------------------------------------------------
    def never_estimate_rule(self, query: str) -> Dict[str, Any]:
        """PWR-355: Flag if query asks for estimate, enforce 'measure don't estimate'."""
        q = query.lower()
        estimate_signals = [
            "estimate", "guess", "approximate", "roughly", "ballpark",
            "how long will", "how much time", "when will it be done",
            "predict", "forecast time", "how many hours",
        ]

        triggered = [s for s in estimate_signals if s in q]

        if triggered:
            return {
                "power_id": "PWR-355",
                "status": "flagged",
                "triggered_by": triggered,
                "guidance": (
                    "JARVIS Rule: Measure, don't estimate. "
                    "Break the task into sub-tasks, time each one, "
                    "and sum measured durations. Use PWR-349 (task_decomposer) "
                    "and PWR-354 (time_ledger_entry) instead."
                ),
            }
        return {
            "power_id": "PWR-355",
            "status": "clear",
            "message": "Query does not request an estimate.",
        }


research_derived_powers = ResearchDerivedPowers()
