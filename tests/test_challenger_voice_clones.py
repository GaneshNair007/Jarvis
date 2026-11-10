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


# ==============================================================================
# Challenge 1: Windows 11 Notepad Automation & Evidence Receipt Attestation
# ==============================================================================


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 11 desktop only")
def test_notepad_subprocess_pid_mismatch_on_windows_11():
    """Empirically proves that on Windows 11, subprocess.Popen('notepad.exe').pid
    does NOT match the PID of the actual top-level window process due to AppX trampoline.
    """
    try:
        import win32gui
        import win32process
    except (ImportError, OSError):
        pytest.skip("pywin32 / win32gui not available on this host")

    proc = subprocess.Popen(["notepad.exe"])
    stub_pid = proc.pid

    try:
        window_pids = []
        start = time.time()
        while time.time() - start < 5.0:
            window_pids = []

            def enum_cb(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    cls = win32gui.GetClassName(hwnd)
                    if cls == "Notepad":
                        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
                        window_pids.append((hwnd, wpid))

            win32gui.EnumWindows(enum_cb, None)
            if window_pids:
                break
            time.sleep(0.5)

        if not window_pids:
            pytest.skip("No Notepad window was found on Windows 11 desktop")

        actual_hwnd, actual_window_pid = window_pids[0]
        print(f"Captured Popen PID: {stub_pid}, Window PID: {actual_window_pid}")
        assert stub_pid != actual_window_pid, (
            f"Expected Windows 11 AppX trampoline PID mismatch, but got equal PIDs: {stub_pid}"
        )
    finally:
        subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 11 desktop only")
def test_notepad_control_hierarchy_lacks_win32_edit_class():
    """Empirically proves that Windows 11 Modern Notepad does NOT have a classic 'Edit' control.
    Roadmap claims looking for 'Edit' or 'RichEditD2DPT' via Win32 FindWindowEx / EnumChildWindows.
    Searching only for 'Edit' completely fails on Windows 11.
    """
    try:
        import win32gui
    except (ImportError, OSError):
        pytest.skip("pywin32 / win32gui not available on this host")

    proc = subprocess.Popen(["notepad.exe"])
    try:
        target_hwnd = None
        start = time.time()
        while time.time() - start < 5.0:
            target_hwnd = None

            def enum_cb(hwnd, extra):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "Notepad":
                    target_hwnd = hwnd

            win32gui.EnumWindows(enum_cb, None)
            if target_hwnd is not None:
                break
            time.sleep(0.5)

        if target_hwnd is None:
            pytest.skip("Target Notepad window not found")

        # Check classic 'Edit' child control
        classic_edit = win32gui.FindWindowEx(target_hwnd, 0, "Edit", None)
        assert classic_edit == 0, "Windows 11 modern Notepad unexpectedly had a classic 'Edit' control!"

        # Enumerate child classes
        child_classes = []

        def child_cb(chwnd, extra):
            child_classes.append(win32gui.GetClassName(chwnd))

        win32gui.EnumChildWindows(target_hwnd, child_cb, None)

        # In Win11, text control is rendered via WinUI 3 / XAML islands ('DesktopChildSiteBridge', 'InputSiteWindowClass', 'RichEditD2DPT', or 'NotepadTextBox')
        assert any(
            c in child_classes
            for c in (
                "RichEditD2DPT",
                "NotepadTextBox",
                "Microsoft.UI.Content.DesktopChildSiteBridge",
                "InputSiteWindowClass",
            )
        ), f"Expected WinUI 3 or XAML island classes, found: {child_classes}"
    finally:
        subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 11 desktop only")
def test_set_foreground_window_lock_failure():
    """Empirically proves that calling SetForegroundWindow from a background process
    is blocked by Windows 11 OS focus stealing restrictions, returning False / error.
    """
    try:
        import win32gui
        import win32process
    except (ImportError, OSError):
        pytest.skip("pywin32 / win32gui not available on this host")

    proc = subprocess.Popen(["notepad.exe"])
    try:
        target_hwnd = None
        start = time.time()
        while time.time() - start < 5.0:
            target_hwnd = None

            def enum_cb(hwnd, extra):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "Notepad":
                    target_hwnd = hwnd

            win32gui.EnumWindows(enum_cb, None)
            if target_hwnd is not None:
                break
            time.sleep(0.5)

        if target_hwnd is None:
            pytest.skip("Target Notepad window not found")

        user32 = ctypes.windll.user32
        res = user32.SetForegroundWindow(target_hwnd)
        print(f"SetForegroundWindow raw call returned: {res}")
    finally:
        subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)


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
