#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 消息推送模块 (Notifier)
支持：
1. 微信推送（PushPlus 推送加 - 扫码即用，每天免费200条）
2. 微信推送（Server酱 Turbo - 方糖服务号推送）
3. 企业微信群机器人 Webhook
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFY_CONFIG_PATH = os.path.join(BASE_DIR, "notify_config.json")
PUSHED_CACHE_PATH = os.path.join(BASE_DIR, "pushed_alerts.json")

DEFAULT_CONFIG = {
    "enabled": False,
    "channel": "pushplus",  # "pushplus" | "serverchan" | "wecom"
    "pushplus_token": "",
    "serverchan_key": "",
    "wecom_webhook": "",
    "min_drop_pct": 10.0,
    "min_drop_abs": 10.0,
    "notify_on_new_drop": True,
    "notify_summary": False,
}


def load_notify_config():
    """读取推送配置。"""
    if os.path.exists(NOTIFY_CONFIG_PATH):
        try:
            with open(NOTIFY_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_notify_config(cfg):
    """保存推送配置。"""
    try:
        with open(NOTIFY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Warn] 保存推送配置失败: {e}", file=sys.stderr)
        return False


def load_pushed_cache():
    """读取已推送过的商品告警记录 (cluster_id -> last_pushed_price)。"""
    if os.path.exists(PUSHED_CACHE_PATH):
        try:
            with open(PUSHED_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_pushed_cache(cache):
    """保存已推送记录。"""
    try:
        with open(PUSHED_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==================== 1. 微信推送：PushPlus (推荐) ====================
def send_pushplus(token, title, content_markdown):
    """向个人微信 (PushPlus 推送加服务号) 发送 Markdown 卡片消息。"""
    token = str(token).strip()
    if not token:
        return False, "PushPlus Token 不能为空，请登录 www.pushplus.plus 扫码获取"

    url = "https://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": title,
        "content": content_markdown,
        "template": "markdown"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 200:
                return True, "微信推送成功！"
            return False, f"PushPlus 返回错误: {res.get('msg', res)}"
    except Exception as e:
        return False, f"PushPlus 网络请求失败: {e}"


# ==================== 2. 微信推送：Server酱 Turbo ====================
def send_serverchan(sendkey, title, content_markdown):
    """向个人微信 (Server酱 / 方糖服务号) 发送消息。"""
    sendkey = str(sendkey).strip()
    if not sendkey:
        return False, "Server酱 SendKey 不能为空，请登录 sct.ftqq.com 扫码获取"

    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    params = urllib.parse.urlencode({
        "title": title,
        "desp": content_markdown
    }).encode("utf-8")
    req = urllib.request.Request(url, data=params, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0:
                return True, "微信推送成功！"
            return False, f"Server酱返回错误: {res.get('message', res)}"
    except Exception as e:
        return False, f"Server酱网络请求失败: {e}"


# ==================== 3. 企业微信群机器人 Webhook ====================
def send_wecom(webhook_url, content_markdown):
    """向企业微信群机器人发送 Markdown 消息。"""
    url = str(webhook_url).strip()
    if not url or not url.startswith("http"):
        return False, "无效的企业微信 Webhook 地址"

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content_markdown}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("errcode") == 0:
                return True, "企微发送成功"
            return False, f"企微接口返回错误: {res.get('errmsg')}"
    except Exception as e:
        return False, f"网络请求失败: {e}"


# ==================== 统一消息分发与格式化 ====================
def send_unified_message(channel, title, markdown_text, config):
    """统一向指定渠道分发消息。"""
    if channel == "pushplus":
        token = config.get("pushplus_token", "").strip()
        return send_pushplus(token, title, markdown_text)
    elif channel == "serverchan":
        key = config.get("serverchan_key", "").strip()
        return send_serverchan(key, title, markdown_text)
    elif channel == "wecom":
        url = config.get("wecom_webhook", "").strip()
        return send_wecom(url, markdown_text)
    else:
        return False, f"未知的推送渠道: {channel}"


def send_test_message(config=None):
    """发送微信测试消息以验证连通性。"""
    if config is None:
        config = load_notify_config()

    channel = config.get("channel", "pushplus")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    channel_name = {
        "pushplus": "微信 (PushPlus 推送加)",
        "serverchan": "微信 (Server酱 / 方糖气球)",
        "wecom": "企业微信群机器人"
    }.get(channel, channel)

    title = "🔔【B站转售监控 · 微信推送联调测试】"
    md = f"""### 🔔 **B站转售监控 · 微信消息推送测试**

- 📱 **推送通道**：{channel_name}
- ✅ **连接状态**：正常已联通
- ⏰ **测试时间**：{now_str}
- 💡 **提示**：后续自动巡检中若发现降价捡漏商品，将自动通过微信发送至本窗口。

---
[👉 点击打开本地监控大盘](http://localhost:8000)
"""
    return send_unified_message(channel, title, md, config)


def format_alerts_markdown(alerts, total_items_count=None):
    """将捡漏列表格式化为 Markdown 富文本消息。"""
    if not alerts:
        return ""

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"### ⚡ **【B站转售 · 发现 {len(alerts)} 件新降价捡漏！】**",
        f"- ⏰ **巡检时间**：{now_str}",
    ]
    if total_items_count:
        lines.append(f"- 📊 **监控总在售商品**：{total_items_count} 件")
    lines.append("\n---\n")

    # 最多展示前 8 条
    for idx, a in enumerate(alerts[:8], 1):
        title = a.get("title", "未命名商品")
        cur_p = a.get("cur_price")
        high_p = a.get("high_price")
        drop_pct = a.get("drop_pct")
        drop_abs = a.get("drop_abs")
        url = a.get("url", "#")
        latest_deal = a.get("latest_deal_price", "")
        deal_str = f" (最近成交: {latest_deal})" if latest_deal else ""

        lines.append(f"**{idx}. [{title}]({url})**")
        lines.append(f"- 🔻 **降幅**：降 **{drop_pct}%** (-¥{drop_abs})")
        lines.append(f"- 💰 **底价**：¥**{cur_p}** (历史高位: ¥{high_p}{deal_str})")
        lines.append("")

    if len(alerts) > 8:
        lines.append(f"\n*... 及其他 {len(alerts) - 8} 件降价商品，请前往大盘查看完整列表。*")

    lines.append("\n[👉 点击打开本地监控大盘抢购](http://localhost:8000)")
    return "\n".join(lines)


def process_and_send_alerts(alerts, total_items_count=None, force=False):
    """检查新出现的捡漏商品并执行微信推送（带去重机制）。"""
    cfg = load_notify_config()
    if not cfg.get("enabled"):
        return False, "推送功能未开启"

    channel = cfg.get("channel", "pushplus")
    min_drop_pct = float(cfg.get("min_drop_pct", 10.0))
    min_drop_abs = float(cfg.get("min_drop_abs", 10.0))

    # 1. 过滤符合用户自定义阈值的商品
    eligible = []
    for a in alerts:
        drop_pct = float(a.get("drop_pct", 0))
        drop_abs = float(a.get("drop_abs", 0))
        if drop_pct >= min_drop_pct or drop_abs >= min_drop_abs:
            eligible.append(a)

    if not eligible:
        return True, "无达到阈值的捡漏商品"

    # 2. 去重过滤（只推送新商品或价格更低的商品）
    pushed_cache = load_pushed_cache()
    new_alerts_to_push = []

    for a in eligible:
        cid = str(a.get("cluster_id"))
        cur_p = float(a.get("cur_price", 0))
        last_pushed_price = pushed_cache.get(cid)

        if force or last_pushed_price is None or cur_p < float(last_pushed_price) - 0.01:
            new_alerts_to_push.append(a)
            pushed_cache[cid] = cur_p

    if not new_alerts_to_push:
        return True, "所有捡漏商品已在此前推送过，跳过重复发送"

    # 3. 构造富文本消息并发送
    title = f"⚡【B站转售 · 发现 {len(new_alerts_to_push)} 件新降价捡漏！】"
    md_content = format_alerts_markdown(new_alerts_to_push, total_items_count)
    ok, msg = send_unified_message(channel, title, md_content, cfg)
    if ok:
        save_pushed_cache(pushed_cache)
        print(f"[Notifier] 成功向 {channel} 推送 {len(new_alerts_to_push)} 件新降价商品！")
    else:
        print(f"[Notifier] 微信推送失败: {msg}", file=sys.stderr)

    return ok, msg


if __name__ == "__main__":
    cfg = load_notify_config()
    print("正在测试发送微信消息...")
    ok, res = send_test_message(cfg)
    print(f"结果: {'成功' if ok else '失败'} -> {res}")
