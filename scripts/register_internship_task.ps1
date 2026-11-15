[CmdletBinding()]
param(
    [string]$TaskName = "JARVIS-Internship-Discovery",
    [string]$RunAt = "08:15"
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run_internship_discovery.ps1"
if (-not (Test-Path $Runner)) { throw "Missing runner script: $Runner" }

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    '-NoProfile -ExecutionPolicy Bypass -File "' + $Runner + '"'
)
$Trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::ParseExact($RunAt, "HH:mm", $null))
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Runs JARVIS public ATS internship discovery. Never submits applications." -Force | Out-Null

Write-Host "Registered $TaskName to run daily at $RunAt local time."
Write-Host "Verify with: Get-ScheduledTask -TaskName '$TaskName'"
