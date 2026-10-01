#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv6 地址变化检测与 DDNS 更新。

用法:
    python ddns_update.py            # 检测；地址变化则更新 dynv6 并推送通知
    python ddns_update.py --force    # 强制更新一次（忽略是否变化）
    python ddns_update.py --show     # 只打印当前对外 IPv6 地址

配置（二选一）:
    1) 项目根目录 ddns.conf（已被 .gitignore 忽略）:
         DDNS_ZONE=xxx.dynv6.net
         DDNS_TOKEN=xxxxxxxxxxxxxxxx
    2) 环境变量 DDNS_ZONE / DDNS_TOKEN

未配置 dynv6 时依然有用：IPv6 一旦变化，就用项目已有的推送通道
（企业微信 / WxPusher / QQ邮箱 / Bark / Server酱）把新地址发到手机，
相当于零成本自建 DDNS。
"""
import argparse
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
    """读取 dynv6 配置：环境变量优先，其次 ddns.conf。"""
    zone = os.environ.get("DDNS_ZONE", "").strip()
    token = os.environ.get("DDNS_TOKEN", "").strip()
    if os.path.exists(CONF_PATH):
        try:
            with open(CONF_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip().lower(), v.strip()
                    if k == "ddns_zone" and not zone:
                        zone = v
                    elif k == "ddns_token" and not token:
                        token = v
        except OSError as e:
            print(f"[Warn] 读取 {CONF_PATH} 失败: {e}")
    return zone, token


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


def notify(addr, zone=""):
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
    text = (
        "### 家里看板地址已更新\n\n"
        f"- 直连：**http://[{addr}]:{PORT}**\n"
        f"- 域名：{zone or '（未配置 dynv6）'}\n"
        f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
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

    zone, token = load_conf()
    last = read_last()
    print(f"[Info] 当前 IPv6: {addr}（上次: {last or '无记录'}）")

    if addr == last and not args.force:
        print("[Info] 地址未变化，无需更新")
        return 0

    ok, msg = update_dynv6(zone, token, addr)
    print(f"[DDNS] {msg}")

    write_last(addr)
    notify(addr, zone if ok else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
