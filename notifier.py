#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 消息推送模块 (Notifier)
支持 100% 永久免费的手机微信即时提醒与移动端一键直达抢购：
1. 💌 QQ邮箱 -> 微信实时弹窗提醒 (100% 腾讯官方、无图轻量化、多商品全量直达链接)
2. 📱 WxPusher 微信消息推送平台 (完全免费)
3. 🍎 iOS Bark (iPhone 原生系统横幅推送，完全免费)
4. 🚀 Server酱 Turbo (经典微信推送)
5. 🏢 企业微信 Webhook
"""

import json
import os
import sys
import time
import csv
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
import urllib.request
import urllib.parse
import urllib.error

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFY_CONFIG_PATH = os.path.join(BASE_DIR, "notify_config.json")
PUSHED_CACHE_PATH = os.path.join(BASE_DIR, "pushed_alerts.json")
HISTORY_CSV_PATH = os.path.join(BASE_DIR, "3c_products_history.csv")
CURRENT_CSV_PATH = os.path.join(BASE_DIR, "3c_products.csv")

DEFAULT_CONFIG = {
    "enabled": False,
    "channel": "qq_email",  # "qq_email" | "wxpusher" | "bark" | "serverchan" | "wecom"
    "notify_below_deal_only": False,  # 是否仅推送低于上次成交价的商品
    "notify_below_three_discount": True,  # 是否包含低于原价3折的新上架好物
    # QQ 邮箱配置 (微信直接弹窗提醒)
    "qq_email": "",
    "qq_smtp_code": "",
    "receiver_email": "",
    # WxPusher 配置
    "wxpusher_app_token": "",
    "wxpusher_uid": "",
    # Bark (iOS) 配置
    "bark_key_or_url": "",
    # Server酱
    "serverchan_key": "",
    # 企业微信
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


def ensure_https_url(url, cluster_id=None):
    """确保 URL 带有 https: 前缀，若无则使用标准 B 站转售链接。"""
    if not url and cluster_id:
        return f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={cluster_id}"
    url = str(url).strip()
    if url.startswith("//"):
        return f"https:{url}"
    if not url.startswith("http"):
        if cluster_id:
            return f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={cluster_id}"
    return url


def get_current_history_alerts():
    """从历史数据中提取当前所有降价捡漏商品。"""
    try:
        # 尝试通过 web_server 的计算引擎直接获取最新 alerts
        from web_server import get_processed_data
        data = get_processed_data()
        alerts = data.get("alerts", [])
        if alerts:
            return alerts
    except Exception:
        pass
    return []


def parse_deal_price_float(deal_val):
    """从成交价格字符串中解析出浮点数。"""
    if not deal_val:
        return None
    s = str(deal_val).replace("¥", "").replace("￥", "").strip()
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


# ==================== 无图片·轻量化·高密度全量邮件生成器 ====================
def build_clean_email_html(alerts, title, subtitle=None):
    """
    生成无图片的轻量化 HTML 邮件：
    1. 不含任何沉重图片，加载极速，手机端绝不卡顿或排版错乱；
    2. 支持一次性展示多达 30~50 件降价商品；
    3. 每件商品包含【名称、底价、原高位、降幅、最近市集成交价与倒挂标识、直接点击抢购链接】。
    """
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    sub = subtitle or f"巡检时间：{now_str} · 共发现 {len(alerts)} 件降价好物"

    items_html = []
    for idx, a in enumerate(alerts[:40], 1):
        cid = a.get("cluster_id")
        raw_url = a.get("url") or f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={cid}"
        bili_url = ensure_https_url(raw_url, cid)
        title_text = a.get("title", "未命名商品")
        cur_p = float(a.get("cur_price", 0.0))
        high_p = a.get("high_price", "0.00")
        drop_pct = a.get("drop_pct", "0")
        drop_abs = a.get("drop_abs", "0.00")
        deal_p = a.get("latest_deal_price", "")
        deal_num = parse_deal_price_float(deal_p)

        deal_badge = ""
        if deal_num is not None:
            if cur_p < deal_num:
                diff = round(deal_num - cur_p, 2)
                deal_badge = f'<span style="display:inline-block; padding:1px 6px; font-size:11px; background:#dcfce7; color:#15803d; border-radius:4px; font-weight:bold; margin-left:4px;">🔥 低于上次成交 ¥{deal_p} (省¥{diff})</span>'
            else:
                deal_badge = f'<span style="display:inline-block; padding:1px 6px; font-size:11px; background:#eff6ff; color:#1d4ed8; border-radius:4px; font-weight:600; margin-left:4px;">市集成交: {deal_p}</span>'

        super_discount_badge = ""
        ref_p = parse_deal_price_float(a.get("reference_price") or a.get("high_price"))
        if ref_p and ref_p > 0:
            rate = cur_p / ref_p
            if rate <= 0.30:
                super_discount_badge = f'<span style="display:inline-block; padding:1px 6px; font-size:11px; background:#fef3c7; color:#b45309; border-radius:4px; font-weight:bold; margin-left:4px;">🏷️ 超低{(rate*10):.1f}折神价</span>'

        items_html.append(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px; margin-bottom:10px;">
            <div style="font-size:14px; font-weight:bold; line-height:1.4;">
                <span style="color:#fb7299; margin-right:4px;">#{idx}</span>
                <a href="{bili_url}" target="_blank" style="color:#0f172a; text-decoration:none;">{title_text}</a>
            </div>
            <div style="margin:8px 0 6px 0; font-size:13px; color:#475569; display:flex; align-items:baseline; flex-wrap:wrap; gap:6px;">
                <span style="color:#ef4444; font-size:16px; font-weight:800;">¥{cur_p:.2f}</span>
                <span style="color:#94a3b8; font-size:11px; text-decoration:line-through;">原高位: ¥{high_p}</span>
                <span style="display:inline-block; padding:1px 6px; font-size:11px; background:#fee2e2; color:#b91c1c; border-radius:4px; font-weight:bold;">🔻降 {drop_pct}% (-¥{drop_abs})</span>
                {deal_badge}
                {super_discount_badge}
            </div>
            <div style="font-size:11px; word-break:break-all; padding-top:4px; border-top:1px dashed #f1f5f9;">
                <span style="color:#64748b;">🔗 抢购链接: </span>
                <a href="{bili_url}" target="_blank" style="color:#2563eb; text-decoration:underline;">{bili_url}</a>
            </div>
        </div>
        """)

    all_items_str = "\n".join(items_html)

    extra_note = ""
    if len(alerts) > 40:
        extra_note = f"""
        <div style="padding:10px; text-align:center; color:#64748b; font-size:12px;">
            *... 以及其他 {len(alerts) - 40} 件降价商品（已按降幅前40件优先展示）*
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:12px; background-color:#f8fafc; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <div style="max-width:600px; margin:0 auto;">
        <!-- Header -->
        <div style="background:linear-gradient(135deg, #fb7299, #e11d48); padding:16px 20px; border-radius:14px; color:#ffffff; margin-bottom:12px;">
            <h1 style="margin:0; font-size:18px; font-weight:bold;">{title}</h1>
            <div style="margin-top:4px; font-size:12px; opacity:0.95;">⏰ {sub}</div>
        </div>

        <!-- Items List -->
        {all_items_str}
        {extra_note}

        <!-- Footer -->
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px; text-align:center; color:#64748b; font-size:12px; line-height:1.5; margin-top:8px;">
            <p style="margin:0; color:#334155; font-weight:bold;">💡 手机端操作提示：</p>
            <p style="margin:2px 0 0 0;">点击上方任意商品标题或蓝色的「抢购链接」，即可直接在手机上打开 B 站完成购买！</p>
        </div>
    </div>
</body>
</html>"""


