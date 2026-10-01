@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

REM ============================================================
REM  数据冷备份 —— 把不可重建的价格轨迹打包到 E 盘
REM
REM  唯一真正需要备份的是 3c_products_history.csv：
REM  几十天积累的价格轨迹，丢了只能从零重新采集。
REM  其余文件能重新抓取，或在 GitHub 上有副本。
REM
REM  压缩后约 9MB/份，保留 14 份。备份目录可用环境变量
REM  BILI_BACKUP_DIR 覆盖。
REM ============================================================

set "PY=C:\Users\DDD\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0backup_data.py" %*
echo.
if "%~1"=="" pause
