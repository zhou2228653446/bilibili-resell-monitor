#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
哔哩哔哩会员购「潮玩闲置 / 转售」首页商品信息抓取脚本
URL: https://mall.bilibili.com/neul-next/resell/home.html?noTitleBar=1

该页面是 SPA，数据通过以下接口加载（均无需登录）：
  POST https://mall.bilibili.com/mall-c-search/resell/home    首页（含首屏商品 + 筛选维度）
  POST https://mall.bilibili.com/mall-c-search/resell/feed    分页商品流

仅依赖 Python 标准库（urllib / json / argparse），无需 pip install。
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

# 解决 Windows 控制台默认 GBK 编码导致输出特殊字符/日文/Emoji 抛 UnicodeEncodeError 问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://mall.bilibili.com/mall-c-search"
REFERER = "https://mall.bilibili.com/neul-next/resell/home.html?noTitleBar=1"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": USER_AGENT,
    "Referer": REFERER,
    "Origin": "https://mall.bilibili.com",
}


def init_session_cookies():
    """获取 B 站前端设备指纹 (buvid3 / buvid4) 并注入请求头，降低被风控限流概率。"""
    finger_url = "https://api.bilibili.com/x/frontend/finger/spi"
    req = urllib.request.Request(
        finger_url,
        headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            b3 = data.get("data", {}).get("b_3", "")
            b4 = data.get("data", {}).get("b_4", "")
            if b3 or b4:
                HEADERS["Cookie"] = f"buvid3={b3}; buvid4={b4};"
    except Exception:
        # 静默降级，不阻塞主流程
        pass


def api_post(path, body, retries=5):
    """调用接口并返回 data 字段；支持 HTTP 429 自动指数退避重试；接口返回 success=false 时抛异常。"""
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8")
    
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            
            if not payload.get("success"):
                raise RuntimeError(f"接口返回失败: {payload.get('message', '未知错误')}")
            return payload.get("data", {})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = attempt * 2.5 + random.uniform(1.0, 2.0)
                print(f"\n  [触发 429 频率限制] 正在退避等待 {wait:.1f} 秒后重试 (第 {attempt}/{retries} 次)...", file=sys.stderr, flush=True)
                time.sleep(wait)
                last_err = RuntimeError(f"HTTP 错误 429: 触发频率限制 ({url})")
            else:
                last_err = RuntimeError(f"HTTP 错误 {e.code}: {e.reason} ({url})")
                if attempt < retries:
                    time.sleep(1.5)
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"网络错误: {e.reason} ({url})")
            if attempt < retries:
                time.sleep(2.0)
        except RuntimeError as e:
            raise e
        except Exception as e:
            last_err = RuntimeError(f"请求异常: {e} ({url})")
            if attempt < retries:
                time.sleep(1.5)

    raise last_err if last_err else RuntimeError("未知错误")


def get_home():
    """获取首页：页头、限时大漏、筛选维度、首屏商品流。"""
    return api_post("/resell/home", {})


def get_feed(page_num=1, page_size=20, sort_type=None,
             category_id=None, ip_id=None):
    """分页获取商品流。"""
    filters = {}
    if category_id:
        filters["productCategory"] = category_id
    if ip_id:
        filters["ipId"] = ip_id
    body = {
        "pageNum": page_num,
        "pageSize": page_size,
        "sortType": sort_type or "hot",
        "filters": filters,
    }
    return api_post("/resell/feed", body)


def get_feed_safe(page_num=1, sort_type=None, category_id=None, ip_id=None,
                  retries=5):
    """带重试的分页请求：调用 api_post（内部已具备 429 退避和重试）。"""
    return get_feed(page_num=page_num, sort_type=sort_type,
                    category_id=category_id, ip_id=ip_id)


