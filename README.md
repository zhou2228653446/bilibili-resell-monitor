# 🛒 Bilibili Mall Resell Monitor (B站会员购转售与市集行情监控看板)

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Config](https://img.shields.io/badge/Dependencies-Standard%20Library%20Core%20%2B%20Optional%20requests-yellow.svg)]()

> 基于 Python 标准库打造的 **B站会员购「潮玩转售/市集」实时数据监控系统与可视化大盘**。  
> 支持**全自动无人值守定时巡检**、**B站官方市集成交均价走势与订单拉取**、**降价捡漏雷达告警**、**在线抓取控制台**以及**无感数据实时刷新**。

---

## ✨ 核心特性

- 🧩 **核心零依赖，requests 可选加速**：Web 服务端完全基于 Python 3 标准库（`http.server`、`urllib`、`threading` 等）实现；爬虫核心在未安装 `requests` 时自动回退 `urllib`（克隆即可运行），安装 `requests` 后自动启用 `Session` 持久化连接，抗 429 更稳定。
- 🖼️ **商品图片本地归档（抗 CDN 换图 / 省流量）**：
  - 抓取完成后自动把新商品图片归档到本地磁盘，已缓存的自动跳过，**不产生任何重复流量**；
  - 归档时自动追加 B站 CDN 缩略图后缀，单张从约 450KB 压缩到约 **12KB（节省 97%）**；
  - 长连接池复用 TCP+TLS，实测吞吐可达 **3.8 张/秒**，688 个商品全量归档仅需 3 分钟、8.4MB；
  - 内容寻址命名（URL 即 key），图片 URL 不变则永久命中；支持 LRU 容量上限自动淘汰。
- 🛡️ **智能防封与抗 429 退避算法 (Anti-Rate-Limiting)**：
  - 自动获取公开游客设备指纹（`buvid3`/`buvid4`），实现无账号物理隔离抓取，0 封号风险；
  - 遇到 B 站 `HTTP 429` 频率限制时，自适应进入指数抖动退避，自动恢复抓取，保证数据 100% 完整不漏抓。
- 📊 **B站市集真实交易与成交走势拉取**：
  - 穿透 B 站会员购官方底层接口，实时拉取商品的历史成交均价变动折线图（含成交量）；
  - 获取近期买家成交订单明细（成交价、成交时间、脱敏买家信息）；
  - 在卡片价格正右侧醒目展示**「最近一次市集成交价」**，直观比对在售价与历史成交价。
- ⏰ **全自动定时巡检与大盘无感自动刷新 (Auto Scheduler & Live Sync)**：
  - 支持设置 **15 分钟 / 30 分钟 / 1 小时 / 2 小时** 周期性自动巡检；
  - 巡检完成后，前端大盘**自动无感实时刷新**，并弹出捡漏 Toast 提醒与提示音。
- 📱 **企业微信机器人捡漏实时推送 (WeCom Notifications)**：
  - 电脑不在身边时，巡检发现新降价捡漏商品可自动推送至手机企业微信群聊；
  - 支持富文本 Markdown 卡片排版（商品名称、底价、降价幅度、直达抢购链接）；
  - 内置**增量去重防骚扰机制**，避免重复轰炸。
- 🎯 **降价捡漏雷达 (Price Drop Radar)**：
  - 自动对比前多次抓取的高位价格，高亮置顶降价幅度超 10% 或 10 元的优质捡漏商品（最高降幅可达 70%+）。
- 🎨 **现代化单页响应式看板 (Modern Web UI)**：
  - 内置暗黑模式 (Dark Mode) / 明亮模式无缝切换；
  - 支持网格卡片流 (Grid) 与紧凑表格视图 (Table) 双视图切换；
  - 多维度实时搜索、排序（降幅优先、价格从低到高、从高到低、折扣优先）与价格区间过滤；
  - 包含一键导出带 BOM 的 UTF-8 CSV 表格。

---

## 🚀 快速上手

### 1. 克隆仓库
```bash
git clone https://github.com/zhou2228653446/bilibili-resell-monitor.git
cd bilibili-resell-monitor
```

### 2. 启动 Web 可视化监控看板
```bash
python web_server.py --open
```
> 参数说明：
> - `--port 8000`：指定 Web 服务监听端口（默认 `8000`）；
> - `--open`：启动后自动在默认浏览器中打开看板（`http://localhost:8000`）。

### 3. 一键封装为独立 Windows EXE（免 Python 环境）
项目支持直接打包为单一便携式 `.exe` 可执行程序，用户在**任何未安装 Python 的 Windows 电脑上双击即可直接运行**：
```bash
# 执行打包脚本（自动安装 PyInstaller 并生成单一 EXE）
python build_exe.py
```
> 构建完成后，根目录下会生成 `bilibili_resell_monitor.exe`。
> 双击该文件即可全自动启动后端服务、定时调度器并弹窗打开浏览器！数据与配置自动保存在 exe 同级目录下，随时便携迁移。

### 3. 命令行独立运行爬虫（可选）
```bash
# 全量抓取 3C数码 分类并导出 JSON 和 CSV
python bili_resell.py --category 898 --all --csv 3c_products.csv --json 3c_products.json

# 抓取手办分类前 5 页
python bili_resell.py --category 142 --pages 5

# 查询指定商品在 B站市集的真实成交记录与走势
python -c "from bili_resell import get_cluster_info; import pprint; pprint.pprint(get_cluster_info('10000000603'))"
```

---

## 📂 项目结构

```text
bilibili-resell-monitor/
├── bili_resell.py            # 核心爬虫引擎（请求封装、429退避、市集成交接口）
├── web_server.py             # REST API 服务器 + 定时调度器 + 静态文件托管
├── image_cache.py            # 商品图片本地缓存（缩略图牵引 + 长连接池 + LRU淘汰）
├── notifier.py               # 微信/邮件/企微等渠道推送
├── web/
│   └── index.html            # 前端单页可视化监控大盘 (Tailwind + Chart.js + Lucide)
├── cache/img/                # 商品图片本地缓存（运行时生成，已 gitignore）
├── 3c_products.json          # 最新商品数据快照
├── 3c_products.csv           # 最新商品 CSV 数据快照
├── 3c_products_history.csv   # 历史多时点价格轨迹库（用于降价告警分析）
├── deals_cache.json          # 市集成交数据本地持久化缓存
├── .gitignore
└── README.md
```

---

## 🖼️ 商品图片本地归档

看板原本直接引用 B站 CDN 图片，存在两个问题：**B站换图/删图后历史商品裂图**，以及
**弱网环境下 CDN 加载缓慢**。图片归档模块把商品图存到本地磁盘，彻底解决这两点。

**工作方式**

1. 抓取完成后自动触发归档（可用 `IMG_AUTO_PREFETCH=0` 关闭），仅下载未缓存的新商品图；
2. 归档时自动追加 CDN 缩略图后缀 `@480w_480h_1c.webp`，大幅压缩体积；
3. 前端 `<img>` 统一走 `/api/img?url=xxx`，服务端本地缓存优先，未命中才回源并落盘；
4. 响应带 `Cache-Control: max-age=604800, immutable`，浏览器二次访问不再请求服务器。

**实测数据**（688 个商品全量归档）

| 指标 | 数值 |
| :--- | :--- |
| 单张图片体积 | 449KB → **12.49KB**（节省 97.2%） |
| 全量 688 张 | **8.39 MB / 3.0 分钟**（3.85 张/秒） |
| 失败数 | 0 |
| 缓存命中响应 | **1~2 ms** |

**环境变量**

| 变量 | 默认 | 说明 |
| :--- | :--- | :--- |
| `IMG_CACHE_DIR` | `./cache/img` | 缓存目录 |
| `IMG_CACHE_MAX_MB` | `512` | 缓存容量上限（MB），超出按 LRU 淘汰 |
| `IMG_AUTO_PREFETCH` | `1` | 抓取后是否自动归档 |
| `IMG_FETCH_INTERVAL` | `0.15` | 下载限速间隔（秒/张） |

**相关接口**

| 接口 | 方法 | 说明 |
| :--- | :---: | :--- |
| `/api/img?url=xxx` | `GET` | 商品图服务（本地缓存优先，未命中回源并落盘） |
| `/api/imgcache/stat` | `GET` | 查询缓存占用、命中统计与配置 |
| `/api/imgcache/prefetch` | `POST` | 手动触发全量归档（后台线程） |
| `/api/imgcache/clear` | `POST` | 清空本地图片缓存 |

> ⚠️ **注意**：部分网络环境下到 B站 CDN 的 **TCP 建连可能极慢**（实测曾达 37~49 秒），
> 而连接建立后单张图传输仅需 0.1~0.3 秒。模块内置的长连接池正是为此设计——
> 复用连接后吞吐提升约 250 倍。若归档异常缓慢，优先排查到 `i0.hdslb.com` 的网络质量。

---

## 🌐 REST API 文档

| 接口 | 方法 | 说明 |
| :--- | :---: | :--- |
| `/api/data` | `GET` | 获取大盘最新商品列表、KPI 统计、异动走势及捡漏告警 |
| `/api/product/history?id=xxx` | `GET` | 查询指定商品的本地抓取历史价格变动时间轴 |
| `/api/product/deals?id=xxx` | `GET` | 实时从 B 站官方接口获取商品市集成交记录与成交均价走势 |
| `/api/batch_deals` | `POST` | 批量异步拉取商品最新成交价（带缓存） |
| `/api/crawl` | `POST` | 触发后台爬虫抓取任务（支持参数：category, sort, pages） |
| `/api/crawl/status` | `GET` | 获取后台爬虫实时运行状态与流式终端日志 |
| `/api/schedule` | `GET / POST` | 查询与设置后台自动定时巡检调度配置 |
| `/api/notify/config` | `GET / POST` | 查询与保存推送渠道配置 |
| `/api/img?url=xxx` | `GET` | 商品图服务（本地缓存优先，未命中回源并落盘） |
| `/api/imgcache/stat` | `GET` | 查询图片缓存占用与命中统计 |
| `/api/imgcache/prefetch` | `POST` | 手动触发全量图片归档（后台线程） |
| `/api/imgcache/clear` | `POST` | 清空本地图片缓存 |

---

## 🐧 Linux 服务器部署（systemd）

项目为纯标准库实现，可直接部署到 Linux 服务器常驻运行（无桌面依赖）。

**1. 安装 Python 并准备目录**

```bash
sudo apt update && sudo apt install -y python3
sudo mkdir -p /opt/bili-monitor && cd /opt/bili-monitor
# 上传或 git clone 项目文件到本目录
```

**2. 可选：安装 requests 提升抓取稳定性**

```bash
pip3 install requests
```

**3. 创建 systemd 服务**

```bash
sudo tee /etc/systemd/system/bili-monitor.service > /dev/null <<'EOF'
[Unit]
Description=Bilibili Resell Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bili-monitor
# --no-open 必需：服务器无桌面环境，禁止尝试拉起浏览器
ExecStart=/usr/bin/python3 /opt/bili-monitor/web_server.py --port 8000 --no-open
Restart=always
RestartSec=10
StandardOutput=append:/var/log/bili-monitor.log
StandardError=append:/var/log/bili-monitor.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now bili-monitor
sudo systemctl status bili-monitor
```

**4. 放通端口**

在轻量应用服务器控制台的「防火墙」中放通 `8000/TCP`（或改用 Nginx 反代后只放通 80/443）。

> ⚠️ **安全提醒**：本服务**没有任何鉴权**，任何能访问该端口的人都可以触发抓取、
> 修改推送配置、查看你的数据。**请勿将 8000 端口直接暴露到公网**。
> 建议二选一：① 只放通给固定 IP；② 用 Nginx 反代并加 Basic Auth。

**5. Nginx 反代 + Basic Auth（推荐）**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;   # 抓取任务较慢，需放宽超时
    }
}
```

```bash
sudo apt install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd youruser
sudo systemctl restart nginx
```

**6. 流量预算参考**

| 项目 | 流量成本 |
| :--- | :--- |
| 图片首次全量归档（688 商品） | **约 8.4 MB**（一次性） |
| 图片增量归档（每日新商品） | 通常 < 5 MB/天 |
| 浏览器二次访问图片 | **0**（浏览器本地缓存 7 天） |
| 抓取商品列表 | 每次数 MB（取决于翻页深度） |

综上，4Mbps 带宽 + 入门套餐的月流量包**完全够用**。

> ⚠️ **务必在防火墙层面只放通必要端口**，并注意该服务默认监听 `0.0.0.0`。
> 若希望仅本机访问，启动时加 `--host 127.0.0.1` 配合 Nginx 反代。

---

## ⚠️ 免责声明 (Disclaimer)

本项目仅用于 Python 网络编程、数据可视化及自动化技术的学习与技术交流。
抓取过程中全程采用公开的访客匿名接口，请合理控制抓取频率，自觉遵守相关网络规范。
