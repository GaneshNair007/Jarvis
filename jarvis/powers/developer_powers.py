"""JARVIS Developer Powers (PWR-025 to PWR-047, PWR-162 to PWR-178).

Provides Git management, automated diff inspection, commit creation,
test runner dispatch, code health diagnostics, and developer tooling.
"""

from __future__ import annotations

import inspect
import os
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("powers.developer")


class DeveloperPowers:
    """Implementations for Developer and Code Assistance domain capabilities."""

    def git_status(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-025: Checks git status of the working tree."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True, timeout=10
            )
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=repo_path, capture_output=True, text=True, timeout=5
            ).stdout.strip()
            modified = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return {
                "power_id": "PWR-025",
                "branch": branch or "main",
                "clean": len(modified) == 0,
                "modified_files_count": len(modified),
                "modified_files": modified[:20],
            }
        except Exception as e:
            return {"power_id": "PWR-025", "error": str(e), "clean": False}

    def git_diff(self, file_path: Optional[str] = None, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-026: Produces git diff of unstaged or staged changes."""
        try:
            cmd = ["git", "diff"]
            if file_path:
                cmd.append(file_path)
            res = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
            )
            diff_out = res.stdout or ""
            return {"power_id": "PWR-026", "diff_length": len(diff_out), "diff_preview": diff_out[:2000]}
        except Exception as e:
            return {"power_id": "PWR-026", "error": str(e)}

    def run_tests(self, test_path: str = "tests", repo_path: str = ".") -> Dict[str, Any]:
        """PWR-027: Executes local test suite."""
        try:
            res = subprocess.run(
                ["python", "-m", "pytest", test_path, "-q"], cwd=repo_path, capture_output=True, text=True, timeout=60
            )
            return {
                "power_id": "PWR-027",
                "exit_code": res.returncode,
                "passed": res.returncode == 0,
                "summary": res.stdout.splitlines()[-1] if res.stdout.splitlines() else "No output",
            }
        except Exception as e:
            return {"power_id": "PWR-027", "error": str(e), "passed": False}

    # ------------------------------------------------------------------
    # Code Search & Analysis (PWR-162 to PWR-168)
    # ------------------------------------------------------------------

    def code_search(self, pattern: str, directory: str = ".") -> Dict[str, Any]:
        """PWR-162: Grep/findstr for pattern in codebase."""
        try:
            # Use findstr on Windows, grep on POSIX
            if os.name == "nt":
                cmd = ["findstr", "/S", "/N", "/I", "/C:" + pattern, "*.*"]
            else:
                cmd = ["grep", "-rn", "--include=*.py", pattern, "."]
            res = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            lines = res.stdout.strip().splitlines()
            matches = []
            for line in lines[:100]:
                matches.append(line.strip())
            return {
                "power_id": "PWR-162",
                "status": "success",
                "pattern": pattern,
                "match_count": len(lines),
                "matches": matches,
            }
        except Exception as e:
            return {"power_id": "PWR-162", "status": "error", "message": str(e)}

    def code_explain(self, file_path: str, start_line: int = 1, end_line: int = 50) -> Dict[str, Any]:
        """PWR-163: Read code lines and return them for analysis."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            selected = all_lines[max(0, start_line - 1) : end_line]
            code_block = "".join(selected)
            return {
                "power_id": "PWR-163",
                "status": "success",
                "file_path": file_path,
                "total_lines": len(all_lines),
                "range": f"{start_line}-{end_line}",
                "code": code_block[:5000],
            }
        except FileNotFoundError:
            return {"power_id": "PWR-163", "status": "error", "message": f"File not found: {file_path}"}
        except Exception as e:
            return {"power_id": "PWR-163", "status": "error", "message": str(e)}

    def generate_docstring(self, file_path: str, function_name: str) -> Dict[str, Any]:
        """PWR-164: Generate a docstring template for a function."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            # Find function definition
            pattern = rf"def\s+{re.escape(function_name)}\s*\(([^)]*)\)"
            match = re.search(pattern, source)
            if not match:
                return {
                    "power_id": "PWR-164",
                    "status": "error",
                    "message": f"Function '{function_name}' not found in {file_path}",
                }

            params_str = match.group(1)
            params = [
                p.strip().split(":")[0].strip().split("=")[0].strip()
                for p in params_str.split(",")
                if p.strip() and p.strip() != "self"
            ]

            # Build docstring
            docstring_lines = [f'    """<Short description of {function_name}.>', ""]
            if params:
                docstring_lines.append("    Args:")
                for p in params:
                    docstring_lines.append(f"        {p}: <description>")
                docstring_lines.append("")
            docstring_lines.append("    Returns:")
            docstring_lines.append("        <description>")
            docstring_lines.append('    """')

            return {
                "power_id": "PWR-164",
                "status": "success",
                "function_name": function_name,
                "parameters": params,
                "docstring_template": "\n".join(docstring_lines),
            }
        except Exception as e:
            return {"power_id": "PWR-164", "status": "error", "message": str(e)}

    def lint_check(self, file_path: Optional[str] = None, directory: str = ".") -> Dict[str, Any]:
        """PWR-165: Run ruff or flake8 for linting."""
        try:
            target = file_path or directory
            # Try ruff first, fall back to flake8
            for tool in ["ruff check", "flake8"]:
                cmd_parts = tool.split() + [target]
                try:
                    res = subprocess.run(
                        cmd_parts,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                        errors="replace",
                    )
                    issues = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                    return {
                        "power_id": "PWR-165",
                        "status": "success",
                        "tool": tool.split()[0],
                        "target": target,
                        "issue_count": len(issues),
                        "issues": issues[:50],
                        "exit_code": res.returncode,
                    }
                except FileNotFoundError:
                    continue
            return {"power_id": "PWR-165", "status": "error", "message": "Neither ruff nor flake8 found on PATH"}
        except Exception as e:
            return {"power_id": "PWR-165", "status": "error", "message": str(e)}

    def format_code(self, file_path: str) -> Dict[str, Any]:
        """PWR-166: Run black or ruff format on a file."""
        try:
            for tool_cmd in [["ruff", "format", file_path], ["black", file_path]]:
                try:
                    res = subprocess.run(
                        tool_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    return {
                        "power_id": "PWR-166",
                        "status": "success",
                        "tool": tool_cmd[0],
                        "file": file_path,
                        "output": (res.stdout or res.stderr).strip()[:2000],
                        "exit_code": res.returncode,
                    }
                except FileNotFoundError:
                    continue
            return {"power_id": "PWR-166", "status": "error", "message": "Neither ruff nor black found on PATH"}
        except Exception as e:
            return {"power_id": "PWR-166", "status": "error", "message": str(e)}

    def dependency_audit(self) -> Dict[str, Any]:
        """PWR-167: pip list + check for outdated packages."""
        try:
            res = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            import json

            try:
                outdated = json.loads(res.stdout) if res.stdout.strip() else []
            except json.JSONDecodeError:
                outdated = []

            total_res = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            try:
                total = json.loads(total_res.stdout) if total_res.stdout.strip() else []
            except json.JSONDecodeError:
                total = []

            return {
                "power_id": "PWR-167",
                "status": "success",
                "total_packages": len(total),
                "outdated_count": len(outdated),
                "outdated": outdated[:50],
            }
        except Exception as e:
            return {"power_id": "PWR-167", "status": "error", "message": str(e)}

    def create_test_stub(self, module_path: str) -> Dict[str, Any]:
        """PWR-168: Generate pytest test stub for a Python module."""
        try:
            with open(module_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            # Extract function and class names
            functions = re.findall(r"^def\s+(\w+)\s*\(", source, re.MULTILINE)
            classes = re.findall(r"^class\s+(\w+)", source, re.MULTILINE)

            module_name = Path(module_path).stem
            lines = [
                f'"""Tests for {module_name}."""',
                "",
                "import pytest",
                "",
            ]

            for func in functions:
                if func.startswith("_"):
                    continue
                lines.extend(
                    [
                        f"def test_{func}():",
                        f'    """Test {func} function."""',
                        f"    # TODO: Implement test for {func}",
                        "    assert True",
                        "",
                    ]
                )

            for cls in classes:
                lines.extend(
                    [
                        f"class Test{cls}:",
                        f'    """Tests for {cls}."""',
                        "",
                        f"    def test_{cls.lower()}_init(self):",
                        f'        """Test {cls} initialization."""',
                        "        # TODO: Implement test",
                        "        assert True",
                        "",
                    ]
                )

            stub_content = "\n".join(lines)
            return {
                "power_id": "PWR-168",
                "status": "success",
                "module": module_path,
                "functions_found": functions,
                "classes_found": classes,
                "test_stub": stub_content,
            }
        except Exception as e:
            return {"power_id": "PWR-168", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Git Operations (PWR-169 to PWR-172)
    # ------------------------------------------------------------------

    def git_log(self, count: int = 10, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-169: Recent git log entries."""
        try:
            res = subprocess.run(
                ["git", "log", f"--max-count={count}", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=short"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commits: List[Dict[str, str]] = []
            for line in res.stdout.strip().splitlines():
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "email": parts[2],
                            "date": parts[3],
                            "message": parts[4],
                        }
                    )
            return {
                "power_id": "PWR-169",
                "status": "success",
                "count": len(commits),
                "commits": commits,
            }
        except Exception as e:
            return {"power_id": "PWR-169", "status": "error", "message": str(e)}

    def git_commit(self, message: str, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-170: Stage all changes and commit. Requires user approval."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return {
                "power_id": "PWR-170",
                "status": "success" if res.returncode == 0 else "error",
                "message": message,
                "output": (res.stdout or res.stderr).strip()[:2000],
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-170", "status": "error", "message": str(e), "approval_required": True}

    def git_push(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-171: Push to origin. Requires user approval."""
        try:
            res = subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "power_id": "PWR-171",
                "status": "success" if res.returncode == 0 else "error",
                "output": (res.stdout or res.stderr).strip()[:2000],
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-171", "status": "error", "message": str(e), "approval_required": True}

    def git_branch_list(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-172: List git branches."""
        try:
            res = subprocess.run(
                ["git", "branch", "-a"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            branches = []
            current_branch = ""
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("*"):
                    current_branch = line[2:].strip()
                    branches.append(current_branch)
                else:
                    branches.append(line)
            return {
                "power_id": "PWR-172",
                "status": "success",
                "current_branch": current_branch,
                "branch_count": len(branches),
                "branches": branches,
            }
        except Exception as e:
            return {"power_id": "PWR-172", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Package & Environment (PWR-173 to PWR-178)
    # ------------------------------------------------------------------

    def pip_install(self, package: str) -> Dict[str, Any]:
        """PWR-173: pip install a package. Requires user approval."""
        try:
            res = subprocess.run(
                ["pip", "install", package],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "power_id": "PWR-173",
                "status": "success" if res.returncode == 0 else "error",
                "package": package,
                "output": (res.stdout or res.stderr).strip()[-2000:],
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-173", "status": "error", "message": str(e), "approval_required": True}

    def file_structure(self, directory: str = ".", depth: int = 3) -> Dict[str, Any]:
        """PWR-174: Directory tree up to a given depth."""
        try:
            tree_lines: List[str] = []

            def _walk(path: str, prefix: str, current_depth: int) -> None:
                if current_depth > depth:
                    return
                try:
                    entries = sorted(os.listdir(path))
                except PermissionError:
                    tree_lines.append(f"{prefix}[Permission Denied]")
                    return

                # Filter out common noise
                skip = {
                    ".git",
                    "__pycache__",
                    "node_modules",
                    ".venv",
                    "venv",
                    ".tox",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".ruff_cache",
                }
                entries = [e for e in entries if e not in skip]

                for i, entry in enumerate(entries):
                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    full = os.path.join(path, entry)
                    tree_lines.append(f"{prefix}{connector}{entry}")
                    if os.path.isdir(full):
                        extension = "    " if is_last else "│   "
                        _walk(full, prefix + extension, current_depth + 1)

            abs_dir = os.path.abspath(directory)
            tree_lines.append(os.path.basename(abs_dir) + "/")
            _walk(abs_dir, "", 1)

            return {
                "power_id": "PWR-174",
                "status": "success",
                "directory": abs_dir,
                "depth": depth,
                "tree": "\n".join(tree_lines[:500]),
            }
        except Exception as e:
            return {"power_id": "PWR-174", "status": "error", "message": str(e)}

    def count_lines(self, directory: str = ".") -> Dict[str, Any]:
        """PWR-175: Lines of code count by file extension."""
        try:
            counts: Dict[str, int] = {}
            file_count = 0
            skip_dirs = {
                ".git",
                "__pycache__",
                "node_modules",
                ".venv",
                "venv",
                ".tox",
                ".mypy_cache",
                ".eggs",
                "dist",
                "build",
            }

            for root, dirs, files in os.walk(os.path.abspath(directory)):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    ext = os.path.splitext(f)[1] or "(no ext)"
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            lc = sum(1 for _ in fh)
                        counts[ext] = counts.get(ext, 0) + lc
                        file_count += 1
                    except (OSError, UnicodeDecodeError):
                        pass

            sorted_counts = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
            return {
                "power_id": "PWR-175",
                "status": "success",
                "directory": os.path.abspath(directory),
                "total_files": file_count,
                "total_lines": sum(counts.values()),
                "by_extension": sorted_counts,
            }
        except Exception as e:
            return {"power_id": "PWR-175", "status": "error", "message": str(e)}

    def todo_scan(self, directory: str = ".") -> Dict[str, Any]:
        """PWR-176: Find TODO/FIXME/HACK comments in code."""
        try:
            markers = ["TODO", "FIXME", "HACK", "XXX", "BUG"]
            findings: List[Dict[str, Any]] = []
            skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
            code_exts = {
                ".py",
                ".js",
                ".ts",
                ".java",
                ".c",
                ".cpp",
                ".go",
                ".rs",
                ".rb",
                ".php",
                ".sh",
                ".bat",
                ".ps1",
                ".yaml",
                ".yml",
                ".toml",
            }

            for root, dirs, files in os.walk(os.path.abspath(directory)):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    ext = os.path.splitext(f)[1]
                    if ext not in code_exts:
                        continue
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            for line_no, line in enumerate(fh, 1):
                                for marker in markers:
                                    if marker in line:
                                        findings.append(
                                            {
                                                "file": os.path.relpath(fp, directory),
                                                "line": line_no,
                                                "marker": marker,
                                                "text": line.strip()[:200],
                                            }
                                        )
                                        break
                    except (OSError, UnicodeDecodeError):
                        pass

            return {
                "power_id": "PWR-176",
                "status": "success",
                "directory": os.path.abspath(directory),
                "finding_count": len(findings),
                "findings": findings[:200],
            }
        except Exception as e:
            return {"power_id": "PWR-176", "status": "error", "message": str(e)}

    def requirements_check(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-177: Compare requirements.txt vs installed packages."""
        try:
            req_file = os.path.join(repo_path, "requirements.txt")
            if not os.path.isfile(req_file):
                return {"power_id": "PWR-177", "status": "error", "message": "requirements.txt not found"}

            with open(req_file, "r", encoding="utf-8") as f:
                req_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

            # Get installed packages
            res = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            import json

            try:
                installed = {p["name"].lower(): p["version"] for p in json.loads(res.stdout)}
            except (json.JSONDecodeError, KeyError):
                installed = {}

            comparison: List[Dict[str, str]] = []
            for req in req_lines:
                # Parse name from requirement spec
                name = re.split(r"[><=!~\[]", req)[0].strip().lower()
                if name:
                    comparison.append(
                        {
                            "requirement": req,
                            "installed_version": installed.get(name, "NOT INSTALLED"),
                            "present": name in installed,
                        }
                    )

            missing = [c for c in comparison if not c["present"]]
            return {
                "power_id": "PWR-177",
                "status": "success",
                "total_requirements": len(comparison),
                "missing_count": len(missing),
                "comparison": comparison,
            }
        except Exception as e:
            return {"power_id": "PWR-177", "status": "error", "message": str(e)}

    def venv_info(self) -> Dict[str, Any]:
        """PWR-178: Virtual environment information."""
        try:
            import sys

            venv_path = os.environ.get("VIRTUAL_ENV", "")
            conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
            in_venv = (
                bool(venv_path)
                or hasattr(sys, "real_prefix")
                or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
            )

            return {
                "power_id": "PWR-178",
                "status": "success",
                "in_virtualenv": in_venv,
                "venv_path": venv_path or None,
                "conda_env": conda_env or None,
                "python_executable": sys.executable,
                "python_version": sys.version,
                "prefix": sys.prefix,
                "base_prefix": getattr(sys, "base_prefix", sys.prefix),
            }
        except Exception as e:
            return {"power_id": "PWR-178", "status": "error", "message": str(e)}


developer_powers = DeveloperPowers()
