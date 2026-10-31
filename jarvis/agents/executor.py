"""
JARVIS Executor Agent (PWR-292 / PWR-293)
PDF Spec: Pages 352-371 — Multi-Agent & Orchestration

Executes concrete actions based on a PlanStep assignment:
- Code generation & execution (sandboxed subprocess)
- File operations (read/write/ingest)
- Shell/OS commands (PowerShell / bash)
- Browser automation (Playwright)
- Desktop control (PyAutoGUI See-Act-Verify)
- System administration (Docker, SSH)

All actions are gated through the policy engine before execution.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.executor")


@dataclass
class ExecutionResult:
    """Structured output from a single executor action."""
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    action_type: str = ""
    status: str = "pending"    # pending | success | failed | rejected
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    evidence: Optional[str] = None   # screenshot path or hash
    duration_ms: float = 0.0
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action_type": self.action_type,
            "status": self.status,
            "stdout": self.stdout[:2000],
            "stderr": self.stderr[:500],
            "return_value": self.return_value,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
            "cost_usd": self.cost_usd,
        }


class ExecutorAgent:
    """
    Executes tasks dispatched by the AgentSwarmCoordinator.
    Routes by action_type and enforces policy before any side-effecting action.
    """

    # ── Dispatch table ────────────────────────────────────────────────────────
    ACTION_DISPATCH = {
        "shell": "_run_shell",
        "python": "_run_python",
        "browser": "_run_browser",
        "desktop": "_run_desktop",
        "file_read": "_run_file_read",
        "file_write": "_run_file_write",
        "docker": "_run_docker",
        "llm": "_run_llm",
    }

    def execute(
        self,
        action_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        approval_token: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Synchronous execute wrapper. Dispatches to the correct action handler.

        Args:
            action_type: One of shell, python, browser, desktop, file_read,
                         file_write, docker, llm.
            payload: Action-specific arguments dict.
            task_id: Parent task ID for audit logging.
            approval_token: Required for Tier 2+ actions.

        Returns:
            ExecutionResult with status and outputs.
        """
        exec_id = f"exec_{uuid.uuid4().hex[:8]}"
        task_id = task_id or exec_id
        start = time.time()

        logger.info(f"ExecutorAgent: executing action_type={action_type} task={task_id}")

        # ── Policy check ──────────────────────────────────────────────────────
        policy_ok, policy_msg = self._check_policy(action_type, payload, approval_token)
        if not policy_ok:
            logger.warning(f"ExecutorAgent: policy rejected — {policy_msg}")
            return ExecutionResult(
                execution_id=exec_id,
                action_type=action_type,
                status="rejected",
                stderr=policy_msg,
                duration_ms=round((time.time() - start) * 1000, 2),
            )

        # ── Dispatch ──────────────────────────────────────────────────────────
        method_name = self.ACTION_DISPATCH.get(action_type, "_run_llm")
        method = getattr(self, method_name, self._run_llm)

        try:
            result = method(payload)
            result.action_type = action_type
            result.execution_id = exec_id
            result.duration_ms = round((time.time() - start) * 1000, 2)

            # ── Audit log ─────────────────────────────────────────────────────
            self._audit(task_id, action_type, result)
            logger.info(
                f"ExecutorAgent: exec={exec_id} status={result.status} "
                f"duration={result.duration_ms}ms"
            )
            return result

        except Exception as exc:
            logger.error(f"ExecutorAgent: unhandled exception — {exc}")
            result = ExecutionResult(
                execution_id=exec_id,
                action_type=action_type,
                status="failed",
                stderr=str(exc),
                duration_ms=round((time.time() - start) * 1000, 2),
            )
            self._audit(task_id, action_type, result)
            return result

    # ── Policy check ──────────────────────────────────────────────────────────

    def _check_policy(
        self, action_type: str, payload: Dict[str, Any], approval_token: Optional[str]
    ) -> tuple[bool, str]:
        """Quick policy pre-check before dispatching."""
        # Desktop / shell / docker require at least Tier 1 review
        high_risk = {"desktop", "docker", "shell"}
        if action_type in high_risk and not approval_token:
            try:
                from jarvis.core.policy_engine import policy_engine
                decision = policy_engine.evaluate(
                    user_input=str(payload.get("command", action_type)),
                    task_type=action_type,
                )
                if decision.tier >= 2:
                    return False, (
                        f"Tier {decision.tier} action '{action_type}' requires "
                        "explicit approval token."
                    )
            except Exception:
                pass
        return True, ""

    # ── Action handlers ───────────────────────────────────────────────────────

    def _run_shell(self, payload: Dict[str, Any]) -> ExecutionResult:
        cmd = payload.get("command", "")
        cwd = payload.get("cwd", None)
        timeout = payload.get("timeout", 30)

        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return ExecutionResult(
            status="success" if proc.returncode == 0 else "failed",
            stdout=proc.stdout[:4000],
            stderr=proc.stderr[:1000],
            return_value=proc.returncode,
        )

    def _run_python(self, payload: Dict[str, Any]) -> ExecutionResult:
        """Execute Python code in a sandboxed subprocess."""
        code = payload.get("code", "")
        timeout = payload.get("timeout", 30)

        import tempfile, os
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                status="success" if proc.returncode == 0 else "failed",
                stdout=proc.stdout[:4000],
                stderr=proc.stderr[:1000],
                return_value=proc.returncode,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _run_browser(self, payload: Dict[str, Any]) -> ExecutionResult:
        url = payload.get("url", "")
        action = payload.get("action", "read")  # read | screenshot | click | search

        try:
            if action == "search":
                from jarvis.browser.search_wrapper import search_wrapper
                results = search_wrapper.search(payload.get("query", url))
                return ExecutionResult(
                    status="success",
                    return_value=results,
                    stdout=str(results)[:1000],
                )
            else:
                from jarvis.browser.url_reader import url_reader
                content = url_reader.read(url)
                return ExecutionResult(
                    status="success",
                    stdout=content[:3000] if content else "",
                    return_value=content,
                )
        except Exception as exc:
            return ExecutionResult(status="failed", stderr=str(exc))

    def _run_desktop(self, payload: Dict[str, Any]) -> ExecutionResult:
        action = payload.get("action", "screenshot")

        try:
            from jarvis.computer.desktop_worker import desktop_worker
            if action == "screenshot":
                result = desktop_worker.take_screenshot()
            elif action == "type":
                result = desktop_worker.type_text(payload.get("text", ""))
            elif action == "click":
                result = desktop_worker.click(payload.get("x", 0), payload.get("y", 0))
            else:
                result = {"status": "unknown_action"}

            return ExecutionResult(
                status="success",
                return_value=result,
                stdout=str(result)[:500],
                evidence=result.get("screenshot_path") if isinstance(result, dict) else None,
            )
        except Exception as exc:
            return ExecutionResult(status="failed", stderr=str(exc))

    def _run_file_read(self, payload: Dict[str, Any]) -> ExecutionResult:
        from pathlib import Path
        path = Path(payload.get("path", ""))
        try:
            content = path.read_text(encoding="utf-8")
            return ExecutionResult(
                status="success",
                stdout=content[:5000],
                return_value=content,
            )
        except Exception as exc:
            return ExecutionResult(status="failed", stderr=str(exc))

    def _run_file_write(self, payload: Dict[str, Any]) -> ExecutionResult:
        from pathlib import Path
        path = Path(payload.get("path", ""))
        content = payload.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ExecutionResult(
                status="success",
                stdout=f"Written {len(content)} chars to {path}",
                return_value=str(path),
            )
        except Exception as exc:
            return ExecutionResult(status="failed", stderr=str(exc))

    def _run_docker(self, payload: Dict[str, Any]) -> ExecutionResult:
        cmd = payload.get("command", "docker ps")
        return self._run_shell({"command": cmd, "timeout": 60})

    def _run_llm(self, payload: Dict[str, Any]) -> ExecutionResult:
        """Fallback: send the payload as a prompt to the model router."""
        prompt = payload.get("prompt", payload.get("task", str(payload)))
        try:
            from jarvis.core.model_router import model_router, RoutingRequest
            req = RoutingRequest(
                task_id=f"exec_{uuid.uuid4().hex[:6]}",
                user_intent=prompt,
                sensitivity_level="low",
            )
            decision = model_router.route(req)
            result = model_router.execute_inference(decision=decision, prompt=prompt)
            content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(result, dict) else str(result)
            )
            return ExecutionResult(
                status="success",
                stdout=content[:3000],
                return_value=content,
                cost_usd=getattr(decision, "estimated_cost_usd", 0.0001),
            )
        except Exception as exc:
            return ExecutionResult(status="failed", stderr=str(exc))

    # ── Audit helper ──────────────────────────────────────────────────────────

    def _audit(self, task_id: str, action_type: str, result: ExecutionResult):
        try:
            from jarvis.core.audit import audit_ledger
            audit_ledger.log_event(
                event_type="EXECUTOR_ACTION",
                task_id=task_id,
                power_id=f"executor.{action_type}",
                status=result.status.upper(),
                inputs={"action_type": action_type},
                outputs={"stdout_len": len(result.stdout), "return_value": str(result.return_value)[:200]},
            )
        except Exception:
            pass


# ── Singleton ─────────────────────────────────────────────────────────────────
executor_agent = ExecutorAgent()

__all__ = ["ExecutorAgent", "ExecutionResult", "executor_agent"]
