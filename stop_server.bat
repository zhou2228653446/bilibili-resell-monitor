@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  停止常驻的监控服务
REM  注意：run_server.bat 自带崩溃重启循环，只杀 Python 进程会被重新拉起，
REM        所以这里先结束计划任务，再杀掉持有 8000 端口的进程。
REM ============================================================

echo [1/3] 结束计划任务 BiliMonitor ...
schtasks /end /tn "BiliMonitor" >nul 2>&1
if errorlevel 1 (echo   没有运行中的任务，或权限不足) else (echo   OK)

echo.
echo [2/3] 结束计划任务 BiliMonitorDDNS ...
schtasks /end /tn "BiliMonitorDDNS" >nul 2>&1
if errorlevel 1 (echo   没有运行中的任务，或权限不足) else (echo   OK)

echo.
echo [3/3] 结束占用 8000 端口的进程 ...
set "KILLED=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%P >nul 2>&1
    set "KILLED=1"
)
if "!KILLED!"=="1" (echo   OK) else (echo   未发现占用 8000 端口的进程)

echo.
echo 服务已停止。
echo 如需重新开机自启，请运行 install_server.bat。
echo.
pause
