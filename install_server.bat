@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM ============================================================
REM  B站转售监控 —— 一键配置为「家里常驻服务器」
REM  必须右键本文件 → 以管理员身份运行
REM
REM  依次完成：
REM    1. 创建开机自启任务 BiliMonitor（SYSTEM 账户，无需登录桌面）
REM    2. 防火墙放行 8000 端口（IPv4 + IPv6）
REM    3. 禁用 IPv6 临时地址，让外网地址保持稳定
REM    4. 电源改为从不睡眠 / 不休眠
REM    5. 创建 DDNS 定时检测任务（每 30 分钟检查 IPv6 是否变化）
REM ============================================================

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 权限不足。请右键本文件，选择「以管理员身份运行」。
    echo.
    pause
    exit /b 1
)

echo [1/5] 创建开机自启任务 BiliMonitor ...
schtasks /create /tn "BiliMonitor" /tr "\"%~dp0run_server.bat\"" /sc onstart /ru SYSTEM /rl HIGHEST /f
if errorlevel 1 (echo   [失败] 任务创建失败，请检查命令输出) else (echo   OK)

echo.
echo [2/5] 创建 DDNS 定时检测任务（每 30 分钟）...
set "PY=C:\Users\DDD\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
schtasks /create /tn "BiliMonitorDDNS" /tr "\"%PY%\" \"%~dp0ddns_update.py\"" /sc minute /mo 30 /ru SYSTEM /rl HIGHEST /f
if errorlevel 1 (echo   [失败] 任务创建失败) else (echo   OK)

echo.
echo [3/5] 防火墙放行 8000 端口 ...
netsh advfirewall firewall delete rule name="Bili Monitor 8000" >nul 2>&1
netsh advfirewall firewall add rule name="Bili Monitor 8000" dir=in action=allow protocol=TCP localport=8000 profile=any
if errorlevel 1 (echo   [失败] 请手动放行) else (echo   OK)

echo.
echo [4/5] 禁用 IPv6 临时地址（让外网地址稳定）...
netsh interface ipv6 set privacy state=disabled
if errorlevel 1 (echo   [失败]) else (echo   OK)

echo.
echo [5/5] 电源改为常开 ...
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change monitor-timeout-dc 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-dc 0
echo   OK

echo.
echo ============================================================
echo  配置完成
echo ============================================================
echo  停止服务     : 双击 stop_server.bat
echo  查看任务状态 : schtasks /query /tn BiliMonitor /v
echo  查看日志     : logs\server.log
echo.

REM ---- 服务已在监听则跳过，避免启动第二个实例抢端口 ----
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo 正在启动服务 ...
    schtasks /run /tn BiliMonitor
    timeout /t 8 /nobreak >nul
) else (
    echo 服务已在运行，跳过启动。
)

REM ---- 读取访问口令 ----
set "TOKEN="
if exist "%~dp0auth.conf" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0auth.conf") do (
        if /i "%%~A"=="DASHBOARD_TOKEN" set "TOKEN=%%~B"
    )
)

REM ---- 取本机局域网 IPv4 与公网 IPv6 ----
set "LAN4="
for /f "delims=" %%I in ('"%PY%" -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('223.5.5.5',80));print(s.getsockname()[0])" 2^>nul') do set "LAN4=%%I"
set "WAN6="
for /f "delims=" %%I in ('"%PY%" "%~dp0ddns_update.py" --show 2^>nul') do set "WAN6=%%I"

echo.
echo ============================================================
echo  访问地址（复制完整地址到浏览器，口令已内嵌）
echo ============================================================
if defined LAN4 (
    echo   家里同 WiFi : http://%LAN4%:8000/?token=%TOKEN%
) else (
    echo   家里同 WiFi : http://localhost:8000/
)
echo   本机直接   : http://localhost:8000/
if defined WAN6 (
    echo   外网/手机流量: http://[%WAN6%]:8000/?token=%TOKEN%
    echo                  ^^^ 需先在路由器防火墙放行，且手机支持 IPv6
) else (
    echo   外网       : 未检测到公网 IPv6，只能在家访问
)
echo.
if defined LAN4 (
    choice /c YN /n /m "现在打开看板？[Y/N]"
    if errorlevel 2 goto :done
    start "" "http://%LAN4%:8000/?token=%TOKEN%"
)
:done
echo.
echo 提示：口令只需带一次，浏览器会记住一年。
pause
