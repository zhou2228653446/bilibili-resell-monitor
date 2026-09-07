# Android 移植版 (android_app/)

Kivy 原生 UI 的安卓端，复用根目录 `bili_resell.py` 爬虫核心，直接函数调用（不内嵌 http.server）。

## 构建方式

本机（Windows，无 WSL/Docker）不执行构建，APK 由 GitHub Actions 云端产出：

1. 代码 push 到 GitHub 后，进入仓库 **Actions** 页；
2. 选择 **Build Android APK** workflow → **Run workflow**（手动触发）；
3. 构建约 15-40 分钟（首次更久，需下载 Android NDK）；
4. 完成后在该次运行页面的 **Artifacts** 下载 `biliresellmonitor-apk`；
5. 传输到手机安装（需允许"安装未知来源应用"）。

或推 tag 触发：`git tag apk-v1.0.0 && git push origin apk-v1.0.0`

## 本地调试（Windows 桌面预览 UI）

```bash
# 使用隔离 venv（已装 kivy 2.3.1）
C:/Users/Administrator/.workbuddy/binaries/python/envs/kivy/Scripts/python.exe android_app/main.py
```

桌面运行时数据路径与项目根目录一致，可直接复用 `3c_products.json` 现有数据。

## 与桌面版差异

| 项 | 桌面 Web 版 | 安卓版 |
|---|---|---|
| UI | 浏览器单页看板 | Kivy 原生四页（列表/雷达/抓取/设置） |
| 通知推送 | 邮件/企微/PushPlus | 暂不可用（安卓后台限制，后续可加 FCM） |
| 数据目录 | 项目根目录 | 应用私有目录（`android_compat.py` 适配） |
| 抓取方式 | 后台线程+定时调度 | 手动触发（省电省流量） |

## 文件说明

- `main.py` — Kivy 应用入口
- `android_compat.py` — 安卓数据目录适配（桌面端无感穿透）
- `buildozer.spec` — 打包配置（arm64-v8a，minSdk 24，targetSdk 34）
