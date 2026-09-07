@echo off
chcp 65001 >nul
title B站会员购转售监控 - 打包为 Windows EXE

echo ============================================================
echo   🚀 正在将 B站会员购转售监控 打包为单一独立 EXE 可执行文件...
echo ============================================================
echo.

python build_exe.py

echo.
pause
