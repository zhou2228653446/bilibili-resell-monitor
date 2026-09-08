# Android 移动端 (v1.4.0 120Hz 高刷流光版)

基于 Kivy 原生 UI 深度重构的安卓移动端，融合 B 站粉色潮流数码设计风格，复用 `bili_resell.py` 爬虫核心，纯 Python 实现。

## 🌟 v1.4.0 核心突破与特性

1. **🚀 90Hz / 120Hz 屏幕高刷新率全面适配**：
   - Kivy 绘图帧率全面放开至 120 FPS (`graphics.maxfps = 120`)；
   - 集成 Android 原生窗口 `preferredRefreshRate = 120.0` 及最佳 DisplayMode 调度，释放高刷屏潜能，彻底告别 60Hz 限制。
2. **⚡ 零内存抖动性能优化（Zero-Allocation Scrolling）**：
   - 全面重构底层 OpenGL Canvas 指令生命周期：圆角矩形与边框指令只在初始化创建一次，滑动中仅做坐标与宽高赋值，杜绝高频 `canvas.clear()` 造成的 GC 停顿与掉帧。
   - 阻尼自然轻盈的惯性滑动算法，长列表丝滑到底。
3. **✨ 丝滑过渡动效与微交互**：
   - 底部导航栏平滑滑动指示条：切换 Tab 时粉色指示条通过缓动曲线平移。
   - 页面切换淡入淡出动画，视觉柔和不生硬。
   - 详情弹窗轻柔缩放淡入展开，半透明遮罩平滑过渡。
4. **📦 实时抓取对齐电脑端（多品类 + 多排序 + 深度）**：
   - **品类选择**：`3C数码 (898)`、`模玩手办 (142)`、`拼装模型 (807)`、`动漫周边 (175)`、`全站商品 (all)`；
   - **排序规则**：`综合最热 (hot)`、`挂售最多 (mostListings)`、`价格最低 (priceFirst)`；
   - **翻页深度**：`快速 5页`、`常规 15页`、`深度 50页`、`全量融合 (最全防漏)`；
   - 沉浸式深色终端日志（Dark Glassmorphism），支持自动滚动到底部。
5. **🔍 实时检索与多维度筛选**：
   - 实时关键词/标题搜索框，输入即响应；
   - 筛选芯片：`全部`、`超值捡漏`（低于最近成交价）、`3折神价`（<= 30% 原价）、`已查成交`；
   - 智能排序：`默认排序`、`差价最大`、`价格升序`、`价格降序`、`折扣最大`。
6. **📋 交互式成交走势详情弹窗**：
   - 点击卡片即可弹出详情底单；
   - 实时异步拉取 B 站官方市集成交明细（买家昵称、成交价格、成交时间，如 `3天前 ¥77`）；
   - 官方成交走势均价节点图；
   - 商品官方规格与属性；
   - `直达B站市集` 一键调起手机浏览器或 B 站 App 查看商品。
7. **🌐 局域网电脑同步**：手机与电脑处于同一 Wi-Fi 时，可直接输入电脑 IP 极速同步大盘数据。

---

## 📲 构建方式 (GitHub Actions 云端打包)

APK 由 GitHub Actions 云端产出（无需在本机安装 Android SDK/NDK/Docker）：

1. 推送 tag `apk-v1.4.0` 触发自动构建：
   ```bash
   git tag apk-v1.4.0
   git push origin apk-v1.4.0
   ```
2. 或进入 GitHub 仓库 **Actions** 页 → 选择 **Build Android APK** workflow → 点击 **Run workflow** 手动触发。
3. 构建完成后在该次运行页面的 **Artifacts** 下载 `biliresellmonitor-apk` 安装包。

---

## 💻 本地调试（Windows 桌面快速预览 UI）

```bash
C:/Users/Administrator/.workbuddy/binaries/python/envs/kivy/Scripts/python.exe android_app/main.py
```

## 📁 文件结构

- `main.py` — Kivy 移动端主程序（UI 布局、120Hz 调度、持久化 Canvas 指令、交互弹窗、动效）
- `android_compat.py` — 安卓私有目录适配层（兼容桌面调试与手机端运行）
- `bili_resell.py` — 爬虫核心与市集成交明细解析引擎
- `buildozer.spec` — 打包配置（v1.4.0，arm64-v8a，minSdk 24，targetSdk 34）
- `NotoSansCJKsc-Regular.otf` — 思源黑体字体（确保安卓 CJK 中文完美渲染）
