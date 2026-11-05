@echo off
rem Stops JARVIS background processes (server + voice daemon).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_jarvis.ps1"
