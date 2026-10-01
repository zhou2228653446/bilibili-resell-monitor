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
echo  立即启动服务 : schtasks /run /tn BiliMonitor
echo  停止服务     : 双击 stop_server.bat
echo  查看任务状态 : schtasks /query /tn BiliMonitor /v
echo  查看日志     : logs\server.log
echo.
echo  外网访问地址 : 见 ddns.conf 配置的域名，或运行
echo                 python ddns_update.py --show 查看当前 IPv6
echo.
pause
