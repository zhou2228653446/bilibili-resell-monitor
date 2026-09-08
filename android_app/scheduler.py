# -*- coding: utf-8 -*-
"""
Android 前后台定时巡检调度器
支持:
1. 可配置巡检周期 (15分钟 / 30分钟 / 1小时 / 2小时)
2. 后台守护线程周期性运行
3. 发现低于成交价或3折好物时，自动向系统通知栏触发通知
4. 去重缓存 (pushed_alerts.json)，避免同件商品重复打扰
"""
import json
import os
import sys
import threading
import time

from android_compat import get_out_path
import bili_resell
import notification_helper

CONFIG_PATH = get_out_path("schedule_config.json")
PUSHED_PATH = get_out_path("pushed_alerts.json")
JSON_PATH = get_out_path("3c_products.json")


def _parse_num(s):
    try:
        return float(str(s).replace("¥", "").replace(",", "").strip())
    except Exception:
        return None


class AutoCrawlScheduler:
    def __init__(self, on_crawl_complete_cb=None, on_log_cb=None):
        self.on_crawl_complete_cb = on_crawl_complete_cb
        self.on_log_cb = on_log_cb
        self.lock = threading.Lock()
        self.running_crawl = False

        self.config = {
            "enabled": False,
            "interval_minutes": 30,
            "category": "898",
            "sort": "hot",
            "pages": 15,
            "last_run": "",
            "next_run": "",
            "next_run_ts": 0,
        }
        self.load_config()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="AutoCrawlScheduler"
        )
        self._thread.start()

    def load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
        except Exception as e:
            print(f"[Scheduler] 加载配置异常: {e}")

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Scheduler] 保存配置失败: {e}")

    def set_enabled(self, enabled):
        with self.lock:
            self.config["enabled"] = enabled
            if enabled:
                # 立即安排下一次运行时间
                interval = max(1, self.config.get("interval_minutes", 30)) * 60
                now = time.time()
                self.config["next_run_ts"] = now + interval
                self.config["next_run"] = time.strftime(
                    "%H:%M:%S", time.localtime(self.config["next_run_ts"])
                )
            else:
                self.config["next_run"] = "已暂停"
                self.config["next_run_ts"] = 0
            self.save_config()

    def set_interval(self, minutes):
        with self.lock:
            self.config["interval_minutes"] = minutes
            if self.config["enabled"]:
                now = time.time()
                self.config["next_run_ts"] = now + minutes * 60
                self.config["next_run"] = time.strftime(
                    "%H:%M:%S", time.localtime(self.config["next_run_ts"])
                )
            self.save_config()

    def get_status_summary(self):
        with self.lock:
            if not self.config.get("enabled"):
                return "已关闭自动巡检"
            next_ts = self.config.get("next_run_ts", 0)
            now = time.time()
            if next_ts > now:
                remaining_min = int((next_ts - now) / 60)
                return f"下次巡检: {self.config.get('next_run')} (约 {remaining_min} 分钟后)"
            return "即将执行巡检…"

    def _worker_loop(self):
        while not self._stop_event.is_set():
            time.sleep(3)
            with self.lock:
                enabled = self.config.get("enabled", False)
                next_ts = self.config.get("next_run_ts", 0)
                now = time.time()

            if not enabled:
                continue

            if now >= next_ts and not self.running_crawl:
                # 触发巡检
                self._trigger_crawl()

    def _trigger_crawl(self):
        with self.lock:
            self.running_crawl = True
            interval_sec = (
                max(1, self.config.get("interval_minutes", 30)) * 60
            )
            now = time.time()
            self.config["next_run_ts"] = now + interval_sec
            self.config["last_run"] = time.strftime("%H:%M:%S")
            self.config["next_run"] = time.strftime(
                "%H:%M:%S", time.localtime(now + interval_sec)
            )
            self.save_config()
            cat = self.config.get("category", "898")
            sort = self.config.get("sort", "hot")
            pages = self.config.get("pages", 15)

        msg = f"[定时巡检触发] 品类={cat}, 排序={sort}, 深度={pages}页..."
        print(msg)
        if self.on_log_cb:
            self.on_log_cb(msg)

        def worker():
            try:
                res = bili_resell.crawl_and_export(
                    category=cat,
                    sort=sort,
                    pages=pages,
                    output_json=JSON_PATH,
                    log_callback=self.on_log_cb,
                )
                self._check_and_notify_deals(res)
                if self.on_crawl_complete_cb:
                    self.on_crawl_complete_cb()
            except Exception as e:
                print(f"[Scheduler] 自动抓取失败: {e}")
                if self.on_log_cb:
                    self.on_log_cb(f"[定时巡检异常] {e}")
            finally:
                self.running_crawl = False

        threading.Thread(target=worker, daemon=True).start()

    def _check_and_notify_deals(self, crawl_res):
        """对比成交价与历史推送缓存，发现新漏品时触发通知栏通知。"""
        if not crawl_res or not isinstance(crawl_res, dict):
            return
        products = crawl_res.get("products", [])
        if not products:
            return

        # 加载已推送缓存 (cid -> price)
        pushed = {}
        if os.path.exists(PUSHED_PATH):
            try:
                with open(PUSHED_PATH, "r", encoding="utf-8") as f:
                    pushed = json.load(f)
            except Exception:
                pushed = {}

        new_deals = []
        for p in products:
            cid = str(p.get("cluster_id") or "")
            if not cid:
                continue
            cur_p = _parse_num(p.get("price"))
            deal_p = _parse_num(p.get("latest_deal_price"))
            ref_p = _parse_num(p.get("reference_price"))

            is_below_deal = cur_p and deal_p and cur_p < deal_p
            is_super_disc = (
                cur_p and ref_p and ref_p > 0 and (cur_p / ref_p) <= 0.3
            )

            if is_below_deal or is_super_disc:
                last_price = pushed.get(cid)
                if last_price is None or cur_p < last_price:
                    new_deals.append((p, is_below_deal, is_super_disc))
                    pushed[cid] = cur_p

        # 保存更新后的已推送记录
        try:
            with open(PUSHED_PATH, "w", encoding="utf-8") as f:
                json.dump(pushed, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if new_deals:
            top_p, is_b, is_s = new_deals[0]
            title = f"发现 {len(new_deals)} 件超值转售捡漏！"
            p_name = top_p.get("title", "未知商品")
            if len(p_name) > 18:
                p_name = p_name[:18] + "…"
            tag = "低于成交价" if is_b else "3折神价"
            cur_price = top_p.get("price", "")
            body = f"【{tag}】{p_name} 现价 {cur_price}，点击进入 App 查看全部捡漏列表！"
            notification_helper.send_system_notification(
                title=title, message=body, subtext="B站捡漏自动巡检"
            )
