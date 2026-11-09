"""
Aider-Inspired Abstract Syntax Tree (AST) Repository Map Generator for Project JARVIS
Analyzes multi-file codebases using Python's native AST engine, extracting classes,
methods, function signatures, and docstrings to build a structural repository map
for long-horizon reasoning models without context blowup.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ASTRepoMapper:
    """
    Parses codebases into an Abstract Syntax Tree (AST) structural map.
    Identifies exported symbols, classes, functions, and inheritance hierarchies.
    """

    EXCLUDE_DIRS = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

    def parse_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Parses a single Python file into classes, functions, and docstrings."""
        rel_path = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
        result = {
            "path": rel_path,
            "classes": [],
            "functions": [],
            "docstring": None,
        }

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            result["error"] = str(e)
            return result

        result["docstring"] = ast.get_docstring(tree)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = [self._format_node(b) for b in node.bases]
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(
                            {
                                "name": item.name,
                                "args": self._format_args(item.args),
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "docstring": ast.get_docstring(item),
                            }
                        )
                result["classes"].append(
                    {
                        "name": node.name,
                        "bases": bases,
                        "methods": methods,
                        "docstring": ast.get_docstring(node),
                    }
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"].append(
                    {
                        "name": node.name,
                        "args": self._format_args(node.args),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "docstring": ast.get_docstring(node),
                    }
                )

        return result

    def scan_repository(self, max_files: int = 200) -> List[Dict[str, Any]]:
        """Scans all Python files in the repository."""
        file_maps = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
            for file in sorted(files):
                if file.endswith(".py"):
                    full_p = Path(root) / file
                    fm = self.parse_python_file(full_p)
                    if fm.get("classes") or fm.get("functions") or fm.get("docstring"):
                        file_maps.append(fm)
                    if len(file_maps) >= max_files:
                        break
            if len(file_maps) >= max_files:
                break
        return file_maps

    def generate_compact_markdown_map(self, max_files: int = 150) -> str:
        """Renders an Aider-style hierarchical AST repository map."""
        scanned = self.scan_repository(max_files=max_files)
        lines = ["# Repository Structural AST Map (Aider Engine Pattern)\n"]

        for fm in scanned:
            path = fm["path"]
            lines.append(f"### `{path}`")
            if fm.get("docstring"):
                first_line = fm["docstring"].strip().split("\n")[0]
                lines.append(f"> {first_line}")

            for cls in fm.get("classes", []):
                base_str = f"({', '.join(cls['bases'])})" if cls["bases"] else ""
                lines.append(f"- **class `{cls['name']}{base_str}`**:")
                for m in cls.get("methods", []):
                    prefix = "async " if m["is_async"] else ""
                    lines.append(f"  - `{prefix}{m['name']}({m['args']})`")

            for fn in fm.get("functions", []):
                prefix = "async " if fn["is_async"] else ""
                lines.append(f"- `def {prefix}{fn['name']}({fn['args']})`")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_args(args: ast.arguments) -> str:
        """Formats function argument signatures."""
        arg_names = []
        for a in args.args:
            if a.arg != "self" and a.arg != "cls":
                arg_names.append(a.arg)
        return ", ".join(arg_names)

    @staticmethod
    def _format_node(node: ast.AST) -> str:
        """Helper to format AST expression nodes."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{ASTRepoMapper._format_node(node.value)}.{node.attr}"
        return "..."


# Global Singleton Instance
ast_repo_mapper = ASTRepoMapper()
