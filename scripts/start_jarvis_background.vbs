' JARVIS Background Launcher (always-on, no windows)
' Starts the API server, the always-on voice daemon and the Iron Man HUD
' overlay (bottom-center arc reactor; pops on wake) hidden at Windows login.
' Install into Startup via: powershell -File scripts\install_jarvis_startup.ps1
Option Explicit

Dim shell, fso, repo, logDir, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' This file lives in <repo>\scripts\ -> repo is its parent folder.
repo = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
logDir = repo & "\logs"
If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)
shell.CurrentDirectory = repo

' 1) FastAPI server (relay + dashboard + REST) on 127.0.0.1:8000
cmd = "cmd /c cd /d """ & repo & """ && pythonw -m uvicorn jarvis.api.server:app --host 127.0.0.1 --port 8000 >> """ & logDir & "\server.log""" 2>&1"
shell.Run cmd, 0, False

' 2) Always-on "Hey Jarvis" voice daemon
cmd = "cmd /c cd /d """ & repo & """ && pythonw -m jarvis.voice.daemon >> """ & logDir & "\voice_daemon.log""" 2>&1"
shell.Run cmd, 0, False

' 3) Iron Man HUD overlay (polling process; shows on wake, quiet otherwise)
cmd = "cmd /c cd /d """ & repo & """ && pythonw -m jarvis.hud.overlay >> """ & logDir & "\hud_overlay.log""" 2>&1"
shell.Run cmd, 0, False

' 4) Record what we started for stop_jarvis.ps1 diagnostics
Dim ts
Set ts = fso.OpenTextFile(logDir & "\launcher.log", 8, True)
ts.WriteLine Now & " JARVIS background launcher started (server + voice daemon + HUD)"
ts.Close
