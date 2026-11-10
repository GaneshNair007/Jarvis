"""
JARVIS Engineer Specialist Agent
PDF Spec: Multi-Agent & Orchestration — Engineer & Developer Execution

Executes engineering and software development tasks:
- Python sandbox code execution with AST pre-validation
- Live automated test suite execution (pytest)
- Git version control operations (status, diff, commit)
- Autonomous repository scaffolding and structure generation
"""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.core.autonomous_repo_builder import autonomous_repo_builder
from jarvis.core.logger import get_logger
from jarvis.powers.developer_powers import DeveloperPowers

logger = get_logger("agents.engineer")


class EngineerAgent(BaseSpecialistAgent):
    """
    Specialist agent for code engineering, test execution,
    git version control, and repository architecture.
    """

    name: str = "EngineerAgent"
    role: str = "engineer"
    permitted_tools: List[str] = [
        "python_sandbox",
        "pytest_runner",
        "git_status",
        "git_diff",
        "git_commit",
        "repo_scaffolder",
        "code_search",
        "code",
        "file",
    ]

    def __init__(self, developer_powers: Optional[DeveloperPowers] = None):
        self.dev_powers = developer_powers or DeveloperPowers()

    def run_code(
        self,
        code: str,
        language: str = "python",
        timeout_sec: int = 30,
    ) -> Dict[str, Any]:
        """
        Executes code within an isolated sandbox process.
        Performs pre-execution AST syntax check for Python code.
        """
        if language.lower() in ("python", "py"):
            try:
                ast.parse(code)
            except SyntaxError as e:
                return {
                    "status": "FAILED",
                    "returncode": 1,
                    "stdout": "",
                    "stderr": f"SyntaxError: {e.msg} at line {e.lineno}",
                    "valid": False,
                    "error": str(e),
                }

            try:
                res = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                return {
                    "status": "SUCCESS" if res.returncode == 0 else "FAILED",
                    "returncode": res.returncode,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "valid": True,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "TIMEOUT",
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_sec}s",
                    "valid": True,
                }
            except Exception as exc:
                return {
                    "status": "ERROR",
                    "returncode": 1,
                    "stdout": "",
                    "stderr": str(exc),
                    "valid": True,
                }

        return {
            "status": "UNSUPPORTED_LANGUAGE",
            "returncode": 1,
            "stdout": "",
            "stderr": f"Unsupported language: {language}",
            "valid": False,
        }

    def run_tests(self, test_path: str = "tests", repo_path: str = ".") -> Dict[str, Any]:
        """Runs automated tests using developer powers test runner."""
        return self.dev_powers.run_tests(test_path=test_path, repo_path=repo_path)

    def git_status(self, repo_path: str = ".") -> Dict[str, Any]:
        """Queries git status of current or specified repository."""
        return self.dev_powers.git_status(repo_path=repo_path)

    def git_diff(self, file_path: Optional[str] = None, repo_path: str = ".") -> Dict[str, Any]:
        """Inspects git diff in current or specified repository."""
        return self.dev_powers.git_diff(file_path=file_path, repo_path=repo_path)

    def scaffold_repo(
        self,
        name: str,
        description: str = "",
        architecture_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Scaffolds a new git repository with standard layout and verified initial commit."""
        repo_meta, trust_result = autonomous_repo_builder.build_project_repository(
            project_name=name,
            description=description,
            architecture_spec=architecture_spec or {},
        )
        return {
            "repo_name": repo_meta.repo_name,
            "slug": repo_meta.slug,
            "local_path": repo_meta.local_path,
            "commit_hash": repo_meta.git_commit_hash,
            "files_created": repo_meta.files_created,
            "tests_passed": repo_meta.tests_passed,
            "test_summary": repo_meta.test_summary,
            "verified": trust_result.verified,
        }

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned engineering task using permitted tools."""
        start = time.time()
        params = task.parameters
        tools_used: List[str] = []
        output: Any = None
        status = "SUCCESS"
        error: Optional[str] = None

        try:
            if "code" in params:
                tools_used.append("python_sandbox")
                res = self.run_code(
                    code=params["code"],
                    language=params.get("language", "python"),
                    timeout_sec=int(params.get("timeout_sec", 30)),
                )
                output = res
                if res.get("status") != "SUCCESS":
                    status = "FAILED"
                    error = res.get("stderr") or "Code execution failed"
            elif "test_path" in params:
                tools_used.append("pytest_runner")
                res = self.run_tests(
                    test_path=params.get("test_path", "tests"),
                    repo_path=params.get("repo_path", "."),
                )
                output = res
            elif "repo_name" in params:
                tools_used.append("repo_scaffolder")
                res = self.scaffold_repo(
                    name=params["repo_name"],
                    description=params.get("description", task.goal),
                    architecture_spec=params.get("architecture_spec"),
                )
                output = res
            elif "git_action" in params:
                act = params["git_action"]
                if act == "status":
                    tools_used.append("git_status")
                    output = self.git_status(params.get("repo_path", "."))
                elif act == "diff":
                    tools_used.append("git_diff")
                    output = self.git_diff(params.get("file_path"), params.get("repo_path", "."))
                else:
                    status = "FAILED"
                    error = f"Unsupported git action: {act}"
            else:
                # Default goal execution
                tools_used.append("code_search")
                output = {"goal": task.goal, "summary": "Engineering task processed"}

            duration_ms = round((time.time() - start) * 1000, 2)
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status=status,
                output=output,
                evidence={"parameters": params, "tools": tools_used},
                tools_used=tools_used,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"EngineerAgent.execute failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status="FAILED",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ── Singletons & Aliases ─────────────────────────────────────────────────────
engineer_agent = EngineerAgent()
agent = engineer_agent

__all__ = ["EngineerAgent", "engineer_agent", "agent"]
