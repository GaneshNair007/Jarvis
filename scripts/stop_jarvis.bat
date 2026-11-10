@echo off
title Stop JARVIS Background Services
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo [JARVIS] Stopping all background services...
python -m jarvis.core.process_manager stop
echo [JARVIS] Services stopped cleanly.
exit /b 0
