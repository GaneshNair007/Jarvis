"""JARVIS Developer Powers (PWR-025 to PWR-047).

Provides Git management, automated diff inspection, commit creation,
test runner dispatch, and code health diagnostics.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("powers.developer")


class DeveloperPowers:
    """Implementations for Developer and Code Assistance domain capabilities."""

    def git_status(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-025: Checks git status of the working tree."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            ).stdout.strip()
            modified = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return {
                "power_id": "PWR-025",
                "branch": branch or "main",
                "clean": len(modified) == 0,
                "modified_files_count": len(modified),
                "modified_files": modified[:20]
            }
        except Exception as e:
            return {"power_id": "PWR-025", "error": str(e), "clean": False}

    def git_diff(self, file_path: Optional[str] = None, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-026: Produces git diff of unstaged or staged changes."""
        try:
            cmd = ["git", "diff"]
            if file_path:
                cmd.append(file_path)
            res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=10)
            return {
                "power_id": "PWR-026",
                "diff_length": len(res.stdout),
                "diff_preview": res.stdout[:2000]
            }
        except Exception as e:
            return {"power_id": "PWR-026", "error": str(e)}

    def run_tests(self, test_path: str = "tests", repo_path: str = ".") -> Dict[str, Any]:
        """PWR-027: Executes local test suite."""
        try:
            res = subprocess.run(
                ["python", "-m", "pytest", test_path, "-q"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "power_id": "PWR-027",
                "exit_code": res.returncode,
                "passed": res.returncode == 0,
                "summary": res.stdout.splitlines()[-1] if res.stdout.splitlines() else "No output"
            }
        except Exception as e:
            return {"power_id": "PWR-027", "error": str(e), "passed": False}


developer_powers = DeveloperPowers()

