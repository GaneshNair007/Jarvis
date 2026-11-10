"""
Background startup script verification.

Proves the always-on launchers exist, are well-formed (PowerShell scripts
parse with zero errors), reference the real entrypoints, and the installer
actually copies the launcher into a target Startup directory.
"""

import re
import pytest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


def test_all_startup_scripts_exist():
    for name in (
        "start_jarvis_background.vbs",
        "start_jarvis.bat",
        "stop_jarvis.bat",
        "stop_jarvis.ps1",
        "stop_all_jarvis.ps1",
        "install_jarvis_startup.ps1",
    ):
        assert (SCRIPTS / name).is_file(), f"missing script: {name}"


def test_vbs_launcher_starts_server_and_voice_daemon_hidden():
    vbs = (SCRIPTS / "start_jarvis_background.vbs").read_text(encoding="utf-8", errors="replace")
    # Hidden window style
    assert "WScript.Shell" in vbs
    assert re.search(r"shell\.Run\s+cmd,\s*0,\s*False", vbs), "launcher must run hidden (style 0)"
    # Real entrypoints
    assert "pythonw" in vbs
    assert "uvicorn jarvis.api.server:app" in vbs
    assert "jarvis.voice.daemon" in vbs
    assert "127.0.0.1" in vbs and "8000" in vbs
    # Logs land somewhere inspectable
    assert "logs" in vbs


def test_bat_launcher_references_real_entrypoints():
    bat = (SCRIPTS / "start_jarvis.bat").read_text(encoding="utf-8", errors="replace")
    assert "uvicorn jarvis.api.server:app" in bat
    assert "jarvis.voice.daemon" in bat
    assert "127.0.0.1" in bat


def test_stop_script_stops_voice_daemon_only():
    """Directive contract: stop_jarvis.ps1 stops the voice daemon, not the API/HUD."""
    ps1 = (SCRIPTS / "stop_jarvis.ps1").read_text(encoding="utf-8", errors="replace")
    assert "jarvis.ops.process_registry" in ps1
    assert "stop --role voice_daemon" in ps1
    assert "uvicorn" not in ps1.lower(), "voice-only stop must not target the API server"
    assert "--role hud_overlay" not in ps1
    assert "stop --all" not in ps1
    # Must never be a blanket python kill
    assert "Stop-Process -Name python" not in ps1
    assert "taskkill /IM python" not in ps1
    assert "Get-Process python" not in ps1


def test_stop_all_script_targets_every_jarvis_role():
    ps1 = (SCRIPTS / "stop_all_jarvis.ps1").read_text(encoding="utf-8", errors="replace")
    assert "jarvis.ops.process_registry stop --all" in ps1
    assert "all_required_running" in ps1
    assert "Stop-Process -Name python" not in ps1
    assert "taskkill /IM python" not in ps1


def test_powershell_scripts_parse_cleanly():
    import subprocess
    import shutil

    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        pytest.skip("PowerShell is not installed on this host")

    parser = r"""
$files = @(
  'scripts\stop_jarvis.ps1',
  'scripts\stop_all_jarvis.ps1',
  'scripts\install_jarvis_startup.ps1'
)
$failed = $false
foreach ($f in $files) {
  $tokens = $null; $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path $f), [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors -and $errors.Count -gt 0) {
    Write-Output ("PARSE_ERROR " + $f + ": " + $errors[0].Message)
    $failed = $true
  } else {
    Write-Output ("PARSE_OK " + $f)
  }
}
if ($failed) { exit 1 } else { exit 0 }
"""
    result = subprocess.run(
        [ps, "-NoProfile", "-Command", parser],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARSE_OK" in result.stdout
    assert "PARSE_ERROR" not in result.stdout


def test_installer_copies_launcher_into_startup_dir(tmp_path):
    """Runs the real installer against a temp Startup dir and verifies the copy."""
    import subprocess
    import shutil

    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        pytest.skip("PowerShell is not installed on this host")

    result = subprocess.run(
        [
            ps,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPTS / "install_jarvis_startup.ps1"),
            "-StartupDir",
            str(tmp_path),
            "-LauncherName",
            "JARVIS Background.vbs",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    installed = tmp_path / "JARVIS Background.vbs"
    assert installed.is_file(), "installer did not copy the launcher"
    original = (SCRIPTS / "start_jarvis_background.vbs").read_bytes()
    assert installed.read_bytes() == original, "installed copy differs from source"
    assert "Installed JARVIS background startup" in result.stdout


def test_voice_daemon_module_has_cli_entrypoint():
    """The VBS launches `pythonw -m jarvis.voice.daemon` — that module must run."""
    source = (REPO / "jarvis" / "voice" / "daemon.py").read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    assert "def main()" in source
