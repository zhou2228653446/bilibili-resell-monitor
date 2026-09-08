[app]
title = B站捡漏监控
package.name = biliresellmonitor
package.domain = org.biliresell
source.dir = .
# 中文字体必须随包分发（安卓无系统 CJK 字体回退，否则全部文字渲染为黑框叉）
source.include_exts = py,png,jpg,kv,atlas,otf,ttf,json,csv
# 复用根目录的爬虫核心模块
source.exclude_dirs = build,dist,__pycache__,web,tests
version = 1.5.1
requirements = python3,kivy==2.3.1,requests,urllib3,hostpython3,filetype
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,WAKE_LOCK,FOREGROUND_SERVICE
android.api = 34
android.minapi = 24
# p4a v2024.01.21 的 recommendations.py 限定 MIN/MAX_NDK_VERSION = 25，
# NDK 26b 会在 create 阶段被 check_ndk_version 拒绝
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
# CI 无 tty，许可证必须自动接受，否则 build-tools（含 aidl）静默安装失败
android.accept_sdk_license = True

# 钉住 python-for-android 版本：p4a master 默认编译 Python 3.14，
# 而 kivy 2.3.1 的 C 扩展不兼容 3.13/3.14（Py_UNICODE 等 C API 已删），
# v2024.01.21 是 Python 3.11.5 + Kivy 2.3.1 的官方支持组合。
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
