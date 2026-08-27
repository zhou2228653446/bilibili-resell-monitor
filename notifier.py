#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 消息推送模块 (Notifier)
支持 100% 永久免费的手机微信即时提醒与移动端一键直达抢购：
1. 💌 QQ邮箱 -> 微信实时弹窗提醒 (100% 腾讯官方、永久免费、手机直达B站)
2. 📱 WxPusher 微信消息推送平台 (完全免费)
3. 🍎 iOS Bark (iPhone 原生系统横幅推送，完全免费)
4. 🚀 Server酱 Turbo (经典微信推送)
5. 🏢 企业微信 Webhook
"""

import json
import os
import sys
import time
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

DEFAULT_CONFIG = {
    "enabled": False,
    "channel": "qq_email",  # "qq_email" | "wxpusher" | "bark" | "serverchan" | "wecom"
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


def ensure_https_url(url):
    """确保 URL 带有 https: 前缀。"""
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("//"):
        return f"https:{url}"
    return url


# ==================== 手机端富文本邮件 HTML 生成器 ====================
def build_mobile_email_html(alerts, title, subtitle=None):
    """生成专为手机微信/移动邮箱优化的自适应 HTML 邮件（带商品图与B站直达抢购按钮）。"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    sub = subtitle or f"巡检时间：{now_str} · 发现 {len(alerts)} 件降价好物"

    items_html = []
    for idx, a in enumerate(alerts[:10], 1):
        raw_url = a.get("url") or f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={a.get('cluster_id')}"
        bili_url = ensure_https_url(raw_url)
        img_url = ensure_https_url(a.get("img", ""))
        title_text = a.get("title", "未命名商品")
        cur_p = a.get("cur_price", "0.00")
        high_p = a.get("high_price", "0.00")
        drop_pct = a.get("drop_pct", "0")
        drop_abs = a.get("drop_abs", "0.00")
        deal_p = a.get("latest_deal_price", "")

        deal_badge = f'<span style="display:inline-block; padding:2px 8px; font-size:11px; background:#eff6ff; color:#2563eb; border-radius:6px; font-weight:600; margin-left:4px;">市集成交: {deal_p}</span>' if deal_p else ''

        img_tag = f'<img src="{img_url}" style="width:72px; height:72px; object-fit:cover; border-radius:10px; border:1px solid #f1f5f9; flex-shrink:0;" alt="cover" />' if img_url else '<div style="width:72px; height:72px; background:#f1f5f9; border-radius:10px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:10px;">暂无图片</div>'

        items_html.append(f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:14px; margin-bottom:12px; box-shadow:0 2px 6px rgba(0,0,0,0.03);">
            <div style="display:flex; gap:12px; align-items:flex-start;">
                {img_tag}
                <div style="flex:1; min-width:0;">
                    <a href="{bili_url}" target="_blank" style="text-decoration:none; color:#0f172a; font-weight:bold; font-size:14px; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
                        {title_text}
                    </a>
                    <div style="margin-top:6px; display:flex; align-items:baseline; flex-wrap:wrap; gap:4px;">
                        <span style="color:#ef4444; font-size:18px; font-weight:800;">¥{cur_p}</span>
                        <span style="color:#94a3b8; font-size:11px; text-decoration:line-through; margin-left:4px;">原高位: ¥{high_p}</span>
                        <span style="display:inline-block; padding:2px 6px; font-size:11px; background:#fee2e2; color:#dc2626; border-radius:6px; font-weight:bold; margin-left:4px;">🔻降 {drop_pct}% (-¥{drop_abs})</span>
                        {deal_badge}
                    </div>
                </div>
            </div>
            <div style="margin-top:10px; text-align:right;">
                <a href="{bili_url}" target="_blank" style="display:inline-block; padding:8px 18px; background:linear-gradient(135deg, #fb7299, #f43f5e); color:#ffffff; font-size:12px; font-weight:bold; text-decoration:none; border-radius:8px; box-shadow:0 2px 8px rgba(251,114,153,0.35);">
                    📱 手机点击一键直达 B站 抢购 ➔
                </a>
            </div>
        </div>
        """)

    all_items_str = "\n".join(items_html)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:16px; background-color:#f8fafc; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <div style="max-width:560px; margin:0 auto;">
        <!-- Header -->
        <div style="background:linear-gradient(135deg, #fb7299, #e11d48); padding:20px; border-radius:18px; color:#ffffff; margin-bottom:14px; box-shadow:0 6px 16px rgba(251,114,153,0.25);">
            <div style="font-size:12px; font-weight:600; opacity:0.9; text-transform:uppercase; letter-spacing:0.5px;">B站会员购 · 转售行情监控</div>
            <h1 style="margin:4px 0 0 0; font-size:20px; font-weight:bold;">{title}</h1>
            <div style="margin-top:6px; font-size:12px; opacity:0.92;">⏰ {sub}</div>
        </div>

        <!-- Items -->
        {all_items_str}

        <!-- Footer -->
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:14px; text-align:center; color:#64748b; font-size:12px; line-height:1.6; margin-top:14px;">
            <p style="margin:0; font-weight:600; color:#334155;">💡 手机端使用提示：</p>
            <p style="margin:4px 0 0 0;">在手机上点击任意商品卡片的<b>「直达抢购」</b>粉色按钮，即可直接在手机浏览器或 B站 App 中打开商品购买，无需在电脑旁！</p>
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

    # 如果未提供专门的 HTML，则生成默认的移动端排版
    if not html_content:
        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #fb7299, #f43f5e); padding: 20px; color: #ffffff;">
                <h2 style="margin: 0; font-size: 18px; font-weight: bold;">{title}</h2>
            </div>
            <div style="padding: 20px; color: #334155; line-height: 1.6; font-size: 14px;">
                <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; background: #f8fafc; padding: 14px; border-radius: 10px; color: #1e293b;">{content_markdown}</pre>
            </div>
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
        # 使用 SSL 协议连接 QQ 邮箱服务器 (端口 465)
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


def send_test_message(config=None):
    """发送测试消息（包含真实的B站移动端直达链接卡片预览）。"""
    if config is None:
        config = load_notify_config()

    channel = config.get("channel", "qq_email")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    sample_alerts = [
        {
            "cluster_id": "10000000603",
            "title": "【示例】FEELALL 星空旋律 鼠标垫 凪款 (测试商品)",
            "cur_price": 9.00,
            "high_price": 30.00,
            "drop_abs": 21.00,
            "drop_pct": 70.0,
            "latest_deal_price": "¥8.92",
            "img": "https://i0.hdslb.com/bfs/mall/mall/60/0a/600ae099b24479e0a6d0cbf06689d0c2.png",
            "url": "https://mall.bilibili.com/neul-next/resell/detail.html?clusterId=10000000603"
        }
    ]

    title = "🔔【B站转售监控 · 微信消息推送测试】"
    md = f"""【B站转售监控 · 微信消息推送测试】
--------------------------------------------
✅ 状态：已成功连通！
⏰ 时间：{now_str}
📱 说明：以后巡检发现降价捡漏时，邮件内会直接附带【商品图片、底价、降价幅度与 B站手机直达抢购链接】，在手机微信中点击即可直接购买，无需打开电脑！

示例商品：
1. FEELALL 星空旋律 鼠标垫 凪款
   底价: ¥9.00 (原高位: ¥30.00 | 降 70.0% | 最近成交: ¥8.92)
   🔗 抢购链接: https://mall.bilibili.com/neul-next/resell/detail.html?clusterId=10000000603
"""
    html = build_mobile_email_html(sample_alerts, "🔔 微信推送联调测试成功！", f"测试时间：{now_str} · 手机直接点击下方按钮即可打开B站抢购")
    return send_unified_message(channel, title, md, config, html_content=html)


def format_alerts_markdown(alerts, total_items_count=None):
    """将捡漏列表格式化为文本/Markdown消息（带B站直达链接）。"""
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

    for idx, a in enumerate(alerts[:8], 1):
        title = a.get("title", "未命名商品")
        cur_p = a.get("cur_price")
        high_p = a.get("high_price")
        drop_pct = a.get("drop_pct")
        drop_abs = a.get("drop_abs")
        raw_url = a.get("url") or f"https://mall.bilibili.com/neul-next/resell/detail.html?clusterId={a.get('cluster_id')}"
        bili_url = ensure_https_url(raw_url)
        latest_deal = a.get("latest_deal_price", "")
        deal_str = f" (最近成交: {latest_deal})" if latest_deal else ""

        lines.append(f"{idx}. {title}")
        lines.append(f"   🔻 降幅：降 {drop_pct}% (-¥{drop_abs})")
        lines.append(f"   💰 底价：¥{cur_p} (原高位: ¥{high_p}{deal_str})")
        lines.append(f"   🔗 B站直达抢购：{bili_url}")
        lines.append("")

    if len(alerts) > 8:
        lines.append(f"... 及其他 {len(alerts) - 8} 件降价商品。")

    lines.append("--------------------------------------------")
    lines.append("💡 点击上方任意商品直达链接即可在手机直接打开 B站 购买！")
    return "\n".join(lines)


def process_and_send_alerts(alerts, total_items_count=None, force=False):
    """检查新出现的捡漏商品并执行移动端优化推送（带去重机制与B站直达链接）。"""
    cfg = load_notify_config()
    if not cfg.get("enabled"):
        return False, "推送功能未开启"

    channel = cfg.get("channel", "qq_email")
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

    # 3. 构造移动端富文本消息并发送
    title = f"⚡【B站转售 · 发现 {len(new_alerts_to_push)} 件新降价捡漏！】"
    md_content = format_alerts_markdown(new_alerts_to_push, total_items_count)
    html_content = build_mobile_email_html(new_alerts_to_push, title)

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
