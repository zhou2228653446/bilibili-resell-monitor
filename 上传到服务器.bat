@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  B站转售监控 —— 上传到服务器并部署（密钥版）
REM
REM  前置条件：
REM    1. 本机已安装 OpenSSH 客户端（Windows 10/11 自带）
REM    2. 已配置 SSH 密钥免密
REM
REM  服务器信息不再硬编码（避免公网 IP 进仓库），按优先级获取：
REM    环境变量  >  deploy.conf  >  运行时交互输入
REM    deploy.conf 已被 .gitignore 忽略，不会提交。
REM
REM  用法：双击本文件即可
REM ============================================================

cd /d "%~dp0"

set "CONF=%~dp0deploy.conf"
set "REMOTE_DIR=/opt/bili-monitor"
set "KEY=%USERPROFILE%\.ssh\id_ed25519"
set "SSH_BASE=-o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20"

REM ---- 读取 deploy.conf（KEY=VALUE 格式，仅接受白名单键）----
if exist "%CONF%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%CONF%") do (
        if /i "%%~A"=="SERVER_IP"   set "SERVER_IP=%%~B"
        if /i "%%~A"=="SERVER_USER" set "SERVER_USER=%%~B"
        if /i "%%~A"=="REMOTE_DIR"  set "REMOTE_DIR=%%~B"
        if /i "%%~A"=="DEPLOY_KEY"  set "KEY=%%~B"
    )
    echo [*] 已读取配置: %CONF%
)

if not defined SERVER_IP   set /p SERVER_IP="请输入服务器公网 IP: "
if not defined SERVER_USER set "SERVER_USER=root"
if not defined SERVER_IP (
    echo [错误] 未提供服务器 IP，已取消。
    pause
    exit /b 1
)

REM ---- 首次运行时询问是否留存配置（下次免输入）----
if not exist "%CONF%" (
    set /p SAVE_CONF="是否保存服务器信息到 deploy.conf（下次免输入）? (y/N) "
    if /i "!SAVE_CONF!"=="y" (
        >  "%CONF%" echo SERVER_IP=!SERVER_IP!
        >> "%CONF%" echo SERVER_USER=!SERVER_USER!
        >> "%CONF%" echo REMOTE_DIR=!REMOTE_DIR!
        >> "%CONF%" echo DEPLOY_KEY=!KEY!
        echo   OK: 已写入 %CONF% ^(该文件已被 .gitignore 忽略^)
    )
)

echo ============================================
echo  B站转售监控 - 上传并部署
echo  目标: %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%
echo  密钥: %KEY%
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
    echo 可在 deploy.conf 中用 DEPLOY_KEY= 指定其它路径。
    echo.
    pause
    exit /b 1
)

echo [1/6] 测试连接 ...
ssh -i "%KEY%" %SSH_BASE% %SERVER_USER%@%SERVER_IP% "echo CONNECT_OK" >nul 2>&1
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

echo [2/6] 在服务器上创建目录 ...
ssh -i "%KEY%" %SSH_BASE% %SERVER_USER%@%SERVER_IP% "mkdir -p %REMOTE_DIR%/web %REMOTE_DIR%/cache/img"
if errorlevel 1 (
    echo [错误] 远程建目录失败。
    pause
    exit /b 1
)
echo   OK
echo.

echo [3/6] 上传程序文件 ...
scp -i "%KEY%" %SSH_BASE% bili_resell.py web_server.py image_cache.py notifier.py deploy.sh %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
if errorlevel 1 (
    echo [错误] 程序文件上传失败。
    pause
    exit /b 1
)
echo   OK
echo.

echo [4/6] 上传前端页面 ...
scp -i "%KEY%" %SSH_BASE% web\index.html %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/web/
if errorlevel 1 (
    echo [错误] 前端文件上传失败。
    pause
    exit /b 1
)
echo   OK
echo.

echo [5/6] 上传数据文件 ...
for %%F in (3c_products.json 3c_products.csv notify_config.json deals_cache.json pushed_alerts.json) do (
    if exist "%%F" (
        scp -i "%KEY%" %SSH_BASE% "%%F" %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
        if errorlevel 1 echo   [警告] %%F 上传失败
    )
)

REM 历史价格库是降价告警的比对基线，缺失会导致告警长期无结果。
REM 远端已存在时不覆盖（服务端往往积累得更全），仅首次部署时上传。
if exist 3c_products_history.csv (
    set "REMOTE_HAS_HISTORY="
    for /f "delims=" %%R in ('ssh -i "%KEY%" %SSH_BASE% %SERVER_USER%@%SERVER_IP% "if [ -f %REMOTE_DIR%/3c_products_history.csv ]; then echo EXISTS; else echo MISSING; fi" 2^>nul') do set "REMOTE_HAS_HISTORY=%%R"
    if "!REMOTE_HAS_HISTORY!"=="EXISTS" (
        echo   [跳过] 服务器已存在历史价格库，保留远端数据
    ) else (
        echo   服务器无历史价格库，正在上传（约 40MB，首次较慢）...
        scp -i "%KEY%" %SSH_BASE% 3c_products_history.csv %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
        if errorlevel 1 echo   [警告] 历史库上传失败（降价告警将缺少基线，不影响启动）
    )
) else (
    echo   [跳过] 本地未找到 3c_products_history.csv
)
echo   OK
echo.

echo [6/6] 重启服务 ...
ssh -i "%KEY%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=30 %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && systemctl restart bili-monitor && sleep 3 && systemctl is-active bili-monitor"
if errorlevel 1 (
    echo [警告] 重启命令未成功返回，请手动检查。
    echo   首次部署请先执行: ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% ^&^& bash deploy.sh"
    echo   查看状态: ssh %SERVER_USER%@%SERVER_IP% "systemctl status bili-monitor"
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
