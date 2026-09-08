# Android 移动端 (v1.5.0 清新高刷·智能通知版)

基于 Kivy 原生 UI 深度重构的安卓移动端，融合清新纯净现代极简设计（Neo-Nordic），复用 `bili_resell.py` 爬虫核心，纯 Python 实现。

## 🌟 v1.5.0 核心突破与特性

1. **🔔 系统状态栏通知与捡漏即时触达**：
   - 官方原生 `NotificationChannel` 支持（高优先级横幅、震动唤醒）；
   - 适配 Android 13+ (API 33+) 运行时 `POST_NOTIFICATIONS` 权限；
   - 当监控到低于成交价的捡漏好物或 3 折神价时，立即弹出系统通知，点击直接回到 App。
2. **⏰ 前后台定时自动巡检**：
   - 支持设置巡检频率：`15分钟`、`30分钟`、`1小时`、`2小时`；
   - 带有开关、倒计时状态显示与一键「测试通知」功能；
   - 应用退入后台时通过 `on_pause() -> True` 保持守护线程持续运作，不漏任何大捡漏。
3. **🚀 突破性图片性能优化（图片加载零卡顿）**：
   - 接入 B 站 CDN 官方缩略图处理网关 `@180w_180h_1c.png`；
   - 单张图片体积从 **983KB 暴降至 38KB (缩减 25.7 倍 / 96%)**；
   - 显存与 OpenGL 纹理解压开销降低 30 倍，结合单帧上传节流，彻底消灭滑动与图片加载掉帧。
4. **🎨 全新清新现代雅致设计（告别土味高饱和）**：
   - **瓷白微灰底色**（`#F8FAFC` Slate-50）：纯净高级，告别沉重压抑；
   - **通透瓷白顶栏**：摒弃厚重艳粉条，改为白底微边、深青黑标题与呼吸柔粉徽标；
   - **清新三色胶囊**：
     - `低于成交 ¥XX`：清新薄荷绿底（`#ECFDF5`）+ 翠绿字（`#059669`）；
     - `3折神价`：晨曦暖金底（`#FEF3C7`）+ 琥珀金字（`#D97706`）；
     - `成交价`：柔和淡灰底（`#F1F5F9`）+ 雅致灰字（`#475569`）；
   - **macOS 风格终端视窗**：红黄绿三色圆点搭配 `#0B0F17` 深色终端。
5. **⚡ 90Hz / 120Hz 高刷新率屏幕自适应**：
   - 解封 120 FPS 上限，原生调度 Android 最高刷新率 DisplayMode。
6. **✨ 丝滑平移动效与微交互**：
   - 底部导航栏平滑平移指示条（`Animation(indicator_x)`）；
   - 页面切换柔和淡入淡出。

---

## 📲 构建方式 (GitHub Actions 云端打包)

APK 由 GitHub Actions 云端产出（无需在本机安装 Android SDK/NDK/Docker）：

1. 推送 tag `apk-v1.5.0` 触发自动构建：
   ```bash
   git tag apk-v1.5.0
   git push origin apk-v1.5.0
   ```
2. 或进入 GitHub 仓库 **Actions** 页 → 选择 **Build Android APK** workflow → 点击 **Run workflow** 手动触发。
3. 构建完成后在该次运行页面的 **Artifacts** 下载 `biliresellmonitor-apk` 安装包。

---

## 💻 本地调试（Windows 桌面快速预览 UI）

```bash
C:/Users/Administrator/.workbuddy/binaries/python/envs/kivy/Scripts/python.exe android_app/main.py
```

## 📁 文件结构

- `main.py` — Kivy 移动端主程序（UI 布局、120Hz 调度、清新配色、交互弹窗、动效）
- `notification_helper.py` — Android 状态栏系统通知助手（NotificationChannel, PendingIntent）
- `scheduler.py` — 前后台定时自动巡检守护线程与漏品检测
- `android_compat.py` — 安卓私有目录适配层（兼容桌面调试与手机端运行）
- `bili_resell.py` — 爬虫核心与市集成交明细解析引擎
- `buildozer.spec` — 打包配置（v1.5.0，arm64-v8a，minSdk 24，targetSdk 34，通知与保活权限）
- `NotoSansCJKsc-Regular.otf` — 思源黑体字体（确保安卓 CJK 中文完美渲染）
