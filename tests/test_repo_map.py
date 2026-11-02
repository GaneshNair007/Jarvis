"""
Unit tests for the Aider-style AST Repository Map generator (jarvis.core.repo_map).
"""

from pathlib import Path
from jarvis.core.repo_map import ASTRepoMapper, ast_repo_mapper


class TestASTRepoMapper:
    def test_parse_python_file_extracts_classes_and_functions(self, tmp_path):
        sample_code = '''"""Module docstring."""

class CognitiveAgent:
    """Agent class docstring."""
    def __init__(self, name: str):
        self.name = name

    async def execute_task(self, task_id: str, payload: dict) -> dict:
        return {"status": "done"}

def standalone_helper(x: int, y: int) -> int:
    """Helper function docstring."""
    return x + y
'''
        f = tmp_path / "test_module.py"
        f.write_text(sample_code, encoding="utf-8")

        mapper = ASTRepoMapper(root_dir=str(tmp_path))
        res = mapper.parse_python_file(f)

        assert res["path"] == "test_module.py"
        assert res["docstring"] == "Module docstring."
        assert len(res["classes"]) == 1
        cls = res["classes"][0]
        assert cls["name"] == "CognitiveAgent"
        assert len(cls["methods"]) == 2
        m_names = [m["name"] for m in cls["methods"]]
        assert "__init__" in m_names
        assert "execute_task" in m_names

        assert len(res["functions"]) == 1
        fn = res["functions"][0]
        assert fn["name"] == "standalone_helper"

    def test_generate_compact_markdown_map(self, tmp_path):
        f = tmp_path / "agent.py"
        f.write_text("class Agent:\n    def run(self): pass\n", encoding="utf-8")

        mapper = ASTRepoMapper(root_dir=str(tmp_path))
        md = mapper.generate_compact_markdown_map()
        assert "# Repository Structural AST Map" in md
        assert "class `Agent`" in md
        assert "run()" in md

    def test_global_singleton_instance_scans_jarvis(self):
        # Verify ast_repo_mapper can scan current jarvis directory
        map_md = ast_repo_mapper.generate_compact_markdown_map(max_files=10)
        assert len(map_md) > 100
        assert "class" in map_md

