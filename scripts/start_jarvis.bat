@echo off
title JARVIS Autonomous Operating System
cd /d "%~dp0\.."
set PYTHONPATH=%CD%

echo [JARVIS] Checking existing background services...
python -c "from jarvis.core.process_manager import process_manager; import sys; sys.exit(1 if process_manager.is_running('jarvis') or process_manager.is_running('audio_daemon') else 0)"
if errorlevel 1 (
    echo [JARVIS] Services are already running.
    call "%~dp0status_jarvis.bat"
    exit /b 0
)

echo [JARVIS] Launching Windows always-on audio daemon...
start /B "" python -m jarvis.voice.listener

echo [JARVIS] Launching JARVIS core orchestration and API server...
start /B "" python -c "import os; from jarvis.core.process_manager import process_manager; process_manager.acquire_pid('jarvis', os.getpid()); from jarvis.main import run_server; run_server()"

echo [JARVIS] Services launched headlessly.
exit /b 0
