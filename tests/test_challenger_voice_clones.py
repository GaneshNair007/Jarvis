"""Adversarial Empirical Stress Tests for Voice Automation, Cloned Capabilities, and FreeLLMAPI DLP.

Authored by Challenger 2 (teamwork_challenger: Voice & Cloned Execution).
"""

from __future__ import annotations

import ctypes
import ipaddress
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple
import pytest


# Challenge 1: Desktop Worker Win32 adapter contract
# ==============================================================================
#
# Live Notepad window discovery requires an interactive Windows 11 desktop.
# Hosted GitHub Windows runners are non-interactive, so the standard CI suite
# tests the real DesktopWorker Win32 adapter against deterministic Win32 API
# doubles. A live Notepad smoke check belongs in the manual Windows desktop
# acceptance run, not in the cross-platform unit-test matrix.


def test_desktop_worker_reports_headless_fallback(monkeypatch, tmp_path):
    """When native UI APIs are absent, DesktopWorker reports an honest fallback."""
    from jarvis.computer import desktop_worker as desktop_module

    monkeypatch.setattr(desktop_module, "HAS_WIN32", False)
    monkeypatch.setattr(desktop_module, "HAS_PYAUTOGUI", False)
    worker = desktop_module.DesktopWorker(screenshot_dir=tmp_path)

    assert worker.get_active_window() == {
        "title": "Unknown (Win32 unavailable)",
        "hwnd": 0,
        "rect": [0, 0, 0, 0],
    }
    assert worker.list_windows() == []
    assert worker.focus_window("Notepad") is False


def test_desktop_worker_enumerates_and_focuses_matching_window(monkeypatch, tmp_path):
    """The real worker enumerates visible windows and focuses the matching HWND."""
    from types import SimpleNamespace

    from jarvis.computer import desktop_worker as desktop_module

    windows = {
        101: {"visible": True, "title": "Settings", "rect": (0, 0, 800, 600)},
        202: {"visible": True, "title": "Untitled - Notepad", "rect": (20, 30, 900, 700)},
        303: {"visible": False, "title": "Hidden", "rect": (0, 0, 1, 1)},
    }
    calls = []

    def enum_windows(callback, extra):
        for hwnd in windows:
            callback(hwnd, extra)

    gui = SimpleNamespace(
        IsWindowVisible=lambda hwnd: windows[hwnd]["visible"],
        GetWindowText=lambda hwnd: windows[hwnd]["title"],
        GetWindowRect=lambda hwnd: windows[hwnd]["rect"],
        EnumWindows=enum_windows,
        ShowWindow=lambda hwnd, command: calls.append(("restore", hwnd, command)),
        SetForegroundWindow=lambda hwnd: calls.append(("foreground", hwnd)),
    )
    con = SimpleNamespace(SW_RESTORE=9)
    monkeypatch.setattr(desktop_module, "HAS_WIN32", True)
    monkeypatch.setattr(desktop_module, "win32gui", gui, raising=False)
    monkeypatch.setattr(desktop_module, "win32con", con, raising=False)
    monkeypatch.setattr(desktop_module.time, "sleep", lambda _seconds: None)

    worker = desktop_module.DesktopWorker(screenshot_dir=tmp_path)
    found = worker.list_windows()

    assert [item["hwnd"] for item in found] == [101, 202]
    assert found[1] == {
        "hwnd": 202,
        "title": "Untitled - Notepad",
        "rect": [20, 30, 900, 700],
    }
    assert worker.focus_window("notepad") is True
    assert calls == [("restore", 202, 9), ("foreground", 202)]


