@echo off
chcp 65001 >nul
title Bilibili Mall Resell Monitor

cd /d "%~dp0"

echo =======================================================
echo    Bilibili Mall Resell Monitor - Quick Start
echo =======================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found! Please install Python 3.8+.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [*] Starting Web Dashboard and Server...
echo [*] Local URL: http://localhost:8000
echo [*] Browser will open automatically...
echo.
echo [INFO] Keep this terminal open to keep the background scheduler running.
echo [INFO] To stop the server, press Ctrl + C or close this window.
echo -------------------------------------------------------
echo.

python web_server.py --port 8000 --open

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Server stopped.
    pause
)
