@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

set "TS=C:\Program Files\Tailscale\tailscale.exe"
set "PY=C:\Users\DDD\AppData\Local\Programs\Python\Python312\python.exe"

if not exist "%TS%" (
    echo [错误] 未找到 Tailscale，请先运行:
    echo        winget install -e --id Tailscale.Tailscale
    pause
    exit /b 1
)

echo ============================================================
echo  Bili 看板 · Tailscale 外网接入
echo ============================================================
echo.

rem ---------- 1. 确保看板服务在跑 ----------
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [1/3] 看板未运行，正在启动 ...
    start "" /min cmd /c run_server.bat
    timeout /t 5 >nul
) else (
    echo [1/3] 看板已在运行
)

rem ---------- 2. 登录 Tailscale ----------
echo.
echo [2/3] 正在启动 Tailscale ...
echo       浏览器会弹出登录页，用微软/谷歌/GitHub 账号登录即可。
echo       若提示权限不足，请右键本脚本选"以管理员身份运行"。
echo.
"%TS%" up

echo.
echo       等待登录完成 ...
set "TSIP="
for /l %%i in (1,1,30) do (
    timeout /t 2 >nul
    for /f "delims=" %%a in ('"%TS%" ip -4 2^>nul') do set "TSIP=%%a"
    if defined TSIP goto :gotip
)
:gotip

if not defined TSIP (
    echo       [未完成] 没拿到 Tailscale IP，请确认浏览器里已登录成功，然后重跑本脚本。
    pause
    exit /b 1
)

rem ---------- 3. 取口令并输出地址 ----------
set "TOKEN="
if exist auth.conf (
    for /f "usebackq tokens=1,* delims==" %%a in ("auth.conf") do (
        if "%%a"=="DASHBOARD_TOKEN" set "TOKEN=%%b"
    )
)

echo.
echo [3/3] 完成
echo ============================================================
echo  Tailscale 地址 : %TSIP%
echo.
echo  本机访问       : http://localhost:8000
echo  手机/外网访问  : http://%TSIP%:8000
if defined TOKEN echo                  首次需带口令: http://%TSIP%:8000/?token=%TOKEN%
echo.
echo  手机要装 Tailscale App 并登录同一账号，才能访问上面的地址。
echo ============================================================
echo.
choice /c YN /n /m "现在用默认浏览器打开看板? (Y/N)"
if errorlevel 2 goto :eof
start "" "http://%TSIP%:8000"
pause
