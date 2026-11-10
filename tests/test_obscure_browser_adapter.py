"""Unit tests for ObscureBrowserAdapter."""

import pytest
from jarvis.tools.adapters.obscure_browser_adapter import ObscureBrowserAdapter


def test_obscure_browser_ssrf_blocking():
    adapter = ObscureBrowserAdapter()
    with pytest.raises(PermissionError):
        adapter.fetch("http://127.0.0.1:3001/api/ping")

    with pytest.raises(PermissionError):
        adapter.fetch("http://localhost:8000/health")

    with pytest.raises(PermissionError):
        adapter.fetch("http://192.168.1.1/admin")


def test_obscure_browser_windows_ssl_fetch():
    adapter = ObscureBrowserAdapter(timeout=5.0)
    try:
        content = adapter.fetch("https://example.com")
        assert "<title>Example Domain</title>" in content
        assert len(content) > 100
    except RuntimeError as e:
        # If external network is unreachable in sandbox/CI, ensure error was from network, not SSL crash
        assert "Network connection failed" in str(e) or "HTTP fetch error" in str(e)
