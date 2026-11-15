[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$StartupWaitSeconds = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stdout = Join-Path $LogDir "internship-server-$Stamp.out.log"
$Stderr = Join-Path $LogDir "internship-server-$Stamp.err.log"
$ResultLog = Join-Path $LogDir "internship-discovery-$Stamp.json"

function Test-JarvisApi {
    try {
        Invoke-RestMethod -Method Get -Uri "$BaseUrl/scheduler/status" -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-JarvisApi)) {
    $Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $PythonCommand) { throw "Python was not found. Install dependencies and configure the JARVIS virtual environment." }
        $Python = $PythonCommand.Source
    }
    Start-Process -FilePath $Python -ArgumentList "-m jarvis.main serve" -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr | Out-Null

    $Deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
    while ((Get-Date) -lt $Deadline -and -not (Test-JarvisApi)) {
        Start-Sleep -Seconds 2
    }
}

if (-not (Test-JarvisApi)) {
    throw "JARVIS API did not become healthy. Inspect $Stderr and $Stdout."
}

$Response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/scheduler/trigger/internship_ats_discovery" -TimeoutSec 180
$Response | ConvertTo-Json -Depth 12 | Set-Content -Path $ResultLog -Encoding UTF8

if ($Response.status -ne "SUCCESS") {
    throw "Scheduler invocation failed. Inspect $ResultLog."
}
if ($Response.result.status -ne "COMPLETED") {
    throw "Discovery did not complete cleanly: $($Response.result.status). Inspect $ResultLog and config/internship_sources.yml."
}

Write-Host "Discovery completed. Result saved to $ResultLog"
Write-Host "No applications were submitted."
