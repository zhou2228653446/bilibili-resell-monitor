# 🛒 Bilibili Mall Resell Monitor (B站会员购转售与市集行情监控看板)

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Dependency](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-success.svg)]()

> 基于 Python 标准库打造的 **B站会员购「潮玩转售/市集」实时数据监控系统与可视化大盘**。  
> 支持**全自动无人值守定时巡检**、**B站官方市集成交均价走势与订单拉取**、**降价捡漏雷达告警**、**在线抓取控制台**以及**无感数据实时刷新**。

---

## ✨ 核心特性

- ⚡ **零第三方依赖 (Zero Dependencies)**：后端完全基于 Python 3 标准库（`http.server`、`urllib`、`threading` 等）实现，克隆即可运行，无需 `pip install` 繁重依赖。
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
├── web/
│   └── index.html            # 前端单页可视化监控大盘 (Tailwind + Chart.js + Lucide)
├── 3c_products.json          # 最新商品数据快照
├── 3c_products.csv           # 最新商品 CSV 数据快照
├── 3c_products_history.csv   # 历史多时点价格轨迹库（用于降价告警分析）
├── deals_cache.json          # 市集成交数据本地持久化缓存
├── .gitignore
└── README.md
```

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

---

## ⚠️ 免责声明 (Disclaimer)

本项目仅用于 Python 网络编程、数据可视化及自动化技术的学习与技术交流。
抓取过程中全程采用公开的访客匿名接口，请合理控制抓取频率，自觉遵守相关网络规范。
