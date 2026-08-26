@echo off
chcp 65001 >nul
title B站会员购转售与市集行情监控看板

cd /d "%~dp0"

echo =======================================================
echo    🛒 B站会员购转售与市集行情监控看板 - 一键启动
echo =======================================================
echo.

:: 检查 Python 环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境！请先安装 Python 3.8 或更高版本。
    echo 官方下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [*] 正在启动监控大盘与本地 API 服务...
echo [*] 服务地址: http://localhost:8000
echo [*] 浏览器将自动打开大盘页面，请稍候...
echo.
echo [提示] 保持此窗口开启即可持续提供监控服务与自动巡检。
echo [提示] 如需关闭服务，直接关闭本窗口或按 Ctrl + C。
echo -------------------------------------------------------
echo.

python web_server.py --port 8000 --open

if %errorlevel% neq 0 (
    echo.
    echo [提示] 服务已停止运行。
    pause
)
