#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据冷备份：把不可重建的业务数据打包到另一块分区。

备份对象里只有 3c_products_history.csv 是真正无法重建的——它是几十天积累的
价格轨迹，丢了只能从头重新采集。其余文件要么能重新抓取，要么在 GitHub 上有。

用法：
    python backup_data.py                # 备份到默认目录 E:\\bili-backup
    python backup_data.py --dir X:\\bak  # 指定备份目录
    python backup_data.py --keep 30      # 保留最近 30 份
    python backup_data.py --list         # 只列出现有备份，不执行
"""

import argparse
import os
import sys
import time
import zipfile

# 备份目录：优先环境变量，其次 E 盘（机械盘上未被傲腾加速的另一个分区）
DEFAULT_DIR = os.environ.get("BILI_BACKUP_DIR", r"E:\bili-backup")

# 要备份的文件 -> (是否核心)。核心文件丢失无法重建。
TARGETS = [
    ("3c_products_history.csv", True),   # 价格轨迹，唯一不可重建的数据
    ("3c_products.json", False),         # 最新快照，重新抓取即得
    ("3c_products.csv", False),
    ("deals_cache.json", False),         # 市集成交缓存，会自行重建
    ("pushed_alerts.json", False),       # 告警去重记录，丢了最多重复推一次
    ("notify_config.json", False),       # 推送渠道配置（含密钥）
    ("auth.conf", False),                # 访问口令
]

KEEP_DEFAULT = 14


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def list_backups(backup_dir):
    if not os.path.isdir(backup_dir):
        return []
    out = []
    for name in os.listdir(backup_dir):
        if name.startswith("bili-data-") and name.endswith(".zip"):
            p = os.path.join(backup_dir, name)
            out.append((name, os.path.getsize(p), os.path.getmtime(p)))
    return sorted(out, key=lambda x: x[2], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="B站转售监控 数据冷备份")
    parser.add_argument("--dir", default=DEFAULT_DIR, help=f"备份目录（默认 {DEFAULT_DIR}）")
    parser.add_argument("--keep", type=int, default=KEEP_DEFAULT, help=f"保留最近几份（默认 {KEEP_DEFAULT}）")
    parser.add_argument("--list", action="store_true", help="只列出现有备份")
    args = parser.parse_args()

    backup_dir = args.dir
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.list:
        items = list_backups(backup_dir)
        if not items:
            print(f"备份目录为空: {backup_dir}")
            return 0
        print(f"备份目录: {backup_dir}")
        for name, size, mtime in items:
            print(f"  {name}  {human(size):>10}  {time.strftime('%Y-%m-%d %H:%M', time.localtime(mtime))}")
        return 0

    src_files = [(n, os.path.join(base_dir, n)) for n, _ in TARGETS]
    existing = [(n, p) for n, p in src_files if os.path.exists(p)]
    missing = [n for n, p in src_files if not os.path.exists(p)]
    if not existing:
        print("[错误] 没有任何可备份的文件，检查当前目录是否正确。")
        return 1

    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(backup_dir, f"bili-data-{stamp}.zip")

    total_raw = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name, path in existing:
            total_raw += os.path.getsize(path)
            zf.write(path, arcname=name)
            print(f"  + {name}  ({human(os.path.getsize(path))})")

    zipped = os.path.getsize(zip_path)
    ratio = (1 - zipped / total_raw) * 100 if total_raw else 0
    print(f"\n备份完成: {zip_path}")
    print(f"  原始 {human(total_raw)} -> 压缩后 {human(zipped)} (省 {ratio:.0f}%)")
    if missing:
        print(f"  跳过（不存在）: {', '.join(missing)}")

    # 轮转：只保留最近 keep 份
    items = list_backups(backup_dir)
    for name, _, _ in items[args.keep:]:
        try:
            os.remove(os.path.join(backup_dir, name))
            print(f"  已清理旧备份: {name}")
        except OSError as e:
            print(f"  [警告] 清理失败 {name}: {e}")

    print(f"\n当前保留 {min(len(items), args.keep)} 份，目录 {backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
