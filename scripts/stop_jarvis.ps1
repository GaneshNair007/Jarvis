# Stops ONLY the JARVIS voice daemon.
# The API server and the HUD overlay keep running. Use stop_all_jarvis.ps1
# for a full shutdown of every JARVIS-owned background process.
#
# The Python process registry validates PID + creation time + command line
# before signalling anything, so an unrelated process that happens to reuse a
# stale PID is never killed.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

$pythonExe = $null
$pythonPrefix = @()
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pythonExe = $python.Source
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $pythonExe = $py.Source
        $pythonPrefix = @('-3')
    }
}
if (-not $pythonExe) {
    Write-Error "Python interpreter not found on PATH; cannot stop the JARVIS voice daemon."
    exit 2
}

Push-Location $repo
try {
    $raw = & $pythonExe @pythonPrefix -m jarvis.ops.process_registry --json stop --role voice_daemon
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

$report = $null
try { $report = ($raw -join "`n") | ConvertFrom-Json } catch { }

if ($code -eq 0) {
    if ($report -and $report.stopped.Count -eq 0) {
        Write-Host "Voice daemon was not running (idempotent no-op). API server and HUD overlay were left untouched."
    } else {
        Write-Host "Voice daemon stopped. API server and HUD overlay were left running."
    }
} else {
    Write-Host "Voice daemon stop did not complete cleanly (exit $code)."
}
exit $code
