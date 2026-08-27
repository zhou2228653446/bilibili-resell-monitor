#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 通讯软件消息推送模块 (Notifier)
支持企业微信群机器人 Webhook，支持富文本 Markdown 排版、捡漏防重推送与测试消息。
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFY_CONFIG_PATH = os.path.join(BASE_DIR, "notify_config.json")
PUSHED_CACHE_PATH = os.path.join(BASE_DIR, "pushed_alerts.json")

DEFAULT_CONFIG = {
    "enabled": False,
    "channel": "wecom",
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


def validate_and_sanitize_wecom_url(url):
    """校验并清洗企业微信 Webhook 链接，精准拦截常见误粘链接。"""
    if not url:
        return None, "请输入企业微信群机器人 Webhook 地址"

    url = str(url).strip().strip('"').strip("'").strip()

    # 常见误区 1: 复制了机器人主页/卡片分享链接 (openBotProfile)
    if "openBotProfile" in url or "wework_admin" in url:
        return None, (
            "您刚才复制的是「机器人主页分享链接」，不是「Webhook 接口地址」！\n\n"
            "👉【正确获取位置】：\n"
            "1. 在企业微信群聊设置中，点击您添加的机器人头像/名字；\n"
            "2. 在面板下方找到「Webhook 地址」一栏（带有 key=... 参数）；\n"
            "3. 点击旁边的「复制」按钮（正确格式应为 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...）。"
        )

    # 自动容错: 用户只填了 key=xxxx 或纯 UUID
    if url.startswith("key="):
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?{url}", None

    if len(url) == 36 and url.count("-") == 4:
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={url}", None

    if not url.startswith("http://") and not url.startswith("https://"):
        return None, "Webhook 地址必须以 https:// 开头"

    if "qyapi.weixin.qq.com" not in url or "webhook/send" not in url:
        return None, (
            "链接格式不正确！企业微信群机器人标准 Webhook 地址应以\n"
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key= 开头。\n"
            "请进入群设置 -> 点击机器人名字 -> 复制「Webhook 地址」。"
        )

    return url, None


def send_wecom_markdown(webhook_url, markdown_text):
    """向企业微信机器人发送 Markdown 消息。"""
    clean_url, err = validate_and_sanitize_wecom_url(webhook_url)
    if err:
        return False, err

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_text
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        clean_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("errcode") == 0:
                return True, "发送成功"
            return False, f"企微接口返回错误 ({res.get('errcode')}): {res.get('errmsg')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP 请求失败 ({e.code}): {e.reason}"
    except Exception as e:
        return False, f"网络请求异常: {e}"


def send_test_message(webhook_url):
    """发送测试消息以验证企微机器人连通性。"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    md = f"""### 🔔 **【B站转售监控 · 消息推送联调测试】**
> 📱 **接收端**：企业微信群机器人
> 状态：<font color="info">连接正常 ✓</font>
> ⏰ **测试时间**：{now_str}
> 💡 **监控说明**：后续巡检发现降价捡漏商品时，将自动推送至本群。

[点击进入本地监控大盘](http://localhost:8000)"""
    return send_wecom_markdown(webhook_url, md)


def format_alerts_markdown(alerts, total_items_count=None):
    """将捡漏列表格式化为企微 Markdown 富文本消息。"""
    if not alerts:
        return ""

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"### ⚡ **【B站转售 · 发现 {len(alerts)} 件新降价捡漏！】**",
        f"> ⏰ **巡检时间**：{now_str}",
    ]
    if total_items_count:
        lines.append(f"> 📊 **在售商品总库**：{total_items_count} 件")
    lines.append("")

    # 最多展示前 8 条，避免超出企微单条消息 4096 字符限制
    for idx, a in enumerate(alerts[:8], 1):
        title = a.get("title", "未命名商品")
        cur_p = a.get("cur_price")
        high_p = a.get("high_price")
        drop_pct = a.get("drop_pct")
        drop_abs = a.get("drop_abs")
        url = a.get("url", "#")
        latest_deal = a.get("latest_deal_price", "")

        deal_str = f" | 最近成交: {latest_deal}" if latest_deal else ""

        lines.append(f"**{idx}. [{title}]({url})**")
        lines.append(f"> 🔻 降幅：<font color=\"warning\">**降 {drop_pct}%** (-¥{drop_abs})</font>")
        lines.append(f"> 💰 底价：<font color=\"info\">**¥{cur_p}**</font> (原高位: ¥{high_p}{deal_str})")
        lines.append("")

    if len(alerts) > 8:
        lines.append(f"> ... 及其他 {len(alerts) - 8} 件降价商品，请前往大盘查看完整列表。")

    lines.append("\n[👉 点击打开监控大盘查看详情](http://localhost:8000)")
    return "\n".join(lines)


def process_and_send_alerts(alerts, total_items_count=None, force=False):
    """
    检查新出现的捡漏商品并执行企业微信推送（带去重机制）。
    :param alerts: 降价捡漏商品列表
    :param total_items_count: 当前在售总量
    :param force: 是否强制推送所有（忽略去重）
    """
    cfg = load_notify_config()
    if not cfg.get("enabled"):
        return False, "推送功能未开启"

    webhook_url = cfg.get("wecom_webhook", "").strip()
    if not webhook_url:
        return False, "未配置企业微信 Webhook"

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

        # 没推送过，或者比上次推送价格更低
        if force or last_pushed_price is None or cur_p < float(last_pushed_price) - 0.01:
            new_alerts_to_push.append(a)
            pushed_cache[cid] = cur_p

    if not new_alerts_to_push:
        return True, "所有捡漏商品已在此前推送过，跳过重复发送"

    # 3. 构造富文本消息并发送
    md_content = format_alerts_markdown(new_alerts_to_push, total_items_count)
    ok, msg = send_wecom_markdown(webhook_url, md_content)
    if ok:
        save_pushed_cache(pushed_cache)
        print(f"[Notifier] 成功向企业微信推送 {len(new_alerts_to_push)} 件新降价商品！")
    else:
        print(f"[Notifier] 企业微信推送失败: {msg}", file=sys.stderr)

    return ok, msg


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        cfg = load_notify_config()
        url = sys.argv[2] if len(sys.argv) > 2 else cfg.get("wecom_webhook")
        print(f"正在向 {url} 发送测试消息...")
        success, res_msg = send_test_message(url)
        print(f"结果: {'成功' if success else '失败'} - {res_msg}")
