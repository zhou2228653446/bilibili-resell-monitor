# -*- coding: utf-8 -*-
"""将看板打包为单一独立 Windows EXE。

用法：
    python build_exe.py          # 或双击「打包成EXE.bat」

说明：
- 未安装 PyInstaller 时自动 pip 安装（Ubuntu 24.04+ 等 PEP 668 环境会失败，
  此时脚本给出 apt / venv 的替代命令）。
- 打包产物会额外复制一份到项目根目录：bilibili_resell_monitor.exe
"""
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
ENTRY_POINT = os.path.join(BASE_DIR, 'web_server.py')
EXE_NAME = 'bilibili_resell_monitor'


def ensure_pyinstaller():
    """确保 PyInstaller 可用；缺失时自动安装。"""
    try:
        import PyInstaller  # noqa: F401
        print('PyInstaller 已就绪')
        return True
    except ImportError:
        pass

    print('未检测到 PyInstaller，正在自动安装 ...')
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pyinstaller']
        )
        print('PyInstaller 安装完成')
        return True
    except subprocess.CalledProcessError:
        print('=' * 60)
        print('[错误] 自动安装 PyInstaller 失败。')
        print('       Ubuntu 24.04+ 等环境受 PEP 668 保护，禁止直接用 pip 装包，请改用：')
        print('         sudo apt install -y python3-pyinstaller')
        print('       或先建虚拟环境：')
        print('         python -m venv .venv && ./.venv/bin/pip install pyinstaller')
        print('=' * 60)
        return False


def build():
    print('=' * 60)
    print('Starting PyInstaller packaging...')
    print('=' * 60)

    if not ensure_pyinstaller():
        return 1

    cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--console',
        '--name', EXE_NAME,
        '--add-data', f'{WEB_DIR}{os.pathsep}web',
        '--hidden-import', 'requests',
        '--hidden-import', 'urllib.request',
        '--hidden-import', 'urllib.parse',
        '--hidden-import', 'email',
        '--hidden-import', 'email.mime.text',
        '--hidden-import', 'email.mime.multipart',
        '--hidden-import', 'email.header',
        '--hidden-import', 'smtplib',
        '--hidden-import', 'ssl',
        '--hidden-import', 'http.server',
        '--hidden-import', 'bili_resell',
        '--hidden-import', 'notifier',
        # 图片缓存模块由 web_server 顶层导入，显式声明防止静态分析漏收
        '--hidden-import', 'image_cache',
        # 批量拉取成交价时是函数内 import，显式声明更稳妥
        '--hidden-import', 'concurrent.futures',
        ENTRY_POINT,
    ]

    print('Running command:', ' '.join(cmd))
    try:
        subprocess.check_call(cmd, cwd=BASE_DIR)
    except subprocess.CalledProcessError:
        print('[错误] PyInstaller 构建失败，详见上方输出。')
        return 1

    dist_exe = os.path.join(BASE_DIR, 'dist', f'{EXE_NAME}.exe')
    target_exe = os.path.join(BASE_DIR, f'{EXE_NAME}.exe')

    if not os.path.exists(dist_exe):
        print('[错误] 未找到构建产物:', dist_exe)
        return 1

    shutil.copy2(dist_exe, target_exe)
    size_mb = os.path.getsize(target_exe) / (1024 * 1024)
    print('=' * 60)
    print(f'Successfully packaged! Executable generated at: {target_exe} ({size_mb:.2f} MB)')
    print('数据与配置保存在 exe 同级目录，可直接拷贝到任何未装 Python 的机器上运行。')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(build())
