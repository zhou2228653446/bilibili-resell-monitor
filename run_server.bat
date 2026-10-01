@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  Bili resell monitor - resident service launcher
REM
REM  NOTE: this file is intentionally pure ASCII (no chcp call either).
REM  cmd.exe cannot reliably parse UTF-8 batch files: multi-byte characters
REM  that straddle its internal read boundary get split, and the tail fragment
REM  is then executed as a command ("... is not recognized"). Keeping to ASCII
REM  makes the startup banner and the archived logs deterministic.
REM
REM  Called by the scheduled task (boot, SYSTEM) and by the Startup folder
REM  (after logon). Auto restart: relaunches 5s after the service exits.
REM ============================================================

REM ---- Python interpreter: prefer the dedicated install ----
set "PY=C:\Users\DDD\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

REM ---- Access token: read from auth.conf (gitignored) ----
set "DASHBOARD_TOKEN="
if exist "%~dp0auth.conf" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0auth.conf") do (
        if /i "%%~A"=="DASHBOARD_TOKEN" set "DASHBOARD_TOKEN=%%~B"
    )
)
if not defined DASHBOARD_TOKEN (
    echo [WARN] DASHBOARD_TOKEN is empty in auth.conf.
    echo        The dashboard will be open to anyone who can reach port 8000.
)

REM ---- Log rotation: archive previous log, keep 7 ----
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\server.log"
if exist "%LOGFILE%" (
    set "STAMP=%DATE:/=-%_%TIME::=-%"
    set "STAMP=!STAMP: =0!"
    move "%LOGFILE%" "%LOGDIR%\server-!STAMP!.log" >nul 2>&1
)
for /f "skip=7 delims=" %%F in ('dir /b /o-d "%LOGDIR%\server-*.log" 2^>nul') do del /q "%LOGDIR%\%%F" 2>nul

echo [%DATE% %TIME%] Service starting
echo   Python  : %PY%
echo   Listen  : http://[::]:8000  (IPv4 / IPv6 dual stack)
echo   Log     : %LOGFILE%

:loop
REM Guard: both the scheduled task (boot, SYSTEM) and the Startup folder
REM (after logon) call this script. Whoever binds port 8000 first keeps it;
REM the other exits here instead of crashing in a restart loop.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [%DATE% %TIME%] Port 8000 already in use, another instance is running. Exiting.
    exit /b 0
)
"%PY%" web_server.py --port 8000 --host :: --no-open >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Service exited with code %errorlevel%, restarting in 5s...
timeout /t 5 /nobreak >nul 2>&1
goto loop