def get_cluster_info(cluster_id):
    """获取单个商品的市集详情与真实成交记录（官方成交均价走势与近期交易明细）。"""
    url = "https://mall.bilibili.com/mall-search-items/items_detail/cluster_info"
    data = json.dumps({"clusterId": str(cluster_id)}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("code") == 0:
                d = payload.get("data", {})
                basic = d.get("clusterBasicInfoFloorVO") or {}
                price_floor = d.get("clusterPriceFloorVO") or {}
                recent_buy = d.get("clusterRecentBuyFloorVO") or {}
                attr_floor = d.get("clusterAttrFloorVO") or {}
                header_floor = d.get("clusterHeaderFloorVO") or {}
                btn_floor = d.get("clusterPurchaseButton") or {}

                chart_points = recent_buy.get("chartData", {}).get("chartPoints", []) if recent_buy.get("chartData") else []
                deals = recent_buy.get("deals", [])

                latest_deal_price = None
                if deals and len(deals) > 0 and deals[0].get("dealPrice"):
                    latest_deal_price = str(deals[0].get("dealPrice"))
                elif chart_points and len(chart_points) > 0:
                    last_pt = chart_points[-1]
                    p_val = last_pt.get("avgPrice") or last_pt.get("price")
                    if p_val:
                        p_val_str = str(p_val).strip()
                        latest_deal_price = p_val_str if p_val_str.startswith("¥") else f"¥{p_val_str}"

                return {
                    "cluster_id": str(cluster_id),
                    "title": basic.get("clusterName", ""),
                    "images": header_floor.get("clusterImgList", []),
                    "price_tag": price_floor.get("priceTag", {}),
                    "lowest_price": btn_floor.get("buttonSubText", ""),
                    "latest_deal_price": latest_deal_price,
                    "attributes": attr_floor.get("attrList", []),
                    "chart_points": chart_points,
                    "deals": deals,
                }
    except Exception as e:
        print(f"[Warn] 获取商品市集成交信息失败 ({cluster_id}): {e}", file=sys.stderr)
    return None


def normalize_item(item):
    """将接口返回的单条商品统一成易读字段。"""
    price_tags = "、".join(t.get("text", "") for t in item.get("priceTags", []) if t.get("text"))
    popularity = "、".join(t.get("text", "") for t in item.get("popularityTags", []) if t.get("text"))
    symbol = item.get("currencySymbol", "¥")
    return {
        "cluster_id": item.get("id", ""),
        "title": item.get("title", "") or "（未命名/限时大漏）",
        "price": f"{symbol}{item.get('price', '')}",
        "reference_price": (f"{symbol}{item['referencePrice']}"
                            if item.get("referencePrice") else ""),
        "discount": price_tags,
        "popularity": popularity,
        "img": "https:" + item["img"] if item.get("img", "").startswith("//") else item.get("img", ""),
        "url": item.get("url", ""),
    }


def print_overview(home):
    """打印首页概览信息。"""
    header = home.get("header", {})
    right = header.get("rightEntry", {})
    print("=" * 60)
    print("【页面概览】")
    if header.get("titleImg"):
        print(f"  标题图: {header.get('titleImg')}")
    if right.get("text"):
        print(f"  入口: {right.get('text')} -> {right.get('jumpUrl')}")

    floor = home.get("discountFloor", {})
    items = floor.get("items", [])
    if items:
        print(f"\n【{floor.get('title', '限时大漏')}】{floor.get('subTitle', '')}")
        for it in items:
            n = normalize_item(it)
            line = f"  - {n['title']}  {n['price']}"
            if n["reference_price"]:
                line += f" (原价 {n['reference_price']})"
            if n["discount"]:
                line += f"  [{n['discount']}]"
            print(line)

    fb = home.get("filterBar", {})
    sorts = fb.get("sortTypes", [])
    cats = fb.get("quickCategories", [])
    ips = fb.get("quickIp", [])
    if sorts:
        print("\n【排序方式】 " + " / ".join(
            f"{s.get('name')}({s.get('type')})" for s in sorts))
    if cats:
        print(f"【商品分类】 共 {len(cats)} 个，如: " + "、".join(
            f"{c.get('name')}({c.get('id')})" for c in cats[:6]) + " ...")
    if ips:
        print(f"【IP 分区】 共 {len(ips)} 个，如: " + "、".join(
            f"{c.get('name')}({c.get('id')})" for c in ips[:6]) + " ...")


def print_items(items, start_no=1):
    """以表格形式打印商品列表。"""
    print("-" * 60)
    for i, it in enumerate(items, start=start_no):
        n = normalize_item(it)
        print(f"{i:>3}. {n['title']}")
        price_line = f"     价格: {n['price']}"
        if n["reference_price"]:
            price_line += f"   原价: {n['reference_price']}"
        print(price_line)
        extra = []
        if n["discount"]:
            extra.append(f"标签:{n['discount']}")
        if n["popularity"]:
            extra.append(f"热度:{n['popularity']}")
        if extra:
            print("     " + "  ".join(extra))
        print(f"     链接: {n['url']}")


def export_csv(items, path):
    """将原始商品列表导出为 CSV 快照（带 BOM，Excel 中文不乱码）。"""
    cols = ["cluster_id", "title", "price", "reference_price",
            "discount", "popularity", "img", "url"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for it in items:
            writer.writerow(normalize_item(it))


HISTORY_COLS = ["crawl_time", "category", "cluster_id", "title", "price",
                "reference_price", "discount", "popularity", "img", "url"]


def parse_price(s):
    """从 '¥59' / '¥1,299.00' 之类的字符串解析出数值。"""
    if not s:
        return None
    nums = re.findall(r"\d+\.?\d*", s.replace(",", ""))
    if not nums:
        return None
    try:
        return float(nums[0])
    except ValueError:
        return None


def fmt_money(v):
    return f"¥{v:.2f}" if isinstance(v, (int, float)) else (v or "")


def append_history(items, path, category, crawl_time):
    """将本次抓取结果追加写入历史 CSV（长表：每行一条商品 + 抓取时间）。"""
    existed = os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLS)
        if not existed:
            writer.writeheader()
        cat = category if category else "all"
        for it in items:
            n = normalize_item(it)
            writer.writerow({
                "crawl_time": crawl_time,
                "category": cat,
                "cluster_id": n["cluster_id"],
                "title": n["title"],
                "price": n["price"],
                "reference_price": n["reference_price"],
                "discount": n["discount"],
                "popularity": n["popularity"],
                "img": n["img"],
                "url": n["url"],
            })


def read_history(path):
    """读取历史 CSV，返回 (rows, 全部抓取时间点列表)。"""
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    times = sorted({r["crawl_time"] for r in rows})
    return rows, times


def print_trend(history_path, category, current_time=None):
    """对比最近两次抓取的价格走势（按 cluster_id 匹配）。"""
    rows, _ = read_history(history_path)
    if not rows:
        print("历史文件中没有数据，无法对比。先正常跑一次抓取即可生成历史。")
        return
    cat = category if category else "all"
    cat_rows = [r for r in rows if r.get("category") == cat]
    if not cat_rows:
        print(f"历史文件中没有分类={cat} 的数据。")
        return
    cat_times = sorted({r["crawl_time"] for r in cat_rows})
    if current_time and current_time in cat_times:
        idx = cat_times.index(current_time)
        if idx == 0:
            print(f"分类={cat} 的首次抓取记录于 {current_time}，已作为基线保存；下次抓取后可对比走势。")
            return
        cur_t, prev_t = cat_times[idx], cat_times[idx - 1]
    else:
        if len(cat_times) < 2:
            print(f"分类={cat} 目前仅 {len(cat_times)} 次抓取记录，已保存基线；再次抓取后即可对比走势。")
            return
        cur_t, prev_t = cat_times[-1], cat_times[-2]

    def price_map(t):
        return {r["cluster_id"]: r for r in cat_rows if r["crawl_time"] == t}

    cur, prev = price_map(cur_t), price_map(prev_t)
    print("\n" + "=" * 60)
    print(f"【价格走势对比】 分类={cat}")
    print(f"  本次: {cur_t}")
    print(f"  上次: {prev_t}")

    up = []      # (title, prev, cur, delta>0)
    down = []    # (title, prev, cur, delta<0)
    same = 0
    new = []     # (title, price)
    gone = []    # (title, price)
    for iid, r in cur.items():
        p = parse_price(r["price"])
        if iid in prev:
            pp = parse_price(prev[iid]["price"])
            if p is not None and pp is not None:
                d = p - pp
                if d > 0:
                    up.append((r["title"], pp, p, d))
                elif d < 0:
                    down.append((r["title"], pp, p, d))
                else:
                    same += 1
            else:
                same += 1
        else:
            new.append((r["title"], p))
    for iid, r in prev.items():
        if iid not in cur:
            gone.append((r["title"], parse_price(r["price"])))

    print(f"\n  价格上升 ▲: {len(up)} 个")
    for t, a, b, d in sorted(up, key=lambda x: -x[3])[:15]:
        print(f"    ▲ {t}  {fmt_money(a)} → {fmt_money(b)}  (+{d:.2f})")
    print(f"\n  价格下降 ▼: {len(down)} 个")
    for t, a, b, d in sorted(down, key=lambda x: x[3])[:15]:
        print(f"    ▼ {t}  {fmt_money(a)} → {fmt_money(b)}  ({d:.2f})")
    print(f"\n  价格不变: {same} 个")
    print(f"  本次新增上架 ＋: {len(new)} 个")
    for t, p in new[:15]:
        print(f"    ＋ {t}  {fmt_money(p)}")
    print(f"  本次下架/消失 －: {len(gone)} 个")
    for t, p in gone[:15]:
        print(f"    － {t}  {fmt_money(p)}")


def detect_price_alerts(history_path, category, current_time=None,
                        prev_n=3, abs_th=10.0, pct_th=0.10):
    """检测价格异动：对比本次抓取与「前 prev_n 次」的高位价格。

    对每个出现在本次抓取中的商品，取前 prev_n 次抓取里的最高价作为基准「高位」，
    若本次价格低于该高位，且 (高位 - 本次) > abs_th 元 或 (高位 - 本次)/高位 > pct_th，
    则判定为「降价异动」并标记。
    返回 dict: {"alerts":[...], "current_time", "prev_times":[...], "baseline_count"}，
    无历史或数据不足时返回 None。
    """
    rows, _ = read_history(history_path)
    if not rows:
        return None
    cat = category if category else "all"
    cat_rows = [r for r in rows if r.get("category") == cat]
    if not cat_rows:
        return None
    cat_times = sorted({r["crawl_time"] for r in cat_rows})
    if current_time and current_time in cat_times:
        idx = cat_times.index(current_time)
    else:
        idx = len(cat_times) - 1
        current_time = cat_times[idx]
    if idx < 1:
        return {"alerts": [], "current_time": current_time,
                "prev_times": [], "baseline_count": 0}
    # 前 prev_n 次（不含本次）作为基准窗口
    prev_times = cat_times[max(0, idx - prev_n):idx]
    if not prev_times:
        return {"alerts": [], "current_time": current_time,
                "prev_times": [], "baseline_count": 0}

    cur_map = {r["cluster_id"]: r for r in cat_rows
               if r["crawl_time"] == current_time}
    # 建立 (时间, cluster_id) -> row，便于快速取前 n 次价格
    prev_rows = {}
    for r in cat_rows:
        if r["crawl_time"] in prev_times:
            prev_rows[(r["crawl_time"], r["cluster_id"])] = r

    def high_price_for(iid):
        """返回前 prev_n 次里该商品的最高价（基准高位）。"""
        best = None
        for t in prev_times:
            r = prev_rows.get((t, iid))
            if r is not None:
                p = parse_price(r["price"])
                if p is not None and (best is None or p > best):
                    best = p
        return best

    alerts = []
    for iid, r in cur_map.items():
        cur = parse_price(r["price"])
        if cur is None:
            continue
        high = high_price_for(iid)
        if high is None:
            continue  # 前 prev_n 次都没有该商品，无法判定基准
        if high <= cur:
            continue  # 没降价（持平/上涨），不提醒
        drop_abs = high - cur
        drop_pct = drop_abs / high if high > 0 else 0.0
        if drop_abs > abs_th or drop_pct > pct_th:
            alerts.append({
                "cluster_id": iid,
                "title": r["title"],
                "cur": cur,
                "high": high,
                "drop_abs": drop_abs,
                "drop_pct": drop_pct,
                "url": r.get("url", ""),
            })
    alerts.sort(key=lambda x: (-x["drop_pct"], -x["drop_abs"]))
    return {"alerts": alerts, "current_time": current_time,
            "prev_times": prev_times, "baseline_count": len(cur_map)}


def write_alert_csv(alerts, path):
    """将价格异动列表导出为 CSV（带 BOM，Excel 中文不乱码）。"""
    cols = ["cluster_id", "title", "high_price", "cur_price",
            "drop_abs", "drop_pct", "url"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for a in alerts:
            w.writerow({
                "cluster_id": a["cluster_id"],
                "title": a["title"],
                "high_price": f"{a['high']:.2f}",
                "cur_price": f"{a['cur']:.2f}",
                "drop_abs": f"{a['drop_abs']:.2f}",
                "drop_pct": f"{a['drop_pct'] * 100:.2f}",
                "url": a["url"],
            })


def print_price_alerts(history_path, category, current_time=None,
                       prev_n=3, abs_th=10.0, pct_th=0.10):
    """打印价格异动提醒（依赖 detect_price_alerts）。返回其返回 dict。"""
    res = detect_price_alerts(history_path, category, current_time,
                              prev_n, abs_th, pct_th)
    if res is None:
        print("\n历史文件中没有数据，无法检测价格异动。")
        return res
    alerts = res["alerts"]
    cat_label = category if category else "all"
    print("\n" + "=" * 60)
    print(f"【价格异动提醒】 分类={cat_label}")
    print(f"  本次抓取: {res['current_time']}")
    print(f"  对比基准: 前 {len(res['prev_times'])} 次抓取各自的最高价")
    if res["prev_times"]:
        print(f"           ({'  |  '.join(res['prev_times'])})")
    print(f"  触发条件: 降价 > {abs_th:.0f} 元 或 > {pct_th * 100:.0f}%")
    if not alerts:
        print("  ✓ 本次未检测到符合阈值的价格异动商品。")
        return res
    print(f"  ⚠️ 共发现 {len(alerts)} 个降价异动商品：")
    for a in alerts[:30]:
        print(f"    🔻 {a['title']}")
        print(f"       高位 {fmt_money(a['high'])} → 现 {fmt_money(a['cur'])}  "
              f"(降 {a['drop_abs']:.2f}元 / {a['drop_pct'] * 100:.1f}%)")
    if len(alerts) > 30:
        print(f"    ... 其余 {len(alerts) - 30} 个见 --alert-csv 导出文件")
    return res


def list_filters(home):
    """列出可筛选的维度与取值（用于配合 --sort/--category/--ip）。"""
    fb = home.get("filterBar", {})
    print("【排序 sort_type】")
    for s in fb.get("sortTypes", []):
        mark = " *" if s.get("selected") else ""
        print(f"  {s.get('type')}: {s.get('name')}{mark}")
    print("\n【商品分类 category_id】")
    for c in fb.get("quickCategories", []):
        print(f"  {c.get('id')}: {c.get('name')}")
    print("\n【IP 分区 ip_id】")
    for c in fb.get("quickIp", []):
        print(f"  {c.get('id')}: {c.get('name')}")


def main():
    parser = argparse.ArgumentParser(
        description="抓取 B 站会员购转售首页商品信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python bili_resell.py                 # 默认抓全部 3c数码 并追加历史表(自动对比走势)\n"
            "  python bili_resell.py --pages 3       # 仅抓 3c数码 前 3 页(每页20)\n"
            "  python bili_resell.py --all           # 抓全部 3c数码(自动翻页去重)\n"
            "  python bili_resell.py --csv 3c.csv    # 另存一份本次快照 CSV\n"
            "  python bili_resell.py --sort priceFirst\n"
            "  python bili_resell.py --category 142 --ip 3000003\n"
            "  python bili_resell.py --category all  # 抓取全部分类\n"
            "  python bili_resell.py --json out.json # 导出本次数据(含 meta)到 JSON\n"
            "  python bili_resell.py --trend         # 读取历史表，对比最近两次价格走势(不抓取)\n"
            "  python bili_resell.py --list-filters  # 查看可筛选维度取值\n"
        ),
    )
    parser.add_argument("--pages", type=int, default=None,
                        help="要抓取的商品流页数(每页20条)；不传则抓取全部")
    parser.add_argument("--all", action="store_true",
                        help="抓取该分类下的全部商品(自动翻页直到 hasMore=false)")
    parser.add_argument("--sort", default="hot",
                        choices=["hot", "mostListings", "priceFirst"],
                        help="排序: hot=热门, mostListings=在售最多, priceFirst=价格优先")
    parser.add_argument("--category", default="898",
                        help="商品分类 ID (见 --list-filters)，默认 898=3c数码；传 all 表示全部")
    parser.add_argument("--ip", default=None, help="IP 分区 ID (见 --list-filters)；传 all 表示全部")
    parser.add_argument("--list-filters", action="store_true",
                        help="仅列出可筛选的排序/分类/IP 取值后退出")
    parser.add_argument("--json", default=None, help="将商品数据(含 meta)导出到该 JSON 文件")
    parser.add_argument("--csv", default=None, help="将本次抓取的商品数据导出为一份 CSV 快照(覆盖写入)")
    parser.add_argument("--history", default="3c_products_history.csv",
                        help="历史累计文件(每次抓取自动追加，用于对比走势)；设为空字符串可关闭")
    parser.add_argument("--no-history", action="store_true",
                        help="不写入历史累计文件(仅本次输出)")
    parser.add_argument("--trend", action="store_true",
                        help="仅读取历史文件并打印最近两次的价格走势对比，不发起抓取")
    parser.add_argument("--no-overview", action="store_true",
                        help="不打印首页概览(限时大漏/筛选维度)")
    parser.add_argument("--no-alert", action="store_true",
                        help="关闭价格异动提醒(默认开启)")
    parser.add_argument("--alert-prev", type=int, default=3,
                        help="价格异动对比的历史抓取次数(默认 3，取前 n 次各自最高价作基准)")
    parser.add_argument("--alert-abs", type=float, default=10.0,
                        help="价格异动绝对阈值(元，默认 10)")
    parser.add_argument("--alert-pct", type=float, default=0.10,
                        help="价格异动相对阈值(默认 0.10 = 10%%)")
    parser.add_argument("--alert-csv", default=None,
                        help="将价格异动商品导出为 CSV(覆盖写入)")
    args = parser.parse_args()

    # 将 "all" / 空字符串 解析为「不筛选」
    cat = None if args.category in ("", "all") else args.category
    ip = None if args.ip in ("", "all") else args.ip

    # 仅查看历史走势（不抓取）
    if args.trend:
        print_trend(args.history or "3c_products_history.csv", cat)
        return

    # 初始化 B 站前端设备指纹 Cookie (buvid3/buvid4)
    init_session_cookies()

    try:
        home = get_home()
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list_filters:
        list_filters(home)
        return

    if not args.no_overview:
        print_overview(home)

    # 商品流抓取说明：
    # 该接口无论 pageSize 传多少都固定返回 20 条，且 hasMore 长期为 true、
    # 商品列表会循环返回（翻到某一页会与前面完全重复）。因此「获取全部」
    # 的正确做法是：按 item id 去重，并在「整页都为已见过的商品」时停止翻页。
    MAX_PAGES = 500  # 安全上限，防止接口异常导致死循环
    if args.all or args.pages is None:
        max_pages = MAX_PAGES
        mode = "全部(去重后)"
    else:
        max_pages = args.pages
        mode = f"前 {args.pages} 页"

    # 已去重的商品（id -> 原始 item），ordered 保持首次出现顺序
    seen_ids = set()
    ordered = []

    def add_items(items):
        added = []
        for it in items:
            iid = it.get("id")
            if iid not in seen_ids:
                seen_ids.add(iid)
                ordered.append(it)
                added.append(it)
        return added

    if cat or ip:
        feed = get_feed(page_num=1, sort_type=args.sort,
                        category_id=cat, ip_id=ip)
        first_items = feed.get("items", [])
        has_more = feed.get("hasMore", False)
    else:
        home_feed = home.get("feed", {})
        first_items = home_feed.get("items", [])
        has_more = home_feed.get("hasMore", False)
    first_added = add_items(first_items)
    cat_label = f"  分类={cat}" if cat else ""
    ip_label = f"  IP={ip}" if ip else ""
    print(f"\n【商品流】 排序={args.sort}{cat_label}{ip_label}  抓取范围={mode}")
    if first_added:
        print_items(first_added, start_no=1)

    page = 2
    no_new_streak = 0
    fail_streak = 0
    while page <= max_pages and has_more:
        try:
            feed = get_feed_safe(page_num=page, sort_type=args.sort,
                                 category_id=cat, ip_id=ip)
        except RuntimeError as e:
            fail_streak += 1
            print(f"  (第{page}页抓取失败，重试仍失败已跳过: {e})")
            if fail_streak >= 5:
                print("  (连续多页抓取失败，疑似网络中断，停止翻页)")
                break
            page += 1
            time.sleep(3.0)  # 发生异常跳过时退避等待，避免连续撞在封禁窗口
            continue
        fail_streak = 0
        items = feed.get("items", [])

        if not items:
            # 接口返回空列表，表明已无更多商品
            no_new_streak += 1
            if no_new_streak >= 2:
                print(f"  (第{page}页返回空列表，商品已抓取完毕，停止翻页)")
                break
            page += 1
            time.sleep(0.5)
            continue

        added = add_items(items)  # 按 id 去重
        if added:
            no_new_streak = 0
            # 为避免大量数据刷屏，仅在前几页 / 前若干条时打印明细
            if page <= 3 or len(ordered) <= 60:
                print_items(added, start_no=len(ordered) - len(added) + 1)
        else:
            # 本页没有新增唯一商品（整页重复）
            no_new_streak += 1
            print(f"  (第{page}页无新增唯一商品，连续 {no_new_streak} 页)")
            if no_new_streak >= 5:
                print("  (连续多页无新增商品，判定当前排序下商品已抓完，停止翻页)")
                break

        has_more = feed.get("hasMore", False)
        page += 1
        time.sleep(random.uniform(0.8, 1.2))  # 稳健延时，避免触发 B站频控限流

    if page > max_pages and (args.all or args.pages is None):
        print(f"  (已达到翻页上限 {max_pages} 页，可能在 cap 内未抓全；可上调源码 MAX_PAGES 重试)")

    total = len(ordered)
    if total > 60:
        print(f"  ... 已获取 {total} 条唯一商品（为节省篇幅仅展示前若干条，完整数据请用 --json/--csv 导出）")

    # 导出数据（均为去重后的唯一商品）
    if args.json:
        export = {
            "meta": {
                "category": cat, "ip": ip, "sort": args.sort,
                "total": total,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "products": [normalize_item(it) for it in ordered],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        print(f"已导出商品数据 -> {args.json}")

    if args.csv:
        export_csv(ordered, args.csv)
        print(f"已导出商品数据 -> {args.csv}")

    # 历史累计：每次抓取自动追加，便于多次对比走势
    crawl_time = time.strftime("%Y-%m-%d %H:%M:%S")
    if args.history and not args.no_history:
        append_history(ordered, args.history, cat, crawl_time)
        print(f"已追加本次抓取 ({total} 条) 到历史文件 -> {args.history}")
        print_trend(args.history, cat, current_time=crawl_time)

        # 价格异动提醒：对比本次与前 N 次抓取的高位价，降价超阈值即标记
        if not args.no_alert:
            alert_res = print_price_alerts(
                args.history, cat, current_time=crawl_time,
                prev_n=args.alert_prev, abs_th=args.alert_abs, pct_th=args.alert_pct)
            if args.alert_csv and alert_res is not None:
                write_alert_csv(alert_res["alerts"], args.alert_csv)
                print(f"已导出价格异动 -> {args.alert_csv}")

        # 抓取完成后，若历史文件已有数据，检查本次是否显著偏少（疑似漏抓）
        if os.path.exists(args.history):
            try:
                _rows, _times = read_history(args.history)
                _cat = cat if cat else "all"
                _per = []
                for _t in _times:
                    if _t == crawl_time:
                        continue
                    _ids = {r["cluster_id"] for r in _rows
                            if r.get("category") == _cat and r["crawl_time"] == _t}
                    if _ids:
                        _per.append(len(_ids))
                if _per:
                    _avg = sum(_per) / len(_per)
                    if total < _avg * 0.5:
                        print("")
                        print(f"⚠️ 警告：本次仅抓取 {total} 条，低于历史均值 {_avg:.0f} 的 50%。")
                        print("   可能撞上 B站转售接口偶发「早循环」窗口导致漏抓，"
                              "建议用 --pages 强制翻页或换 mostListings/priceFirst 排序后重跑。")
            except Exception:
                pass

    print("\n" + "=" * 60)
    print(f"本次共获取唯一商品 {total} 条。")


if __name__ == "__main__":
    main()
