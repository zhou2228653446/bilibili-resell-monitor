@echo off
chcp 936 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  B站转售监控 —— 上传到服务器并部署（密钥版）
REM
REM  前置条件：
REM    1. 本机已安装 OpenSSH 客户端（Windows 10/11 自带）
REM    2. 已配置 SSH 密钥免密（本脚本已内置密钥路径）
REM
REM  用法：双击本文件即可
REM ============================================================

set "SERVER_IP=115.159.210.120"
set "SERVER_USER=root"
set "REMOTE_DIR=/opt/bili-monitor"
set "KEY=%USERPROFILE%\.ssh\id_ed25519"

set "SSH_OPTS=-i ""%KEY%"" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20"

echo ============================================
echo  B站转售监控 - 上传并部署
echo  目标: %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%
echo ============================================
echo.

REM ---- 检查 scp ----
where scp >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 scp 命令。
    echo 请在「设置 - 应用 - 可选功能」中安装 OpenSSH 客户端。
    echo.
    pause
    exit /b 1
)

REM ---- 检查密钥 ----
if not exist "%KEY%" (
    echo [错误] 未找到 SSH 密钥：%KEY%
    echo.
    pause
    exit /b 1
)

echo [1/5] 测试连接 ...
ssh -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 %SERVER_USER%@%SERVER_IP% "echo CONNECT_OK" >nul 2>&1
if errorlevel 1 (
    echo [错误] SSH 连接失败。
    echo   1. 确认服务器在运行
    echo   2. 确认密钥已装入服务器（~/.ssh/authorized_keys）
    echo.
    pause
    exit /b 1
)
echo   OK: 密钥登录正常
echo.

echo [2/5] 在服务器上创建目录 ...
ssh -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 %SERVER_USER%@%SERVER_IP% "mkdir -p %REMOTE_DIR%/web %REMOTE_DIR%/cache/img"
if errorlevel 1 (
    echo [错误] 远程建目录失败。
    pause
    exit /b 1
)
echo   OK
echo.

echo [3/5] 上传程序文件 ...
scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 bili_resell.py web_server.py image_cache.py notifier.py deploy.sh %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if errorlevel 1 (
    echo [错误] 程序文件上传失败。
    pause
    exit /b 1
)
echo   OK
echo.

echo [4/5] 上传前端与数据文件 ...
scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 web\index.html %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/web/
if errorlevel 1 (
    echo [错误] 前端文件上传失败。
    pause
    exit /b 1
)

if exist 3c_products.json    scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes 3c_products.json    %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if exist 3c_products.csv     scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes 3c_products.csv     %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if exist notify_config.json  scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes notify_config.json  %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if exist deals_cache.json    scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes deals_cache.json    %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if exist pushed_alerts.json  scp -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes pushed_alerts.json  %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
echo   OK
echo.

echo [5/5] 重启服务 ...
ssh -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=30 %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && systemctl restart bili-monitor && sleep 3 && systemctl is-active bili-monitor"
if errorlevel 1 (
    echo [警告] 重启命令未成功返回，请手动检查。
    echo   查看状态: ssh root@%SERVER_IP% "systemctl status bili-monitor"
    pause
    exit /b 1
)
echo.

echo ============================================
echo  部署完成
echo  访问: http://%SERVER_IP%:8000
echo ============================================
echo.
pause
exit /b 0