# ==================== 1. QQ邮箱 -> 微信即时通知 (100% 永久免费) ====================
def send_qq_email(sender_email, auth_code, receiver_email, title, content_markdown, html_content=None):
    """
    通过 QQ 邮箱 SMTP 发送捡漏提醒邮件。
    微信开启「QQ邮箱提醒」后，手机微信将直接弹出实时消息通知！
    """
    sender = str(sender_email).strip()
    auth = str(auth_code).strip()
    receiver = str(receiver_email).strip() or sender

    if not sender or "@" not in sender:
        return False, "请填入有效的发送 QQ 邮箱（例如: 123456@qq.com）"
    if not auth:
        return False, "请填入 QQ 邮箱 SMTP 授权码（登录 mail.qq.com -> 设置 -> 账户开启生成）"

    if not html_content:
        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 16px;">
            <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #fb7299;">{title}</h2>
            <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; background: #f8fafc; padding: 12px; border-radius: 8px; color: #1e293b; font-size: 13px;">{content_markdown}</pre>
        </div>
        """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = formataddr(("B站捡漏监控", sender))
    msg["To"] = formataddr(("微信提醒", receiver))

    part1 = MIMEText(content_markdown, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=12)
        server.login(sender, auth)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()
        return True, "邮件发送成功！微信「QQ邮箱提醒」将立即弹窗提示。"
    except smtplib.SMTPAuthenticationError:
        return False, "QQ 邮箱授权码错误或未开启 POP3/SMTP 服务，请重新生成授权码"
    except Exception as e:
        return False, f"邮件发送失败: {e}"


# ==================== 2. WxPusher 微信消息推送 (完全免费) ====================
def send_wxpusher(app_token, uid, title, content_markdown):
    """通过 WxPusher 向个人微信发送 Markdown 消息。"""
    app_token = str(app_token).strip()
    uid = str(uid).strip()

    if not app_token:
        return False, "WxPusher AppToken 不能为空，请登录 wxpusher.zjiecode.com 创建应用获取"
    if not uid:
        return False, "WxPusher UID 不能为空，请在平台关注公众号后在「我的用户」中复制 UID"

    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": app_token,
        "content": f"## {title}\n\n{content_markdown}",
        "summary": title[:30],
        "contentType": 3,
        "uids": [uid],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 1000:
                return True, "WxPusher 微信推送成功！"
            return False, f"WxPusher 错误: {res.get('msg', res)}"
    except Exception as e:
        return False, f"WxPusher 请求失败: {e}"


# ==================== 3. iOS Bark (iPhone 原生通知，完全免费) ====================
def send_bark(key_or_url, title, content_text):
    """向 iPhone Bark App 发送原生系统横幅通知。"""
    key = str(key_or_url).strip().rstrip("/")
    if not key:
        return False, "Bark Key 不能为空（请在 App Store 下载 Bark 获取专属 Key）"

    if key.startswith("http"):
        base_url = key
    else:
        base_url = f"https://api.day.app/{key}"

    payload = {
        "title": title,
        "body": content_text,
        "group": "B站捡漏监控",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 200:
                return True, "Bark 推送成功，已在 iPhone 弹出通知！"
            return False, f"Bark 返回: {res.get('message', res)}"
    except Exception as e:
        return False, f"Bark 请求失败: {e}"


# ==================== 4. 统一分发器 ====================
def send_unified_message(channel, title, markdown_text, config, html_content=None):
    """统一向指定渠道分发消息。"""
    if channel == "qq_email":
        return send_qq_email(
            config.get("qq_email", ""),
            config.get("qq_smtp_code", ""),
            config.get("receiver_email", ""),
            title,
            markdown_text,
            html_content=html_content
        )
    elif channel == "wxpusher":
        return send_wxpusher(
            config.get("wxpusher_app_token", ""),
            config.get("wxpusher_uid", ""),
            title,
            markdown_text
        )
    elif channel == "bark":
        return send_bark(
            config.get("bark_key_or_url", ""),
            title,
            markdown_text
        )
    elif channel == "serverchan":
        key = config.get("serverchan_key", "").strip()
        url = f"https://sctapi.ftqq.com/{key}.send"
        params = urllib.parse.urlencode({"title": title, "desp": markdown_text}).encode("utf-8")
        req = urllib.request.Request(url, data=params, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return (True, "发送成功") if res.get("code") == 0 else (False, res.get("message"))
        except Exception as e:
            return False, str(e)
    elif channel == "wecom":
        url = config.get("wecom_webhook", "").strip()
        payload = {"msgtype": "markdown", "markdown": {"content": markdown_text}}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return (True, "企微发送成功") if res.get("errcode") == 0 else (False, res.get("errmsg"))
        except Exception as e:
            return False, str(e)
    else:
        return False, f"未知的推送渠道: {channel}"


def format_alerts_markdown(alerts, total_items_count=None):
    """将捡漏列表格式化为纯文本消息（包含所有商品的标题、底价、降幅与直接链接）。"""
    if not alerts:
        return ""

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"⚡【B站转售 · 发现 {len(alerts)} 件新降价捡漏！】",
        f"⏰ 巡检时间：{now_str}",
    ]
    if total_items_count:
        lines.append(f"📊 监控在售商品总数：{total_items_count} 件")
    lines.append("--------------------------------------------")

    for idx, a in enumerate(alerts[:30], 1):
        cid = a.get("cluster_id")
        title = a.get("title", "未命名商品")
        cur_p = a.get("cur_price")
        high_p = a.get("high_price")
        drop_pct = a.get("drop_pct")
        drop_abs = a.get("drop_abs")
        raw_url = a.get("url") or f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={cid}"
        bili_url = ensure_https_url(raw_url, cid)
        latest_deal = a.get("latest_deal_price", "")
        deal_str = f" | 最近成交: {latest_deal}" if latest_deal else ""

        lines.append(f"{idx}. {title}")
        lines.append(f"   💰 底价: ¥{cur_p} (原高位: ¥{high_p}{deal_str})")
        lines.append(f"   🔻 降幅: 降 {drop_pct}% (-¥{drop_abs})")
        lines.append(f"   🔗 抢购直达: {bili_url}")
        lines.append("")

    if len(alerts) > 30:
        lines.append(f"... 以及其他 {len(alerts) - 30} 件降价商品。")

    lines.append("--------------------------------------------")
    lines.append("💡 在手机上点击上方链接即可直接打开 B 站购买！")
    return "\n".join(lines)


def send_test_message(config=None):
    """发送测试消息（自动拉取当前数据库中所有真实的降价捡漏商品，展示完整列表与B站抢购链接）。"""
    if config is None:
        config = load_notify_config()

    channel = config.get("channel", "qq_email")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # 获取当前真实所有的捡漏商品列表
    current_alerts = get_current_history_alerts()
    if not current_alerts:
        # 若历史记录不足两轮，提供 3 条真实格式的示例商品
        current_alerts = [
            {
                "cluster_id": "10000000603",
                "title": "FEELALL 星空旋律 鼠标垫 凪款",
                "cur_price": 9.00,
                "high_price": 30.00,
                "drop_abs": 21.00,
                "drop_pct": 70.0,
                "latest_deal_price": "¥8.92",
                "url": "https://mall.bilibili.com/neul-next/resell/detail.html?clusterId=10000000603"
            },
            {
                "cluster_id": "10000000604",
                "title": "B站会员购 3C数码周边 / 降价好物示例 A",
                "cur_price": 35.00,
                "high_price": 70.00,
                "drop_abs": 35.00,
                "drop_pct": 50.0,
                "latest_deal_price": "¥36.00",
                "url": "https://mall.bilibili.com/neul-next/resell/detail.html?clusterId=10000000604"
            },
            {
                "cluster_id": "10000000605",
                "title": "漫展联名 机械键盘键帽定制款 示例 B",
                "cur_price": 49.00,
                "high_price": 89.00,
                "drop_abs": 40.00,
                "drop_pct": 44.9,
                "latest_deal_price": "¥52.00",
                "url": "https://mall.bilibili.com/neul-next/resell/detail.html?clusterId=10000000605"
            }
        ]

    only_below_deal = bool(config.get("notify_below_deal_only", False))
    if only_below_deal:
        below_only_list = [
            a for a in current_alerts
            if parse_deal_price_float(a.get("latest_deal_price")) and float(a.get("cur_price", 0)) < parse_deal_price_float(a.get("latest_deal_price"))
        ]
        if below_only_list:
            current_alerts = below_only_list

    title = f"🔔【B站转售监控 · 微信推送测试 (共 {len(current_alerts)} 件商品)】"
    md = format_alerts_markdown(current_alerts)
    sub_title = "已开启「仅推送低于上次成交价」" if only_below_deal else f"当前共 {len(current_alerts)} 件降价好物"
    html = build_clean_email_html(current_alerts, f"🔔 微信消息推送测试 ({sub_title})", f"测试时间：{now_str} · 点击任意链接即可手机打开 B站 抢购")
    return send_unified_message(channel, title, md, config, html_content=html)


def process_and_send_alerts(alerts, total_items_count=None, force=False):
    """检查新出现的捡漏商品并执行全量轻量化推送（带去重机制、低于上次成交价过滤与B站直达链接）。"""
    cfg = load_notify_config()
    if not cfg.get("enabled"):
        return False, "推送功能未开启"

    channel = cfg.get("channel", "qq_email")
    min_drop_pct = float(cfg.get("min_drop_pct", 10.0))
    min_drop_abs = float(cfg.get("min_drop_abs", 10.0))
    notify_below_deal_only = bool(cfg.get("notify_below_deal_only", False))
    notify_below_three_discount = bool(cfg.get("notify_below_three_discount", True))

    # 1. 过滤符合用户自定义规则的商品
    eligible = []
    for a in alerts:
        cur_p = float(a.get("cur_price", 0))
        deal_num = parse_deal_price_float(a.get("latest_deal_price"))
        is_below_deal = (deal_num is not None and cur_p < deal_num)

        ref_p = parse_deal_price_float(a.get("reference_price") or a.get("high_price"))
        title_str = str(a.get("title", "")).upper()
        is_feelall = "FEELALL" in title_str
        is_super_discount = (ref_p is not None and ref_p > 0 and (cur_p / ref_p) <= 0.30 and not is_feelall)

        drop_pct = float(a.get("drop_pct", 0))
        drop_abs = float(a.get("drop_abs", 0))

        if notify_below_deal_only:
            # 严格模式：只推送当前在售底价低于最近一次市集成交价的商品
            if is_below_deal:
                eligible.append(a)
        else:
            # 常规模式：降幅/降额达标 或 低于市集成交价 或 低于原价3折
            if drop_pct >= min_drop_pct or drop_abs >= min_drop_abs or is_below_deal or (notify_below_three_discount and is_super_discount):
                eligible.append(a)

    if not eligible:
        return True, "无达到设定规则的捡漏商品"

    # 2. 去重过滤
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

    # 3. 构造无图片、高密度轻量化全量消息并发送
    title = f"⚡【B站转售 · 发现 {len(new_alerts_to_push)} 件新降价捡漏！】"
    md_content = format_alerts_markdown(new_alerts_to_push, total_items_count)
    html_content = build_clean_email_html(new_alerts_to_push, title)

    ok, msg = send_unified_message(channel, title, md_content, cfg, html_content=html_content)
    if ok:
        save_pushed_cache(pushed_cache)
        print(f"[Notifier] 成功向 {channel} 推送 {len(new_alerts_to_push)} 件新降价商品！")
    else:
        print(f"[Notifier] 推送失败: {msg}", file=sys.stderr)

    return ok, msg


if __name__ == "__main__":
    cfg = load_notify_config()
    print("正在测试发送消息...")
    ok, res = send_test_message(cfg)
    print(f"结果: {'成功' if ok else '失败'} -> {res}")
