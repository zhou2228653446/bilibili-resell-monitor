@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  B站转售监控 —— 服务常驻启动脚本
REM
REM  由任务计划程序调用（开机自启）。双击也能跑，但会占用控制台窗口。
REM  自带崩溃重启：服务进程退出后 5 秒自动拉起，7x24 无需人工干预。
REM ============================================================

REM ---- Python 解释器：优先用为服务单独安装的正式版 ----
set "PY=C:\Users\DDD\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

REM ---- 访问口令：从 auth.conf 读取（该文件已被 .gitignore 忽略）----
set "DASHBOARD_TOKEN="
if exist "%~dp0auth.conf" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0auth.conf") do (
        if /i "%%~A"=="DASHBOARD_TOKEN" set "DASHBOARD_TOKEN=%%~B"
    )
)
if not defined DASHBOARD_TOKEN (
    echo [警告] 未配置访问口令。auth.conf 里 DASHBOARD_TOKEN 为空，
    echo         服务将对任何能访问 8000 端口的人完全开放。
)

REM ---- 日志：启动时归档上一轮日志，仅保留最近 7 份 ----
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\server.log"
if exist "%LOGFILE%" (
    set "STAMP=%DATE:/=-%_%TIME::=-%"
    set "STAMP=!STAMP: =0!"
    move "%LOGFILE%" "%LOGDIR%\server-!STAMP!.log" >nul 2>&1
)
for /f "skip=7 delims=" %%F in ('dir /b /o-d "%LOGDIR%\server-*.log" 2^>nul') do del /q "%LOGDIR%\%%F" 2>nul

echo [%DATE% %TIME%] 启动服务
echo   Python  : %PY%
echo   监听    : http://[::]:8000 （IPv4 / IPv6 双栈）
echo   日志    : %LOGFILE%

REM ---- 常驻循环：--host :: 开启双栈，局域网与公网 IPv6 都能连 ----
:loop
"%PY%" web_server.py --port 8000 --host :: --no-open >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] 服务进程退出（退出码 %errorlevel%），5 秒后自动重启...
timeout /t 5 /nobreak >nul 2>&1
goto loop
