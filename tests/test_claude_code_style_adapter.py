"""Unit tests for ClaudeCodeStyleAdapter."""

from jarvis.tools.adapters.claude_code_style_adapter import ClaudeCodeStyleAdapter


def test_claude_code_style_directive_and_validation():
    adapter = ClaudeCodeStyleAdapter()
    directive = adapter.get_system_prompt_directive()
    assert isinstance(directive, str)
    assert len(directive) > 10

    # Test AST validation on clean code
    clean_code = "import os\nimport sys\nx = 1\n"
    res_clean = adapter.validate_code_conformance(clean_code)
    assert res_clean["valid"] is True
    assert len(res_clean["violations"]) == 0

    # Test AST validation on prohibited wildcard import
    dirty_code = "from os import *\nx = 1\n"
    res_dirty = adapter.validate_code_conformance(dirty_code)
    assert res_dirty["valid"] is False
    assert any("Prohibited wildcard import" in v for v in res_dirty["violations"])
