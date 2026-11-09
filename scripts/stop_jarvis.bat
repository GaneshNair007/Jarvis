@echo off
rem Stops the JARVIS voice daemon only (API server + HUD stay running).
rem For a full shutdown use stop_all_jarvis.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_jarvis.ps1"
