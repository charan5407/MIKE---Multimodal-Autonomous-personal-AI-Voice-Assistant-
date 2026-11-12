' ==============================================================================
' MIKE Desktop Assistant - Silent Background Launcher
' Starts Python Core Server and Electron HUD Shell without a command prompt window
' ==============================================================================

Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' Get project directory where this script is located
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Cleanup existing processes on ports 5173 and 8765
strKillCmd = "powershell -NoProfile -WindowStyle Hidden -Command ""Get-NetTCPConnection -LocalPort 5173,8765 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"""
WshShell.Run strKillCmd, 0, True

' Start Python Core Server (hidden window mode)
strPythonExe = strScriptDir & "\.venv\Scripts\python.exe"
strServerScript = strScriptDir & "\run_server.py"
WshShell.CurrentDirectory = strScriptDir
WshShell.Run """" & strPythonExe & """ """ & strServerScript & """", 0, False

' Brief pause to allow FastAPI and WebSocket to initialize
WScript.Sleep 4000

' Start Electron Desktop Shell (native desktop app window)
strElectronExe = strScriptDir & "\desktop\node_modules\electron\dist\electron.exe"
WshShell.CurrentDirectory = strScriptDir & "\desktop"
WshShell.Run """" & strElectronExe & """ .", 1, False