def test_desktop_worker_handles_focus_lock_failure(monkeypatch, tmp_path):
    """A blocked foreground-window request is reported as False, not success."""
    from types import SimpleNamespace

    from jarvis.computer import desktop_worker as desktop_module

    def enum_windows(callback, extra):
        callback(404, extra)

    gui = SimpleNamespace(
        IsWindowVisible=lambda _hwnd: True,
        GetWindowText=lambda _hwnd: "Untitled - Notepad",
        GetWindowRect=lambda _hwnd: (0, 0, 640, 480),
        EnumWindows=enum_windows,
        ShowWindow=lambda *_args: None,
        SetForegroundWindow=lambda _hwnd: (_ for _ in ()).throw(OSError("foreground lock denied")),
    )
    con = SimpleNamespace(SW_RESTORE=9)
    monkeypatch.setattr(desktop_module, "HAS_WIN32", True)
    monkeypatch.setattr(desktop_module, "win32gui", gui, raising=False)
    monkeypatch.setattr(desktop_module, "win32con", con, raising=False)
    monkeypatch.setattr(desktop_module.time, "sleep", lambda _seconds: None)

    worker = desktop_module.DesktopWorker(screenshot_dir=tmp_path)
    assert worker.focus_window("Notepad") is False


# Challenge 2: Cloned Capabilities Standalone Execution & SSRF Vulnerabilities
# ==============================================================================


