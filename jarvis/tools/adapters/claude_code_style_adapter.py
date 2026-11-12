"""JARVIS Claude Code Style Adapter.

Exposes Claude Code engineering principles as system prompt directives
and AST-based static code validation checks.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


class ClaudeCodeStyleAdapter:
    """Adapter for ingesting and validating Claude Code engineering directives."""

    DEFAULT_SKILL_PATH = Path(
        r"C:\Users\Ganesh Nair\.gemini\config\skills\claude-code-style\SKILL.md"
    )

    def __init__(self, skill_path: Optional[Path] = None):
        self.skill_path = skill_path or self.DEFAULT_SKILL_PATH
        self._cached_prompt: Optional[str] = None

    def get_system_prompt_directive(self) -> str:
        """Returns the prompt directive to be injected into developer subagents."""
        if self._cached_prompt:
            return self._cached_prompt

        if self.skill_path.exists():
            try:
                content = self.skill_path.read_text(encoding="utf-8")
                # Strip YAML frontmatter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                self._cached_prompt = content
            except Exception:
                self._cached_prompt = self._default_directive()
        else:
            self._cached_prompt = self._default_directive()
        return self._cached_prompt

    @staticmethod
    def _default_directive() -> str:
        return (
            "CLAUDE CODE STYLE DIRECTIVES:\n"
            "1. Code Conciseness: Standard library over bloat, minimal code.\n"
            "2. Systematic Debugging: Root-cause identification before edits.\n"
            "3. Human Safety Gates: Require authorization for destructive actions."
        )

    def validate_code_conformance(self, code_str: str) -> Dict[str, Any]:
        """Performs static AST checks ensuring code conforms to simplicity directives."""
        violations: List[str] = []
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return {"valid": False, "violations": [f"SyntaxError: {str(e)}"]}

        # Check for prohibited wildcard imports
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        violations.append(
                            f"Line {node.lineno}: Prohibited wildcard import 'from {node.module} import *'."
                        )

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "ast_node_count": sum(1 for _ in ast.walk(tree)),
        }
