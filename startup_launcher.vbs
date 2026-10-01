' Bili resell monitor - silently start the dashboard after logon
'
' Deploy: copy this file into the Windows Startup folder
'   (Win+R -> shell:startup)
'   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
'
' No admin rights needed. If install_server.bat has also created the system
' level scheduled task, that task starts the service at boot (before logon);
' this script then finds port 8000 already taken and exits quietly, because
' run_server.bat has a port guard. No duplicate instances.
'
' If the project moves, edit proj below and re-copy this file to Startup.
'
' ASCII only on purpose - VBScript files are decoded with the system ANSI
' code page, so non-ASCII comments can garble.

Option Explicit

Dim sh, proj
proj = "D:\repos\bili"

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = proj
sh.Run "cmd /c """ & proj & "\run_server.bat""", 0, False
