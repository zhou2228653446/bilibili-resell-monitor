# Android 移动端重构版 (android_app/)

基于 Kivy 原生 UI 深度重构的安卓移动端，融合 B 站粉色潮流数码设计风格，复用根目录 `bili_resell.py` 爬虫核心，纯 Python 实现。

## 🌟 核心功能与现代 UI 特性

- **🎨 现代沉浸式视觉体验**：B 站经典粉色主题、纯白圆角卡片、柔和阴影边框与清晰视觉层级，告别简陋灰白框。
- **🖼️ 商品缩略图完整呈现**：内置 `AsyncImage` 异步加载与缓存，支持商品真实图展示与缺省图回退。
- **🔍 实时检索与多维度筛选**：
  - 实时关键词/标题搜索框，输入即响应；
  - 筛选芯片：`全部`、`🔥 捡漏`（低于最近成交价）、`🏷️ 3折神价`（<= 30% 原价）、`已查成交`；
  - 智能排序：`默认排序`、`差价最大`、`售价最低`、`售价最高`、`折扣最大`。
- **📋 交互式成交走势详情弹窗**：
  - 点击卡片即可弹出详情底单；
  - 实时异步拉取 B 站官方市集成交明细（买家昵称、成交价格、成交时间，如 `6小时前 ¥118`）；
  - 官方成交走势均价节点图；
  - 商品官方规格与属性（IP、品牌、类别、参数）；
  - `🛒 直达B站市集` 一键调起手机浏览器或 B 站 App 查看商品。
- **🎯 捡漏雷达页面**：专用于汇总当前在售价明显低于市集最新成交价的超值好物。
- **⚡ 实时抓取与控制台**：
  - 本地监控大盘数据统计卡片（商品总量、均价、最低价）；
  - 支持设置抓取深度（快速 5 页 / 常规 15 页 / 全量 50 页）与排序模式；
  - 实时滚动终端日志输出窗口。
- **🌐 局域网电脑同步**：手机与运行 `web_server.py` 的电脑处于同一 Wi-Fi 时，可直接输入电脑 IP 极速同步大盘数据。

## 构建方式 (GitHub Actions 云端打包)

APK 由 GitHub Actions 云端产出（无需在本机安装 Android SDK/NDK/Docker）：

1. 代码 push 到 GitHub 后，进入仓库 **Actions** 页；
2. 选择 **Build Android APK** workflow → **Run workflow**（手动触发）；
3. 构建完成后在该次运行页面的 **Artifacts** 下载 `biliresellmonitor-apk`；
4. 传输到安卓手机安装运行。

或推 tag 触发自动构建：`git tag apk-v1.2.0 && git push origin apk-v1.2.0`

## 本地调试（Windows 桌面快速预览 UI）

```bash
# 使用隔离 venv 启动桌面端移动 UI 预览
C:/Users/Administrator/.workbuddy/binaries/python/envs/kivy/Scripts/python.exe android_app/main.py
```

## 文件结构

- `main.py` — Kivy 移动端主程序（UI 布局、交互弹窗、状态过滤、数据流）
- `android_compat.py` — 安卓私有目录适配层（兼容桌面调试与手机端运行）
- `bili_resell.py` — 爬虫核心与市集成交明细解析引擎
- `buildozer.spec` — 打包配置（arm64-v8a，minSdk 24，targetSdk 34）
- `NotoSansCJKsc-Regular.otf` — 思源黑体字体（确保安卓 CJK 中文完美渲染）
