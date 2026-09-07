[app]
title = B站捡漏监控
package.name = biliresellmonitor
package.domain = org.biliresell
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
# 复用根目录的爬虫核心模块
source.exclude_dirs = build,dist,__pycache__,web,tests
version = 1.0.0
requirements = python3,kivy==2.3.1,requests,urllib3,hostpython3
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 34
android.minapi = 24
android.ndk = 26b
android.archs = arm64-v8a
android.allow_backup = True
# CI 无 tty，许可证必须自动接受，否则 build-tools（含 aidl）静默安装失败
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
