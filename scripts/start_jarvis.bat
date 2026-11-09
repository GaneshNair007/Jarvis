@echo off
rem JARVIS foreground launcher (visible consoles for debugging)
rem For hidden always-on startup use start_jarvis_background.vbs instead.
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs

start "JARVIS-Server" cmd /k python -m uvicorn jarvis.api.server:app --host 127.0.0.1 --port 8000
start "JARVIS-Voice" cmd /k python -m jarvis.voice.daemon

echo JARVIS server  -> http://127.0.0.1:8000
echo JARVIS relay UI -> http://127.0.0.1:8000/relay
echo Close the two console windows to stop.
