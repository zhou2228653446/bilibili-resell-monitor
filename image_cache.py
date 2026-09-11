#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站转售监控 - 商品图片本地缓存模块 (ImageCache)

设计要点：
1. 磁盘缓存 + 内容寻址命名，图片 URL 即内容哈希，URL 不变则永久命中。
2. 缩略图牵引：抓取/回源时主动追加 B站 CDN 图片处理后缀（默认 480w webp），
   实测可将原图 449KB 压到 12.5KB（约 2.8%），使全量归档从 GB 级降到几十 MB。
3. LRU 淘汰：按目录总容量上限自动清理最久未访问的图片，防止磁盘无限膨胀。
4. 线程安全：所有磁盘写入走原子替换（临时文件 + os.replace），并发安全。
5. 零第三方依赖：仅用 Python 标准库，与项目主程序保持一致。

缓存目录结构：
    cache/img/<前2位>/<sha1>.<ext>
    例如 cache/img/4a/4aeae511eb51d1d40a44cdccc99180bf.webp
"""

import hashlib
import http.client
import os
import shutil
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request

# Windows / Linux 双端通用的 SSL 宽松上下文（B站 CDN 存在链不完整情况）
_SSL_CTX = ssl._create_unverified_context()

# 图片处理后缀白名单：只把「已知可安全追加」的原始 CDN 地址挑出来加后缀，
# 避免对已带 @ 参数的 URL 重复追加导致 404。
DEFAULT_THUMB_SUFFIX = "@480w_480h_1c.webp"

# 多档位后缀：用于「先低清占位、再加载高清」的渐进式加载。
#   place  极小占位图，2~3KB，先铺满格子避免白屏/跳动
#   mid    中等尺寸，列表滚动时的过渡档
#   hi     高清档，用户点开大图时用（等同 DEFAULT_THUMB_SUFFIX）
# 实测同一原图(197KB)各档体积：
#   @120w = 2.3KB   @240w = 5.1KB   @320w = 7.4KB   @480w = 12.9KB   @800w = 24KB
_SIZE_SUFFIX = {
    "place": "@120w_120h_1c.webp",
    "mid": "@240w_240h_1c.webp",
    "hi": "@480w_480h_1c.webp",
    "big": "@800w_800h_1c.webp",
}

# 支持追加缩略图后缀的宿主白名单（B站图片 CDN）
_CDN_HOSTS = (
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "hdslb.com",
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_CONTENT_TYPE_EXT = {
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


def _log_factory(log_callback):
    """统一日志出口：有回调走回调，否则静默（避免污染 Web 服务日志）。"""
    if log_callback:
        def _log(msg):
            try:
                log_callback(str(msg))
            except Exception:
                pass
        return _log

    def _silent(msg):
        pass
    return _silent


class _ConnPool:
    """
    按 host 复用 HTTPS 长连接的极简连接池。

    关键性能点：图片单张仅 5~20KB，而一次 TCP + TLS 握手在跨网环境下往往要
    数百毫秒到数秒，远大于传输本身。复用连接后，第二张起可跳过握手，
    批量归档的吞吐能提升一个数量级。
    """

    def __init__(self, timeout=20):
        self.timeout = timeout
        self._conns = {}
        self._lock = threading.Lock()

    def _get(self, host):
        with self._lock:
            conn = self._conns.get(host)
            if conn is not None:
                return conn
            ctx = _SSL_CTX
            conn = http.client.HTTPSConnection(host, timeout=self.timeout, context=ctx)
            self._conns[host] = conn
            return conn

    def get(self, url, headers, timeout=None):
        """
        用长连接发起 GET，返回 (status, content_type, body)。
        连接失效（对端关闭/超时）时自动重建并重试一次。
        """
        parsed = urllib.parse.urlsplit(url)
        host = parsed.netloc
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        last_err = None
        for attempt in (0, 1):
            conn = self._get(host)
            try:
                conn.request("GET", path, headers=headers)
                resp = conn.getresponse()
                body = resp.read()
                if resp.status != 200:
                    raise OSError("HTTP %s" % resp.status)
                return resp.status, (resp.getheader("Content-Type") or "image/webp"), body
            except Exception as e:
                last_err = e
                # 该连接已不可用，丢弃后重试一次（第二次会新建连接）
                with self._lock:
                    old = self._conns.pop(host, None)
                if old is not None:
                    try:
                        old.close()
                    except Exception:
                        pass
                if attempt == 1:
                    break
        raise last_err if last_err else OSError("unknown error")

    def close(self):
        with self._lock:
            for conn in self._conns.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._conns.clear()


class ImageCache:
    """商品图片磁盘缓存管理器。"""

    def __init__(self, cache_dir, max_size_mb=512, thumb_suffix=DEFAULT_THUMB_SUFFIX,
                 timeout=20, log_callback=None, min_interval=0.0):
        """
        :param cache_dir:   缓存根目录
        :param max_size_mb: 目录容量上限（MB），超出后按访问时间 LRU 淘汰
        :param thumb_suffix: B站 CDN 缩略图后缀；传 None / "" 表示存原图
        :param timeout:     单张图下载超时（秒）
        :param min_interval: 两次下载之间的最小间隔（秒），用于限速保护带宽
        """
        self.cache_dir = cache_dir
        self.max_size_bytes = int(max_size_mb) * 1024 * 1024
        self.thumb_suffix = thumb_suffix
        self.timeout = timeout
        self.min_interval = min_interval
        self.log = _log_factory(log_callback)

        self._lock = threading.Lock()
        self._last_fetch_ts = 0.0
        # 长连接池：跨图片复用 TCP+TLS，避免每张小图都重新握手
        self._pool = _ConnPool(timeout=timeout)
        # 运行期统计，便于在控制台展示本次归档效果
        self.stats = {"hit": 0, "miss": 0, "saved": 0, "fail": 0, "bytes_in": 0}

        os.makedirs(self.cache_dir, exist_ok=True)

    # ---------------- 内部工具 ----------------

    @staticmethod
    def _key_for(url, size=None):
        """
        图片 URL(+档位) -> sha1 十六进制。

        同一张原图会按不同档位（占位图 @120w / 高清图 @480w）分别缓存，
        因此档位必须并入 key，否则两档会互相覆盖。
        """
        raw = url if not size else f"{size}|{url}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _path_for(self, url, ext, size=None):
        key = self._key_for(url, size)
        sub = os.path.join(self.cache_dir, key[:2])
        return os.path.join(sub, key + ext)

    def _find_existing(self, url, size=None):
        """在磁盘上查找该 URL 的缓存文件（不关心扩展名）。"""
        key = self._key_for(url, size)
        sub = os.path.join(self.cache_dir, key[:2])
        if not os.path.isdir(sub):
            return None
        for name in os.listdir(sub):
            if name.startswith(key):
                return os.path.join(sub, name)
        return None

    def _thumb_url(self, url, size=None):
        """
        为 CDN 地址追加缩略图后缀；非 CDN 或已带参数则原样返回。

        :param size: 尺寸档位标识（如 "place" 走占位图、None 走默认高清档）
        """
        suffix = self.thumb_suffix if size is None else _SIZE_SUFFIX.get(size, self.thumb_suffix)
        if not suffix:
            return url
        if "@" in url:
            return url
        lowered = url.lower()
        for host in _CDN_HOSTS:
            if f"//{host}/" in lowered:
                return url + suffix
        return url

    def _throttle(self):
        """限速：保证两次下载之间至少间隔 min_interval 秒。"""
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_fetch_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_fetch_ts = time.time()

    def _evict_if_needed(self):
        """容量超限时按 atime/mtime 从旧到新淘汰，直到低于上限的 90%。"""
        try:
            entries = []
            total = 0
            for root, _dirs, files in os.walk(self.cache_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    total += st.st_size
                    entries.append((max(st.st_atime, st.st_mtime), st.st_size, fp))
            if total <= self.max_size_bytes:
                return
            target = int(self.max_size_bytes * 0.9)
            entries.sort(key=lambda x: x[0])
            removed = 0
            freed = 0
            for _ts, size, fp in entries:
                if total - freed <= target:
                    break
                try:
                    os.remove(fp)
                    freed += size
                    removed += 1
                except OSError:
                    continue
            if removed:
                self.log(f"[ImageCache] 容量超限，已淘汰 {removed} 张旧图，释放 "
                          f"{freed / 1024 / 1024:.1f} MB")
        except Exception as e:
            self.log(f"[ImageCache] 淘汰异常: {e}")

    # ---------------- 对外接口 ----------------

    def has(self, url, size=None):
        """判断是否已缓存（可指定档位）。"""
        if not url:
            return False
        return self._find_existing(url, size) is not None

    def get(self, url, size=None, _count_stat=True):
        """读取缓存，返回 (bytes, content_type, path)；未命中返回 (None, None, None)。"""
        if not url:
            return None, None, None
        path = self._find_existing(url, size)
        if not path:
            if _count_stat:
                self.stats["miss"] += 1
            return None, None, None
        try:
            with open(path, "rb") as f:
                data = f.read()
            # 触摸访问时间，让 LRU 反映真实使用热度
            try:
                os.utime(path, None)
            except OSError:
                pass
            if _count_stat:
                self.stats["hit"] += 1
            return data, self._guess_ct(path), path
        except OSError:
            if _count_stat:
                self.stats["miss"] += 1
            return None, None, None

    @staticmethod
    def _guess_ct(path):
        ext = os.path.splitext(path)[1].lower()
        for ct, e in _CONTENT_TYPE_EXT.items():
            if e == ext:
                return ct
        return "application/octet-stream"

    def fetch_and_store(self, url, size=None, force=False, _count_stat=True):
        """
        下载并落盘。已缓存则直接返回（除非 force=True）。
        返回 (bytes, content_type)；失败返回 (None, None)。

        :param size: 档位标识（None=默认高清档，其余见 _SIZE_SUFFIX）
        """
        if not url or not url.startswith("http"):
            return None, None

        if not force:
            # get() 内部已按 _count_stat 完成 hit/miss 计数，此处不再重复
            data, ct, _p = self.get(url, size=size)
            if data is not None:
                return data, ct

        self._throttle()
        target = self._thumb_url(url, size=size)
        headers = {"User-Agent": _USER_AGENT, "Referer": "https://mall.bilibili.com/",
                   "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                   "Connection": "keep-alive"}
        try:
            # 走长连接池：同一 host 的图片复用 TCP+TLS，避免每张都重新握手
            _st, ct_raw, data = self._pool.get(target, headers)
            ct = (ct_raw or "image/webp").split(";")[0].strip()
        except Exception as e:
            # 缩略图后缀失败时回退原图，保证不丢图。
            #
            # ⚠️ 但仅对「大图档」允许回退：place/mid 是给首屏铺格子用的，
            # 一旦回退成原图（可能几百 KB~1MB）会彻底毁掉渐进式加载的意义
            # —— 首屏反而更慢，且原图会被永久缓存进占位档。
            # 小档失败就干脆返回空，前端继续显示占位底色，等下轮再试。
            allow_fallback = size in (None, "hi", "big")
            if target != url and allow_fallback:
                try:
                    _st, ct_raw, data = self._pool.get(url, headers)
                    ct = (ct_raw or "image/png").split(";")[0].strip()
                except Exception as e2:
                    self.stats["fail"] += 1
                    self.log(f"[ImageCache] 下载失败 {url[:70]}: {e2}")
                    return None, None
            else:
                self.stats["fail"] += 1
                if target != url:
                    self.log(f"[ImageCache] 缩略档 {size} 下载失败(不回退原图) "
                              f"{url[:70]}: {e}")
                else:
                    self.log(f"[ImageCache] 下载失败 {url[:70]}: {e}")
                return None, None

        ext = _CONTENT_TYPE_EXT.get(ct, ".webp")
        path = self._path_for(url, ext, size=size)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 原子写入：先写临时文件再 rename，避免并发读到半截文件
        tmp = path + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except OSError as e:
            self.log(f"[ImageCache] 落盘失败 {path}: {e}")
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return data, ct

        # 注意：miss 已在上面 get() 未命中时计数，这里只统计实际下载落盘
        self.stats["saved"] += 1
        self.stats["bytes_in"] += len(data)

        # 每存 50 张检查一次容量，避免每次都遍历目录
        if self.stats["saved"] % 50 == 0:
            with self._lock:
                self._evict_if_needed()

        return data, ct

    def prefetch_many(self, urls, size=None, log_every=100, stop_event=None):
        """
        批量预热：顺序下载，内置限速。返回统计 dict。
        仅下载未缓存的，已缓存直接跳过（零流量）。

        :param size: 档位标识；传 None 走默认高清档
        """
        urls = [u for u in urls if u and isinstance(u, str)]
        pending = [u for u in urls if not self.has(u, size=size)]
        skipped = len(urls) - len(pending)
        self.log(f"[ImageCache] 预热开始（档位 {size or 'default'}）："
                  f"待下载 {len(pending)} 张（已缓存跳过 {skipped} 张）")

        ok = 0
        fail = 0
        done = 0
        for u in pending:
            if stop_event is not None and stop_event.is_set():
                self.log("[ImageCache] 收到停止信号，预热中止")
                break
            data, _ct = self.fetch_and_store(u, size=size)
            done += 1
            if data:
                ok += 1
            else:
                fail += 1
            if log_every and done % log_every == 0:
                self.log(f"[ImageCache] 预热进度 {done}/{len(pending)} "
                          f"(成功 {ok} / 失败 {fail})，已下载 "
                          f"{self.stats['bytes_in'] / 1024 / 1024:.1f} MB")

        self.log(f"[ImageCache] 预热完成（档位 {size or 'default'}）：成功 {ok}，失败 {fail}，"
                  f"本次入网 {self.stats['bytes_in'] / 1024 / 1024:.1f} MB")
        return {"ok": ok, "fail": fail, "skipped": skipped, "bytes_in": self.stats["bytes_in"]}

    def stat(self):
        """返回缓存目录当前状态（图片数 / 总容量）。"""
        count = 0
        total = 0
        for root, _dirs, files in os.walk(self.cache_dir):
            for fn in files:
                if fn.endswith(".tmp"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    total += os.path.getsize(fp)
                    count += 1
                except OSError:
                    continue
        return {
            "count": count,
            "bytes": total,
            "mb": round(total / 1024 / 1024, 2),
            "max_mb": round(self.max_size_bytes / 1024 / 1024, 1),
            **self.stats,
        }

    def clear(self):
        """清空缓存目录。"""
        try:
            if os.path.isdir(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            return True
        except OSError as e:
            self.log(f"[ImageCache] 清空失败: {e}")
            return False

    def purge_oversized(self, max_kb=40):
        """
        清理「缩略档里混进的大图」这类脏缓存。

        背景：早期版本在缩略图下载失败时会回退下载原图，并把原图存进了
        占位/中间档的缓存槽位（原图可能几百 KB~1MB）。这些脏数据会让首屏
        反而变慢，且永远命中不会再重下。此方法按大小把它们删掉，
        下次访问即会重新拉取正确的缩略图。

        :param max_kb: 超过该体积即视为脏数据（默认 40KB；正常缩略图均 < 30KB）
        :return: (删除数量, 释放字节数)
        """
        limit = max_kb * 1024
        removed = 0
        freed = 0
        try:
            for root, _dirs, files in os.walk(self.cache_dir):
                for fn in files:
                    if fn.endswith(".tmp"):
                        continue
                    fp = os.path.join(root, fn)
                    try:
                        sz = os.path.getsize(fp)
                    except OSError:
                        continue
                    if sz <= limit:
                        continue
                    try:
                        os.remove(fp)
                        removed += 1
                        freed += sz
                    except OSError:
                        continue
            if removed:
                self.log(f"[ImageCache] 已清理 {removed} 个超大缩略图缓存，"
                          f"释放 {freed / 1024 / 1024:.1f} MB")
            return removed, freed
        except Exception as e:
            self.log(f"[ImageCache] 清理异常: {e}")
            return removed, freed

    def close(self):
        """释放长连接池占用的资源（进程退出前调用）。"""
        try:
            self._pool.close()
        except Exception:
            pass


def extract_img_urls(data):
    """
    从看板数据结构（get_latest_data 的返回）或商品列表中提取全部图片 URL。
    兼容 alerts / products 两种节点。
    """
    urls = []
    seen = set()

    def _add(u):
        if u and isinstance(u, str) and u.startswith("http") and u not in seen:
            seen.add(u)
            urls.append(u)

    if isinstance(data, dict):
        for node in ("products", "alerts"):
            for item in data.get(node) or []:
                if isinstance(item, dict):
                    _add(item.get("img"))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _add(item.get("img"))
    return urls


if __name__ == "__main__":
    # 简易自测：python image_cache.py <缓存目录> <图片URL> [...]
    if len(sys.argv) < 3:
        print("用法: python image_cache.py <缓存目录> <图片URL> [更多URL...]")
        sys.exit(1)
    _dir = sys.argv[1]
    ic = ImageCache(_dir, max_size_mb=128, log_callback=lambda m: print(m))
    for _u in sys.argv[2:]:
        _t0 = time.time()
        _data, _ct = ic.fetch_and_store(_u)
        _cost = (time.time() - _t0) * 1000
        if _data:
            print(f"  OK {len(_data) / 1024:.1f} KB  {_ct}  {_cost:.0f}ms  {_u[:80]}")
        else:
            print(f"  FAIL  {_u[:80]}")
    print(ic.stat())
