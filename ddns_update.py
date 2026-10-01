#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv6 地址变化检测与 DDNS 更新。

用法:
    python ddns_update.py            # 检测；地址变化则更新 DDNS 并推送通知
    python ddns_update.py --force    # 强制更新一次（忽略是否变化）
    python ddns_update.py --show     # 只打印当前对外 IPv6 地址

配置（二选一）:
    1) 项目根目录 ddns.conf（已被 .gitignore 忽略）:
         DDNS_PROVIDER=noip
         DDNS_HOST=your-host.ddns.net
         DDNS_USER=<DDNS Key 用户名>
         DDNS_TOKEN=<DDNS Key 密码>
    2) 同名环境变量（优先级更高）

支持的服务商:
    noip    No-IP（默认）。国内可达、域名可解析，免费版每 30 天需在邮件里点一次确认。
    dynv6   已停用——其全部免费后缀（dns.army / v6.army / dynv6.net / v6.rocks 等）
            在国内 DNS 上均为 NXDOMAIN，手机无法解析。代码保留备用。

未配置任何服务商时依然有用：IPv6 一旦变化，就用项目已有的推送通道
（企业微信 / WxPusher / QQ邮箱 / Bark / Server酱）把新地址发到手机，
相当于零成本自建 DDNS。
"""
import argparse
import base64
import os
import socket
import sys
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(BASE_DIR, "ddns.conf")
STATE_PATH = os.path.join(BASE_DIR, ".last_ipv6")

# 用于探测出网源地址的公网 DNS；UDP connect 不实际发包
PROBE_TARGET = ("2001:4860:4860::8888", 53)

PORT = 8000


def load_conf():
    """读取 DDNS 配置：环境变量优先，其次 ddns.conf。

    返回 dict: {provider, host, user, token}
    为兼容早期只看 dynv6 的配置，`DDNS_ZONE` 会被当作 `DDNS_HOST`。
    """
    cfg = {
        "provider": os.environ.get("DDNS_PROVIDER", "").strip().lower(),
        "host": os.environ.get("DDNS_HOST", "").strip(),
        "user": os.environ.get("DDNS_USER", "").strip(),
        "token": os.environ.get("DDNS_TOKEN", "").strip(),
    }
    aliases = {
        "ddns_provider": "provider",
        "ddns_host": "host",
        "ddns_hostname": "host",
        "ddns_zone": "host",
        "ddns_user": "user",
        "ddns_login": "user",
        "ddns_token": "token",
        "ddns_password": "token",
    }
    if os.path.exists(CONF_PATH):
        try:
            with open(CONF_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    key = aliases.get(k.strip().lower())
                    if key and not cfg[key]:
                        cfg[key] = v.strip()
        except OSError as e:
            print(f"[Warn] 读取 {CONF_PATH} 失败: {e}")
    if not cfg["provider"]:
        # 旧配置只有 DDNS_ZONE，用后缀反推服务商
        host = cfg["host"].lower()
        cfg["provider"] = "dynv6" if host.endswith(
            ("dynv6.net", "dns.army", "v6.army", "dns.navy", "v6.navy", "v6.rocks")
        ) else "noip"
    return cfg


def get_global_ipv6():
    """返回本机对外通信使用的全局 IPv6 地址。"""
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.connect(PROBE_TARGET)
        addr = s.getsockname()[0]
        s.close()
        return addr
    except OSError as e:
        print(f"[Error] 未能获取 IPv6 地址: {e}")
        return None


def read_last():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def write_last(addr):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            f.write(addr)
    except OSError as e:
        print(f"[Warn] 保存地址失败: {e}")


def update_dynv6(zone, token, addr):
    """更新 dynv6 的 AAAA 记录，返回 (ok, msg)。"""
    if not zone or not token:
        return False, "未配置 DDNS_ZONE / DDNS_TOKEN，跳过 dynv6 更新"
    qs = urllib.parse.urlencode({"zone": zone, "token": token, "ipv6": addr})
    req = urllib.request.Request(
        f"https://dynv6.com/api/update?{qs}",
        headers={"User-Agent": "bili-monitor-ddns/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
        return True, f"dynv6 已更新: {body[:120]}"
    except Exception as e:
        return False, f"dynv6 更新失败: {e}"


# No-IP 要求请求携带合规的 User-Agent，否则客户端可能被限流或封禁
NOIP_ENDPOINT = "https://dynupdate.no-ip.com/nic/update"
NOIP_UA = "BiliMonitor DdnsUpdate/1.0 Win10 zhou2228653446@users.noreply.github.com"

# No-IP 的失败返回码含义
NOIP_HINTS = {
    "nohost": "域名不存在或不属于该账号",
    "badauth": "DDNS Key 用户名/密码错误",
    "badagent": "客户端被禁用（User-Agent 不合规）",
    "abuse": "账号被风控暂停",
}


def update_noip(host, user, token, addr):
    """更新 No-IP 的 AAAA 记录，返回 (ok, msg)。

    只传 myip=<IPv6>，因此只写 AAAA 记录，不会触发 IPv4 自动探测
    （本机 IPv4 入站不通，多一条 A 记录只会拖慢客户端）。
    """
    if not (host and user and token):
        return False, "未配置 DDNS_HOST / DDNS_USER / DDNS_TOKEN，跳过 No-IP 更新"
    auth = base64.b64encode(f"{user}:{token}".encode()).decode()
    qs = urllib.parse.urlencode({"hostname": host, "myip": addr})
    req = urllib.request.Request(
        f"{NOIP_ENDPOINT}?{qs}",
        headers={"Authorization": f"Basic {auth}", "User-Agent": NOIP_UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
    except Exception as e:
        return False, f"No-IP 更新失败: {e}"
    head = body.split()[0] if body else ""
    if head in ("good", "nochg"):
        return True, f"No-IP 已更新: {body[:120]}"
    hint = NOIP_HINTS.get(head)
    return False, f"No-IP 更新失败: {body[:120]}{'（' + hint + '）' if hint else ''}"


def update_ddns(cfg, addr):
    """按 provider 分派更新请求，返回 (ok, msg)。"""
    if cfg["provider"] == "dynv6":
        return update_dynv6(cfg["host"], cfg["token"], addr)
    return update_noip(cfg["host"], cfg["user"], cfg["token"], addr)


def notify(addr, host=""):
    """借项目已有推送通道把新地址发到手机。"""
    try:
        import notifier
    except Exception as e:
        print(f"[Warn] 推送模块不可用: {e}")
        return
    cfg = notifier.load_notify_config()
    if not cfg.get("enabled"):
        print("[Info] 推送未开启，未发送通知（可在看板「推送设置」中开启）")
        return
    lines = ["### 家里看板地址已更新", ""]
    if host:
        lines.append(f"- 固定域名：**http://{host}:{PORT}/**")
    lines.append(f"- 直连地址：**http://[{addr}]:{PORT}/**")
    lines.append(f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    if host:
        lines += ["", "域名记录已自动更新，书签不用改。"]
    text = "\n".join(lines) + "\n"
    ok, msg = notifier.send_unified_message(
        cfg.get("channel", ""), "看板地址变更", text, cfg
    )
    print(f"[Notify] {'已发送' if ok else '发送失败'}: {msg}")


def main():
    ap = argparse.ArgumentParser(description="IPv6 地址变化检测与 DDNS 更新")
    ap.add_argument("--force", action="store_true", help="即使地址未变化也更新一次")
    ap.add_argument("--show", action="store_true", help="只打印当前 IPv6 地址")
    args = ap.parse_args()

    addr = get_global_ipv6()
    if not addr:
        return 1

    if args.show:
        print(addr)
        return 0

    cfg = load_conf()
    last = read_last()
    print(f"[Info] 服务商: {cfg['provider']}  当前 IPv6: {addr}（上次: {last or '无记录'}）")

    if addr == last and not args.force:
        print("[Info] 地址未变化，无需更新")
        return 0

    ok, msg = update_ddns(cfg, addr)
    print(f"[DDNS] {msg}")

    write_last(addr)
    notify(addr, cfg["host"] if ok else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
