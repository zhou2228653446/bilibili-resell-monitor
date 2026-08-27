#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 消息推送模块 (Notifier)
支持 100% 永久免费的个人微信及手机推送通道：
1. 💌 QQ邮箱 -> 微信实时弹窗提醒 (100% 腾讯官方、永久免费、零限制、最推荐)
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


# ==================== 1. QQ邮箱 -> 微信即时通知 (100% 永久免费) ====================
def send_qq_email(sender_email, auth_code, receiver_email, title, content_markdown):
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

    # 构造 HTML 邮件内容
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="background: linear-gradient(135deg, #fb7299, #f43f5e); padding: 20px 24px; color: #ffffff;">
            <h2 style="margin: 0; font-size: 18px; font-weight: bold;">🛒 B站转售监控 · 降价捡漏提醒</h2>
            <p style="margin: 6px 0 0 0; font-size: 12px; opacity: 0.9;">自动巡检发现超值降价商品，请及时查阅！</p>
        </div>
        <div style="padding: 24px; color: #334155; line-height: 1.6; font-size: 14px;">
            <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; background: #f8fafc; padding: 16px; border-radius: 12px; border: 1px solid #f1f5f9; color: #1e293b;">{content_markdown}</pre>
        </div>
        <div style="padding: 16px 24px; background: #f8fafc; border-top: 1px solid #f1f5f9; text-align: center;">
            <a href="http://localhost:8000" style="display: inline-block; padding: 10px 24px; background: #fb7299; color: #ffffff; text-decoration: none; border-radius: 9999px; font-weight: bold; font-size: 13px;">打开本地监控大盘</a>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = Header(f"B站捡漏监控 <{sender}>", "utf-8")
    msg["To"] = Header(receiver, "utf-8")

    part1 = MIMEText(content_markdown, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")
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
        "contentType": 3,  # 3 代表 Markdown 格式
        "uids": [uid],
        "url": "http://localhost:8000"
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
        "url": "http://localhost:8000"
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
def send_unified_message(channel, title, markdown_text, config):
    """统一向指定渠道分发消息。"""
    if channel == "qq_email":
        return send_qq_email(
            config.get("qq_email", ""),
            config.get("qq_smtp_code", ""),
            config.get("receiver_email", ""),
            title,
            markdown_text
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
        # 兼容 Server酱
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
        # 兼容企微
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
    """发送测试消息以验证连通性。"""
    if config is None:
        config = load_notify_config()

    channel = config.get("channel", "qq_email")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    channel_name = {
        "qq_email": "QQ 邮箱 -> 微信实时弹窗提醒 (100% 永久免费)",
        "wxpusher": "WxPusher 微信消息推送 (完全免费)",
        "bark": "iOS Bark 原生横幅推送",
        "serverchan": "Server酱 Turbo",
        "wecom": "企业微信群机器人"
    }.get(channel, channel)

    title = "🔔【B站转售监控 · 微信消息推送联调测试】"
    md = f"""【B站转售监控 · 消息推送测试】
--------------------------------------------
📱 推送通道：{channel_name}
✅ 连接状态：连通正常，测试成功！
⏰ 发送时间：{now_str}
💡 监控说明：后续自动巡检中若发现降价捡漏商品，将自动发送至本窗口。

👉 本地大盘链接: http://localhost:8000
"""
    return send_unified_message(channel, title, md, config)


def format_alerts_markdown(alerts, total_items_count=None):
    """将捡漏列表格式化为 Markdown / 文本消息。"""
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
        url = a.get("url", "#")
        latest_deal = a.get("latest_deal_price", "")
        deal_str = f" (最近成交: {latest_deal})" if latest_deal else ""

        lines.append(f"{idx}. {title}")
        lines.append(f"   🔻 降幅：降 {drop_pct}% (-¥{drop_abs})")
        lines.append(f"   💰 底价：¥{cur_p} (原高位: ¥{high_p}{deal_str})")
        lines.append(f"   🔗 抢购链接：{url}")
        lines.append("")

    if len(alerts) > 8:
        lines.append(f"... 及其他 {len(alerts) - 8} 件降价商品，请前往大盘查看。")

    lines.append("--------------------------------------------")
    lines.append("👉 打开本地监控大盘: http://localhost:8000")
    return "\n".join(lines)


def process_and_send_alerts(alerts, total_items_count=None, force=False):
    """检查新出现的捡漏商品并执行推送（带去重机制）。"""
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

    # 3. 构造消息并发送
    title = f"⚡【B站转售 · 发现 {len(new_alerts_to_push)} 件新降价捡漏！】"
    md_content = format_alerts_markdown(new_alerts_to_push, total_items_count)
    ok, msg = send_unified_message(channel, title, md_content, cfg)
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
