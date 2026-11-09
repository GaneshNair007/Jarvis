# Stops every JARVIS-owned background process started by
# start_jarvis_background.vbs: voice daemon, API server and HUD overlay.
#
# Uses the validated process registry (PID + creation time + command line).
# Never terminates unrelated python.exe/pythonw.exe processes. Safe to run
# repeatedly: a full stop with nothing running is an idempotent no-op.
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
    Write-Error "Python interpreter not found on PATH; cannot stop JARVIS."
    exit 2
}

Push-Location $repo
try {
    & $pythonExe @pythonPrefix -m jarvis.ops.process_registry stop --all
    $code = $LASTEXITCODE

    if ($code -eq 0) {
        # Independent verification: re-read live process identity after the
        # stop, rather than trusting the stop command's own report.
        $healthRaw = & $pythonExe @pythonPrefix -m jarvis.ops.process_registry --json health
        $health = ($healthRaw -join "`n") | ConvertFrom-Json
        if ($health.all_required_running) {
            Write-Host "Verification FAILED: a JARVIS process is still running."
            foreach ($role in $health.roles.PSObject.Properties) {
                if ($role.Value.running) {
                    Write-Host ("  still running: " + $role.Name + " pids " + ($role.Value.instances.pid -join ', '))
                }
            }
            $code = 1
        } else {
            Write-Host "Verified: API server, voice daemon and HUD overlay are all stopped."
        }
    }
} finally {
    Pop-Location
}

exit $code
