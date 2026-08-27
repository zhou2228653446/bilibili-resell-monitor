#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站会员购转售数据看板 Web 服务器
基于 Python 标准库实现，提供 REST API、数据分析与静态页面服务。

运行方式:
  python web_server.py          # 启动服务并在 http://localhost:8000 运行
  python web_server.py --port 8080 --open
"""

import argparse
import csv
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# 确保在 Windows 控制台支持 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
JSON_PATH = os.path.join(BASE_DIR, "3c_products.json")
CSV_PATH = os.path.join(BASE_DIR, "3c_products.csv")
HISTORY_PATH = os.path.join(BASE_DIR, "3c_products_history.csv")
DEALS_CACHE_PATH = os.path.join(BASE_DIR, "deals_cache.json")
SCRIPT_PATH = os.path.join(BASE_DIR, "bili_resell.py")

# 引入 bili_resell 模块的市集详情与成交拉取函数
try:
    from bili_resell import get_cluster_info
except Exception:
    get_cluster_info = None

# 引入通讯软件推送模块
try:
    import notifier
except Exception:
    notifier = None

# 市集成交数据持久化缓存管理
deals_cache_lock = threading.Lock()
deals_cache = {}

def load_deals_cache():
    global deals_cache
    if os.path.exists(DEALS_CACHE_PATH):
        try:
            with open(DEALS_CACHE_PATH, "r", encoding="utf-8") as f:
                deals_cache = json.load(f)
        except Exception:
            deals_cache = {}

def save_deals_cache():
    try:
        with open(DEALS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(deals_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warn] 保存成交缓存失败: {e}", file=sys.stderr)

load_deals_cache()

# 全局抓取任务状态管理
crawl_lock = threading.Lock()
crawl_state = {
    "running": False,
    "start_time": None,
    "log_lines": [],
    "exit_code": None,
    "process": None,
}

# 自动定时巡检调度状态管理
schedule_lock = threading.Lock()
schedule_state = {
    "enabled": False,
    "interval_minutes": 30,
    "category": "898",
    "sort": "hot",
    "last_run": None,
    "next_run": None,
    "_next_run_ts": 0,
}


def scheduler_worker():
    """后台定时巡检调度线程，定期自动触发抓取。"""
    while True:
        time.sleep(3)
        with schedule_lock:
            if not schedule_state["enabled"]:
                continue
            now = time.time()
            next_ts = schedule_state["_next_run_ts"]
            if now < next_ts:
                continue

            interval_sec = max(1, schedule_state["interval_minutes"]) * 60
            schedule_state["_next_run_ts"] = now + interval_sec
            schedule_state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            schedule_state["next_run"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + interval_sec))
            cat = schedule_state["category"]
            sort = schedule_state["sort"]

        with crawl_lock:
            is_running = crawl_state["running"]

        if not is_running:
            print(f"[Scheduler] 自动巡检任务触发: 分类={cat}, 排序={sort}")
            t = threading.Thread(
                target=run_crawl_thread,
                kwargs={"category": cat, "sort": sort, "pages": None},
                daemon=True,
            )
            t.start()


def parse_price(s):
    """从价格字符串中提取数值。"""
    if not s:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    nums = re.findall(r"\d+\.?\d*", str(s).replace(",", ""))
    if not nums:
        return None
    try:
        return float(nums[0])
    except ValueError:
        return None


def get_latest_data():
    """读取并汇总最新的商品数据、统计指标、走势及降价告警。"""
    products = []
    meta = {
        "total": 0,
        "fetched_at": "",
        "category": "898",
        "sort": "hot"
    }

    # 1. 尝试读取 JSON 快照
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                products = data.get("products", [])
                meta.update(data.get("meta", {}))
        except Exception as e:
            print(f"[Warn] 读取 JSON 失败: {e}", file=sys.stderr)

    # 2. 若无 JSON，回退读取 CSV
    if not products and os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                products = list(csv.DictReader(f))
                meta["total"] = len(products)
                meta["fetched_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(CSV_PATH)))
        except Exception as e:
            print(f"[Warn] 读取 CSV 失败: {e}", file=sys.stderr)

    # 3. 读取历史长表并计算走势与告警
    history_rows = []
    history_times = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8-sig") as f:
                history_rows = list(csv.DictReader(f))
            history_times = sorted({r["crawl_time"] for r in history_rows if "crawl_time" in r})
        except Exception as e:
            print(f"[Warn] 读取历史表失败: {e}", file=sys.stderr)

    # 价格解析与统计计算
    prices = []
    for p in products:
        p_val = parse_price(p.get("price"))
        p["price_num"] = p_val
        p["ref_price_num"] = parse_price(p.get("reference_price"))
        if p_val is not None:
            prices.append(p_val)

    stats = {
        "total_count": len(products),
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "history_points_count": len(history_times),
        "last_crawl_time": history_times[-1] if history_times else meta.get("fetched_at", ""),
    }

    # 4. 计算走势与异动（对比最近两次）
    trend = {"up": 0, "down": 0, "same": 0, "new": 0, "gone": 0}
    product_delta_map = {}
    if len(history_times) >= 2:
        cur_t, prev_t = history_times[-1], history_times[-2]
        cur_map = {r["cluster_id"]: r for r in history_rows if r.get("crawl_time") == cur_t}
        prev_map = {r["cluster_id"]: r for r in history_rows if r.get("crawl_time") == prev_t}

        for iid, r in cur_map.items():
            cp = parse_price(r.get("price"))
            if iid in prev_map:
                pp = parse_price(prev_map[iid].get("price"))
                if cp is not None and pp is not None:
                    delta = round(cp - pp, 2)
                    product_delta_map[iid] = delta
                    if delta > 0:
                        trend["up"] += 1
                    elif delta < 0:
                        trend["down"] += 1
                    else:
                        trend["same"] += 1
            else:
                trend["new"] += 1
                product_delta_map[iid] = "new"

        for iid in prev_map:
            if iid not in cur_map:
                trend["gone"] += 1

    # 为每个商品附加 delta 信息
    for p in products:
        iid = p.get("cluster_id")
        p["delta"] = product_delta_map.get(iid, 0)

    # 5. 计算价格异动（降价捡漏告警：对比前 3 次高位价）
    alerts = []
    if len(history_times) >= 2:
        idx = len(history_times) - 1
        prev_window = history_times[max(0, idx - 3):idx]
        cur_map = {r["cluster_id"]: r for r in history_rows if r.get("crawl_time") == history_times[idx]}

        prev_rows = {}
        for r in history_rows:
            if r.get("crawl_time") in prev_window:
                prev_rows[(r["crawl_time"], r["cluster_id"])] = r

        for iid, r in cur_map.items():
            cur_p = parse_price(r.get("price"))
            if cur_p is None:
                continue

            high_p = None
            for t in prev_window:
                pr = prev_rows.get((t, iid))
                if pr:
                    pp = parse_price(pr.get("price"))
                    if pp is not None and (high_p is None or pp > high_p):
                        high_p = pp

            if high_p is not None and high_p > cur_p:
                drop_abs = round(high_p - cur_p, 2)
                drop_pct = round(drop_abs / high_p, 4)
                if drop_abs >= 10.0 or drop_pct >= 0.10:
                    matching_prod = next((p for p in products if p.get("cluster_id") == iid), None)
                    alerts.append({
                        "cluster_id": iid,
                        "title": r.get("title", ""),
                        "cur_price": cur_p,
                        "high_price": high_p,
                        "drop_abs": drop_abs,
                        "drop_pct": round(drop_pct * 100, 1),
                        "img": matching_prod.get("img", "") if matching_prod else r.get("img", ""),
                        "url": r.get("url", ""),
                        "discount": matching_prod.get("discount", "") if matching_prod else r.get("discount", ""),
                    })

    # 6. 从持久化缓存中注入已知的市集最新成交价
    with deals_cache_lock:
        for p in products:
            iid = p.get("cluster_id")
            if iid in deals_cache and deals_cache[iid].get("latest_deal_price"):
                p["latest_deal_price"] = deals_cache[iid].get("latest_deal_price")
        for a in alerts:
            iid = a.get("cluster_id")
            if iid in deals_cache and deals_cache[iid].get("latest_deal_price"):
                a["latest_deal_price"] = deals_cache[iid].get("latest_deal_price")

    return {
        "meta": meta,
        "stats": stats,
        "trend": trend,
        "alerts": alerts,
        "products": products,
    }


def get_product_history(cluster_id):
    """根据 cluster_id 提取单个商品的所有历史抓取价格点。"""
    if not os.path.exists(HISTORY_PATH):
        return {"cluster_id": cluster_id, "title": "", "points": []}

    points = []
    title = ""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("cluster_id") == cluster_id:
                    title = r.get("title", title)
                    p_num = parse_price(r.get("price"))
                    points.append({
                        "crawl_time": r.get("crawl_time", ""),
                        "price": r.get("price", ""),
                        "price_num": p_num,
                        "reference_price": r.get("reference_price", ""),
                    })
    except Exception as e:
        print(f"[Warn] 获取商品历史失败: {e}", file=sys.stderr)

    points.sort(key=lambda x: x["crawl_time"])
    return {
        "cluster_id": cluster_id,
        "title": title,
        "points": points,
    }


def run_crawl_thread(category="898", sort="hot", pages=None):
    """在独立后台线程中执行爬虫并记录实时输出。"""
    global crawl_state
    cmd = [sys.executable, SCRIPT_PATH, "--csv", "3c_products.csv", "--json", "3c_products.json"]
    if category and category != "all":
        cmd.extend(["--category", category])
    elif category == "all":
        cmd.extend(["--category", "all"])

    if sort:
        cmd.extend(["--sort", sort])
    if pages:
        cmd.extend(["--pages", str(pages)])

    with crawl_lock:
        crawl_state["running"] = True
        crawl_state["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        crawl_state["log_lines"] = [f"[System] 启动抓取任务: {' '.join(cmd)}"]
        crawl_state["exit_code"] = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        with crawl_lock:
            crawl_state["process"] = proc

        for line in iter(proc.stdout.readline, ""):
            line_str = line.rstrip()
            if line_str:
                with crawl_lock:
                    crawl_state["log_lines"].append(line_str)
                    if len(crawl_state["log_lines"]) > 500:
                        crawl_state["log_lines"].pop(0)

        proc.stdout.close()
        return_code = proc.wait()
        with crawl_lock:
            crawl_state["exit_code"] = return_code
            crawl_state["log_lines"].append(f"[System] 抓取完成，退出码: {return_code}")

        # 抓取成功后自动触发企业微信捡漏消息推送
        if return_code == 0 and notifier:
            try:
                latest_data = get_latest_data()
                alerts = latest_data.get("alerts", [])
                total = len(latest_data.get("products", []))
                notifier.process_and_send_alerts(alerts, total_items_count=total)
            except Exception as notify_err:
                print(f"[Warn] 自动推送捡漏消息异常: {notify_err}", file=sys.stderr)
    except Exception as e:
        with crawl_lock:
            crawl_state["exit_code"] = -1
            crawl_state["log_lines"].append(f"[System Error] 抓取异常: {e}")
    finally:
        with crawl_lock:
            crawl_state["running"] = False
            crawl_state["process"] = None


class DashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """自定义 HTTP 请求处理器，支持 REST API 与静态资源。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            self.handle_api_data()
        elif path == "/api/product/history":
            qs = urllib.parse.parse_qs(parsed.query)
            cluster_id = qs.get("id", [""])[0]
            self.handle_api_product_history(cluster_id)
        elif path == "/api/product/deals":
            qs = urllib.parse.parse_qs(parsed.query)
            cluster_id = qs.get("id", [""])[0]
            self.handle_api_product_deals(cluster_id)
        elif path == "/api/crawl/status":
            self.handle_api_crawl_status()
        elif path == "/api/schedule":
            self.handle_api_get_schedule()
        elif path == "/api/notify/config":
            self.handle_api_get_notify_config()
        elif path == "/api/img":
            qs = urllib.parse.parse_qs(parsed.query)
            img_url = qs.get("url", [""])[0]
            self.handle_api_img_proxy(img_url)
        elif path in ("/", "/index.html"):
            index_file = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(index_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(index_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "index.html not found")
        else:
            # 正常托管 web 目录下的静态文件
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/crawl":
            self.handle_api_crawl()
        elif path == "/api/schedule":
            self.handle_api_set_schedule()
        elif path == "/api/batch_deals":
            self.handle_api_batch_deals()
        elif path == "/api/notify/config":
            self.handle_api_set_notify_config()
        elif path == "/api/notify/test":
            self.handle_api_notify_test()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_get_schedule(self):
        with schedule_lock:
            data = {
                "enabled": schedule_state["enabled"],
                "interval_minutes": schedule_state["interval_minutes"],
                "category": schedule_state["category"],
                "sort": schedule_state["sort"],
                "last_run": schedule_state["last_run"],
                "next_run": schedule_state["next_run"],
            }
        self.send_json(200, data)

    def handle_api_set_schedule(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            params = json.loads(body)
        except Exception:
            params = {}

        with schedule_lock:
            if "enabled" in params:
                schedule_state["enabled"] = bool(params["enabled"])
            if "interval_minutes" in params:
                schedule_state["interval_minutes"] = max(1, int(params["interval_minutes"]))
            if "category" in params:
                schedule_state["category"] = str(params["category"])
            if "sort" in params:
                schedule_state["sort"] = str(params["sort"])

            # 重置下次运行时间
            if schedule_state["enabled"]:
                now = time.time()
                interval_sec = schedule_state["interval_minutes"] * 60
                schedule_state["_next_run_ts"] = now + interval_sec
                schedule_state["next_run"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + interval_sec))
            else:
                schedule_state["next_run"] = None

            res_data = {
                "enabled": schedule_state["enabled"],
                "interval_minutes": schedule_state["interval_minutes"],
                "next_run": schedule_state["next_run"],
            }

        self.send_json(200, res_data)

    def handle_api_data(self):
        try:
            data = get_latest_data()
            self.send_json(200, data)
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def handle_api_product_history(self, cluster_id):
        if not cluster_id:
            self.send_json(400, {"error": "Missing id parameter"})
            return
        try:
            data = get_product_history(cluster_id)
            self.send_json(200, data)
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def handle_api_product_deals(self, cluster_id):
        """调用 B站 官方接口获取单个商品的真实成交明细、官方走势点与市集属性。"""
        if not cluster_id:
            self.send_json(400, {"error": "Missing id parameter"})
            return
        if not get_cluster_info:
            self.send_json(500, {"error": "get_cluster_info 模块未就绪"})
            return
        try:
            info = get_cluster_info(cluster_id)
            if info:
                # 存入成交持久化缓存
                with deals_cache_lock:
                    deals_cache[str(cluster_id)] = {
                        "latest_deal_price": info.get("latest_deal_price"),
                        "title": info.get("title"),
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_deals_cache()
                self.send_json(200, info)
            else:
                self.send_json(404, {"error": "未获取到该商品的市集成交信息"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def handle_api_batch_deals(self):
        """批量获取指定商品的最新成交价（优先读缓存，缺失的异步小并发拉取）。"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            params = json.loads(body)
            ids = params.get("ids", [])
        except Exception:
            ids = []

        result = {}
        missing_ids = []
        with deals_cache_lock:
            for cid in ids:
                cid_str = str(cid)
                if cid_str in deals_cache and deals_cache[cid_str].get("latest_deal_price"):
                    result[cid_str] = deals_cache[cid_str].get("latest_deal_price")
                else:
                    missing_ids.append(cid_str)

        if missing_ids and get_cluster_info:
            import concurrent.futures
            def fetch_deal(cid_str):
                try:
                    info = get_cluster_info(cid_str)
                    if info and info.get("latest_deal_price"):
                        return cid_str, info.get("latest_deal_price"), info.get("title")
                except Exception:
                    pass
                return cid_str, None, None

            # 控制小并发（最多 4 个线程，最多拉取当前页前 16 个）
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(fetch_deal, cid) for cid in missing_ids[:16]]
                for f in concurrent.futures.as_completed(futures):
                    cid_str, ldp, title = f.result()
                    if ldp:
                        result[cid_str] = ldp
                        with deals_cache_lock:
                            deals_cache[cid_str] = {
                                "latest_deal_price": ldp,
                                "title": title,
                                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            }

            with deals_cache_lock:
                save_deals_cache()

        self.send_json(200, result)

    def handle_api_get_notify_config(self):
        """获取当前企业微信推送配置。"""
        if not notifier:
            self.send_json(500, {"error": "notifier 模块未就绪"})
            return
        cfg = notifier.load_notify_config()
        self.send_json(200, cfg)

    def handle_api_set_notify_config(self):
        """保存企业微信推送配置。"""
        if not notifier:
            self.send_json(500, {"error": "notifier 模块未就绪"})
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            params = json.loads(body)
        except Exception:
            params = {}

        cfg = notifier.load_notify_config()
        cfg.update(params)
        ok = notifier.save_notify_config(cfg)
        if ok:
            self.send_json(200, {"success": True, "config": cfg})
        else:
            self.send_json(500, {"error": "保存推送配置失败"})

    def handle_api_notify_test(self):
        """发送企业微信测试推送。"""
        if not notifier:
            self.send_json(500, {"error": "notifier 模块未就绪"})
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            params = json.loads(body)
            webhook_url = params.get("wecom_webhook", "").strip()
        except Exception:
            webhook_url = ""

        if not webhook_url:
            cfg = notifier.load_notify_config()
            webhook_url = cfg.get("wecom_webhook", "").strip()

        if not webhook_url:
            self.send_json(400, {"error": "请先填入企业微信机器人 Webhook 地址"})
            return

        ok, msg = notifier.send_test_message(webhook_url)
        if ok:
            self.send_json(200, {"success": True, "message": "测试消息发送成功，请在企业微信群中查看！"})
        else:
            self.send_json(400, {"error": msg})

    def handle_api_img_proxy(self, img_url):
        """代理加载 B站 图片，避免客户端因 Referer 策略加载失败。"""
        if not img_url or not img_url.startswith("http"):
            self.send_error(400, "Invalid image URL")
            return
        try:
            req = urllib.request.Request(
                img_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": "https://mall.bilibili.com/",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_type = resp.headers.get("Content-Type", "image/png")
                img_bytes = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(img_bytes)))
                self.end_headers()
                self.wfile.write(img_bytes)
        except Exception as e:
            self.send_error(502, f"Proxy failed: {e}")

    def handle_api_crawl_status(self):
        with crawl_lock:
            status = {
                "running": crawl_state["running"],
                "start_time": crawl_state["start_time"],
                "exit_code": crawl_state["exit_code"],
                "log_lines": crawl_state["log_lines"][-80:],  # 最近 80 行日志
            }
        self.send_json(200, status)

    def handle_api_crawl(self):
        with crawl_lock:
            if crawl_state["running"]:
                self.send_json(409, {"error": "抓取任务正在执行中，请等待完成"})
                return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            params = json.loads(body)
        except Exception:
            params = {}

        category = params.get("category", "898")
        sort = params.get("sort", "hot")
        pages = params.get("pages", None)

        thread = threading.Thread(
            target=run_crawl_thread,
            kwargs={"category": category, "sort": sort, "pages": pages},
            daemon=True,
        )
        thread.start()
        self.send_json(200, {"message": "抓取任务已启动"})

    def send_json(self, status_code, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # 简化静态资源 log 输出
        if not args[0].startswith("GET /api/crawl/status"):
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description="B站会员购转售数据看板 Web 服务器")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--open", action="store_true", help="启动后自动在浏览器打开看板")
    args = parser.parse_args()

    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = (args.host, args.port)

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    httpd = ThreadedHTTPServer(server_address, DashboardHTTPHandler)
    url = f"http://localhost:{args.port}"
    print("=" * 60)
    print(f"🚀 B站会员购转售数据看板 已启动!")
    print(f"🌐 本地访问地址: {url}")
    print(f"💡 按 Ctrl + C 可停止服务器")
    print("=" * 60)

    # 启动后台自动定时巡检调度线程
    threading.Thread(target=scheduler_worker, daemon=True).start()

    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[System] 服务器已停止。")
        httpd.server_close()


if __name__ == "__main__":
    main()
