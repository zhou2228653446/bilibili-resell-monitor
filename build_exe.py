# -*- coding: utf-8 -*-
import os, sys, subprocess, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
ENTRY_POINT = os.path.join(BASE_DIR, 'web_server.py')
EXE_NAME = 'bilibili_resell_monitor'

def build():
    print('=' * 60)
    print('Starting PyInstaller packaging...')
    print('=' * 60)

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
        ENTRY_POINT,
    ]

    print('Running command:', ' '.join(cmd))
    subprocess.check_call(cmd, cwd=BASE_DIR)

    dist_exe = os.path.join(BASE_DIR, 'dist', f'{EXE_NAME}.exe')
    target_exe = os.path.join(BASE_DIR, f'{EXE_NAME}.exe')

    if os.path.exists(dist_exe):
        shutil.copy2(dist_exe, target_exe)
        size_mb = os.path.getsize(target_exe) / (1024 * 1024)
        print('=' * 60)
        print(f'Successfully packaged! Executable generated at: {target_exe} ({size_mb:.2f} MB)')
        print('=' * 60)

if __name__ == '__main__':
    build()