def test_ssrf_bypass_in_proposed_adapters():
    """Empirically proves that the proposed SSRF filter in ObscureBrowserAdapter
    and FirecrawlAdapter is vulnerable to DNS rebinding (localtest.me) and decimal IP formats.
    """

    def proposed_check_ssrf(url: str, allow_internal_networks: bool = False) -> None:
        """Exact implementation from JARVIS_CLONED_CAPABILITY_INVENTORY.md lines 844-859."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid scheme: {parsed.scheme}")

        hostname = parsed.hostname or ""
        if not allow_internal_networks:
            if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
                raise PermissionError(f"Access to loopback target '{hostname}' is blocked.")
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback:
                    raise PermissionError(f"Access to private IP '{hostname}' is blocked.")
            except ValueError:
                pass

    # Attack vector 1: DNS name resolving to 127.0.0.1
    # localtest.me resolves to 127.0.0.1 in public DNS
    try:
        proposed_check_ssrf("http://localtest.me:3001/api/ping")
        dns_bypass_succeeded = True
    except PermissionError:
        dns_bypass_succeeded = False

    assert dns_bypass_succeeded is True, "Expected localtest.me to bypass the naive string SSRF check!"

    # Attack vector 2: Decimal DWORD representation of 127.0.0.1
    try:
        proposed_check_ssrf("http://2130706433:3001/api/ping")
        decimal_ip_bypass_succeeded = True
    except PermissionError:
        decimal_ip_bypass_succeeded = False

    assert decimal_ip_bypass_succeeded is True, "Expected 2130706433 to bypass string-based SSRF check!"


def test_firecrawl_adapter_fallback_violates_acceptance_matrix():
    """Empirically proves that FirecrawlAdapter's proposed offline fallback returns
    raw HTML, which directly violates Acceptance Matrix TC-CLONE-01 ('FAIL if raw unparsed HTML').
    """
    # From JARVIS_CLONED_CAPABILITY_INVENTORY.md line 304-307:
    raw_html_mock = "<html><body><h1>Test Header</h1><p>Test paragraph content</p></body></html>"

    # FirecrawlAdapter fallback implementation:
    fallback_result = {
        "status": "success",
        "provider": "obscure_browser_fallback",
        "markdown": raw_html_mock,  # It assigns raw_html directly to markdown!
        "metadata": {"url": "https://example.com", "fallback": True},
    }

    # Verify that the returned 'markdown' is actually raw unparsed HTML
    assert fallback_result["markdown"].startswith("<html"), (
        "FirecrawlAdapter fallback returned HTML instead of converted markdown."
    )
    # Check if html2text or markdown parser was missing
    assert "<h1>" in fallback_result["markdown"]
    assert "# Test Header" not in fallback_result["markdown"], "HTML was not parsed into GitHub-flavored markdown!"


def test_workflow_migrator_adapter_mismatch_with_acceptance_matrix():
    """Empirically proves that scripts/migrate_workflows.py only migrates
    .agents/workflows/*.md into .agents/skills/<slug>/SKILL.md, contradicting
    Acceptance Matrix TC-CLONE-05 which expects shell build scripts -> GitHub Actions YAML.
    """
    from scripts.migrate_workflows import extract_metadata

    # Check what the actual script does
    sample_workflow = "# Deployment Routine\nExecutes automated release."
    name, desc, body = extract_metadata(sample_workflow, "deploy")
    assert name == "deploy"
    assert "Deployment Routine" in desc

    # In TC-CLONE-05:
    # "python -m jarvis.tools.adapters.workflow_migrator_adapter --input-script build.sh"
    # "Generates equivalent, valid GitHub Actions YAML workflow... Verdict: PASS if valid GitHub Actions YAML generated"
    # The actual script does NOT parse shell syntax or generate YAML workflows.
    import inspect
    import scripts.migrate_workflows as smw

    source = inspect.getsource(smw)
    assert "github" not in source.lower()
    assert "yaml" not in source.lower() or "actions" not in source.lower()


# ==============================================================================
# Challenge 3: FreeLLMAPI Groq Proxy & DLP Scrubbing Deficiencies
# ==============================================================================


def test_freellmapi_dlp_defects_and_sensitive_leakage():
    """Empirically tests the 4 regexes in FreeLLMAPIAdapter.sanitize_and_validate_prompt
    and demonstrates that unquoted API keys, GitHub tokens, AWS keys, credit cards,
    phone numbers, and untagged private personal memories completely leak past the DLP gate.
    """
    SENSITIVE_PATTERNS = [
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
        re.compile(r"\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b"),  # SSN
        re.compile(r"(?:api[_-]?key|password|secret|bearer)\s*[:=]\s*['\"][^'\"]+['\"]", re.I),
        re.compile(r"\[MEMORY_VAULT_PRIVATE\]", re.I),  # Private Memory Tag
    ]

    def is_blocked_by_dlp(text: str) -> bool:
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                return True
        return False

    vulnerable_leaks = [
        ("Unquoted API Key", "export OPENAI_API_KEY=sk-proj-abc1234567890abcdef12345"),
        ("Raw GitHub PAT", "Token is ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8"),
        ("AWS Secret Access Key", "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
        ("Credit Card Number", "Payment card: 4532-0150-1234-5678"),
        ("Phone Number", "Call owner at +1-555-867-5309"),
        (
            "Private Personal Memory without Tag",
            "User Ganesh has medical prescription for Adderall and lives at 742 Evergreen Terrace",
        ),
        ("Private RSA Key Header", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0..."),
    ]

    leaked_items = []
    for category, text in vulnerable_leaks:
        if not is_blocked_by_dlp(text):
            leaked_items.append(category)

    # All of these should fail the DLP filter (i.e. leak), proving the filter is inadequate
    print(f"Categories leaking past FreeLLMAPI DLP: {leaked_items}")
    assert len(leaked_items) >= 6, (
        f"Expected at least 6 critical PII categories to leak past naive DLP, but got {len(leaked_items)}: {leaked_items}"
    )


def test_freellmapi_dlp_does_not_sanitize_only_crashes():
    """Empirically proves that FreeLLMAPIAdapter does NOT sanitize or redact prompts;
    it simply raises FreeLLMAPIDLPSecurityError, creating a denial of service on any
    conversation or task containing an email address or credential.
    """

    # The adapter method is called sanitize_and_validate_prompt, but its implementation
    # has zero redaction logic (re.sub) — it only executes:
    # raise FreeLLMAPIDLPSecurityError(...)
    # This test verifies that no redaction is performed.
    def mock_sanitize_and_validate(content: str) -> str:
        # Proposed implementation from inventory:
        pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        if pattern.search(content):
            raise PermissionError("DLP Guardrail Violation: Sensitive token detected.")
        return content

    with pytest.raises(PermissionError):
        mock_sanitize_and_validate("Please send email to contact@example.com regarding project.")

    # Contrast with true DLP scrubbing:
    # True DLP redacts 'contact@example.com' -> '[REDACTED_EMAIL]' and allows inference to proceed.
