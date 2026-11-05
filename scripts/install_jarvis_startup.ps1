# Installs JARVIS always-on startup: copies the background launcher into the
# current user's Windows Startup folder so server + voice daemon launch at login.
param(
    [string]$StartupDir = [Environment]::GetFolderPath('Startup'),
    [string]$LauncherName = 'JARVIS Background.vbs'
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'start_jarvis_background.vbs'
if (-not (Test-Path -LiteralPath $source)) {
    throw "Launcher not found: $source"
}
if (-not (Test-Path -LiteralPath $StartupDir)) {
    New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null
}
$dest = Join-Path $StartupDir $LauncherName
Copy-Item -LiteralPath $source -Destination $dest -Force
Write-Host "Installed JARVIS background startup:"
Write-Host "  $dest"
Write-Host "It will launch at next sign-in (server + always-on voice daemon)."
Write-Host "To remove: Remove-Item `"$dest`""
