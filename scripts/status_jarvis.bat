@echo off
title JARVIS Background Services Status
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
python -m jarvis.core.process_manager
exit /b 0
