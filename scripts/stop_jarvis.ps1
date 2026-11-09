# Stops JARVIS background processes started by start_jarvis_background.vbs
# Kills only processes whose command line references the JARVIS server, voice daemon or HUD overlay.
$ErrorActionPreference = 'SilentlyContinue'
$pattern = 'jarvis\.voice\.daemon|uvicorn jarvis\.api\.server|jarvis\.hud\.overlay'
$killed = @()
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern } | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        $killed += "$($_.ProcessId): $($_.Name)"
    } catch { }
}
if ($killed.Count -eq 0) {
    Write-Host "No JARVIS processes found running."
} else {
    Write-Host "Stopped:"
    $killed | ForEach-Object { Write-Host "  $_" }
}
