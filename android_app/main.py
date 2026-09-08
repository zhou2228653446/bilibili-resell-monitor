# -*- coding: utf-8 -*-
"""B站会员购转售监控 - Android 端 (Kivy)

架构说明：
- 不内嵌 http.server（安卓后台服务受限），直接 import bili_resell 函数调用；
- 数据文件落在应用私有目录（android_compat.get_out_path 适配）；
- UI 为移动端原生布局：商品列表 / 降价雷达 / 抓取 / 通知设置 四页；
- 爬虫在线程中执行，UI 通过 Clock 主线程调度刷新，不卡界面。
"""
import json
import os
import threading
import time

# ---- 中文字体注册（必须放在所有其他 kivy 导入之前！）----
# Kivy 在 kivy.core.text 模块被导入的那一瞬间就从 Config 读取 default_font 并
# 固化默认字体（kivy/core/text/__init__.py: literal_eval(Config.get(...)) +
# 模块级 Label.register(DEFAULT_FONT, ...)）。若此块放在 from kivy.core.window
# import Window 之后，core.text 早已导入完毕，default_font 永远停留在 Roboto，
# 而 Roboto 不含 CJK 字形、安卓无系统字体回退 → 全部中文渲染成黑框叉。
# default_font 为 4 元素列表：[name, regular, italic, bold]。
from kivy.config import Config  # kivy.config 本身不触发 core.text 导入，安全

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "NotoSansCJKsc-Regular.otf")
if os.path.exists(_FONT_PATH):
    Config.set("kivy", "default_font",
               repr(["CJK", _FONT_PATH, _FONT_PATH, _FONT_PATH]))

# ---- 字体配置完成，以下才是正常导入 ----
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.core.text import LabelBase

from android_compat import IS_ANDROID, get_out_path
import bili_resell

# 显式注册 CJK 名称（default_font 生效时此调用为幂等重复，双保险）
if os.path.exists(_FONT_PATH):
    LabelBase.register(name="CJK", fn_regular=_FONT_PATH,
                       fn_bold=_FONT_PATH, fn_italic=_FONT_PATH)

# 安卓端数据文件路径（桌面调试时与原路径一致）
JSON_PATH = get_out_path("3c_products.json")
HISTORY_PATH = get_out_path("3c_products_history.csv")
DEALS_CACHE_PATH = get_out_path("deals_cache.json")

# 移动端友好的中文字号与配色（浅色主题）
C_PRIMARY = "#1f6feb"
C_BG = "#f6f8fa"
C_CARD = "#ffffff"
C_TEXT = "#24292f"
C_SUB = "#57606a"
C_DROP = "#cf222e"   # 降价红（A股习惯：红涨绿跌，但捡漏降价是好事→红色醒目）
C_DEAL = "#1a7f37"   # 成交价绿

Window.clearcolor = C_BG


def _parse_price(s):
    """'¥47.80' -> 47.8，失败返回 None。"""
    try:
        return float(str(s).replace("¥", "").replace(",", "").strip())
    except Exception:
        return None


class CardRow(BoxLayout):
    """单条商品卡片：标题 / 在售价 / 成交价 / 降幅。"""

    def __init__(self, product, **kw):
        super().__init__(orientation="vertical", padding=dp(10),
                         spacing=dp(4), size_hint_y=None, **kw)
        self.height = dp(96)
        title = product.get("title", "未知商品")
        if len(title) > 40:
            title = title[:40] + "…"

        price_num = _parse_price(product.get("price"))
        deal_num = _parse_price(product.get("latest_deal_price"))
        drop_txt = ""
        if price_num and deal_num and price_num > 0:
            pct = (deal_num - price_num) / price_num * 100
            if pct <= -10:
                drop_txt = f"  低于成交 {abs(pct):.0f}%"

        header = BoxLayout(size_hint_y=None, height=dp(22))
        header.add_widget(Label(text=title, font_size=sp(14),
                                color=C_TEXT, bold=True,
                                halign="left", valign="middle",
                                size_hint_x=0.75,
                                text_size=(Window.width - dp(48), None)))
        header.add_widget(Label(text=f"{product.get('price', '-')}",
                                font_size=sp(14), color=C_PRIMARY, bold=True))
        self.add_widget(header)

        footer = BoxLayout(size_hint_y=None, height=dp(20))
        footer.add_widget(Label(
            text=f"成交 {product.get('latest_deal_price', '查成交...')}{drop_txt}",
            font_size=sp(12),
            color=C_DEAL if deal_num else C_SUB))
        footer.add_widget(Label(
            text=product.get("discount_rate", "") or "",
            font_size=sp(12), color=C_DROP))
        self.add_widget(footer)


class TabBar(BoxLayout):
    """底部标签栏。"""

    def __init__(self, app_ref, **kw):
        super().__init__(size_hint=(1, None), height=dp(52), **kw)
        self.app_ref = app_ref
        for name, cb in (("列表", app_ref.show_list),
                         ("雷达", app_ref.show_radar),
                         ("抓取", app_ref.show_crawl),
                         ("设置", app_ref.show_settings)):
            btn = Button(text=name, font_size=sp(15), bold=True,
                         background_normal="", background_color=(0.94, 0.96, 0.98, 1),
                         color=C_PRIMARY)
            btn.bind(on_press=lambda _b, f=cb: f())
            self.add_widget(btn)


class ResellMonitorMobile(App):
    title = "B站捡漏监控"

    def build(self):
        self.root_box = BoxLayout(orientation="vertical")
        self.content = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.root_box.add_widget(self.content)
        self.root_box.add_widget(TabBar(self))
        self.products = []
        self.alerts = []
        self.crawling = False
        Clock.schedule_once(lambda _dt: self.show_list(), 0.1)
        return self.root_box

    # ---------- 数据 ----------
    def load_products(self):
        try:
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                self.products = data.get("products", data) if isinstance(data, dict) else data
        except Exception as e:
            self.toast(f"读取数据失败: {e}")

    def sort_by_deal_gap(self, items):
        """成交价低于在售越多越靠前（捡漏优先）。"""
        def gap(p):
            a, b = _parse_price(p.get("price")), _parse_price(p.get("latest_deal_price"))
            return (b - a) / a if a and b and a > 0 else -999
        return sorted(items, key=gap, reverse=True)

    # ---------- 页面 ----------
    def _clear(self):
        self.content.clear_widgets()

    def show_list(self):
        self._clear()
        self.load_products()
        self._header(f"商品列表  共 {len(self.products)} 件")
        if not self.products:
            self.content.add_widget(Label(text="暂无数据，请到「抓取」页执行一次抓取",
                                          color=C_SUB, font_size=sp(14)))
            return
        sv = ScrollView()
        grid = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        for p in self.products[:80]:
            grid.add_widget(CardRow(p))
        sv.add_widget(grid)
        self.content.add_widget(sv)

    def show_radar(self):
        self._clear()
        self.load_products()
        self._header("降价雷达  捡漏优先排序")
        hot = self.sort_by_deal_gap([p for p in self.products
                                     if _parse_price(p.get("latest_deal_price"))])
        if not hot:
            self.content.add_widget(Label(text="暂无成交价数据", color=C_SUB))
            return
        sv = ScrollView()
        grid = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        for p in hot[:30]:
            grid.add_widget(CardRow(p))
        sv.add_widget(grid)
        self.content.add_widget(sv)

    def show_crawl(self):
        self._clear()
        self._header("手动抓取")
        self.crawl_log = Label(text="点击下方按钮开始抓取\n(约 1-3 分钟，请保持网络畅通)",
                               color=C_SUB, font_size=sp(13), halign="center")
        sort_sel = Spinner(text="默认排序",
                           values=("默认排序", "价格升序", "热门优先", "最多在售"),
                           size_hint=(1, None), height=dp(44), font_size=sp(14))
        self.sort_sel = sort_sel
        btn = Button(text="开始全量抓取", size_hint=(1, None), height=dp(50),
                     font_size=sp(16), bold=True,
                     background_normal="", background_color=(0.12, 0.44, 0.92, 1))
        btn.bind(on_press=lambda _b: self._start_crawl())
        for w in (sort_sel, btn, self.crawl_log):
            self.content.add_widget(w)

    def _start_crawl(self):
        if self.crawling:
            return
        self.crawling = True
        sort_map = {"默认排序": "hot", "价格升序": "priceFirst", "热门优先": "hot", "最多在售": "mostListings"}
        sort_id = sort_map.get(self.sort_sel.text, "hot")

        def worker():
            try:
                self.crawl_log.text = "抓取中…"
                bili_resell.crawl_and_export(
                    pages=5,                       # 移动端默认 5 页，省流量省时间
                    sort=sort_id,
                    output_json=JSON_PATH,
                    history_csv=HISTORY_PATH,
                    log_callback=lambda m: None,
                )
                msg = "抓取完成 ✓"
            except Exception as e:
                msg = f"抓取失败: {e}"
            Clock.schedule_once(lambda _dt: self._crawl_done(msg), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _crawl_done(self, msg):
        self.crawling = False
        self.crawl_log.text = msg
        self.toast(msg)

    def show_settings(self):
        self._clear()
        self._header("设置")
        info = (
            f"数据目录: {'应用私有目录' if IS_ANDROID else '项目根目录'}\n"
            f"商品快照: {os.path.basename(JSON_PATH)}\n"
            f"成交缓存: {os.path.basename(DEALS_CACHE_PATH)}\n\n"
            "推送通知(邮件/企微/PushPlus)当前版本\n"
            "在安卓端暂不可用，桌面端 Web 看板\n"
            "(web_server.py) 保留全部推送功能。"
        )
        self.content.add_widget(Label(text=info, color=C_SUB, font_size=sp(13),
                                      halign="center"))

    # ---------- 工具 ----------
    def _header(self, text):
        self.content.add_widget(Label(text=text, font_size=sp(17), bold=True,
                                      color=C_TEXT, size_hint_y=None, height=dp(34)))

    def toast(self, msg):
        popup = Popup(content=Label(text=msg, color=C_TEXT, font_size=sp(14)),
                      size_hint=(0.7, 0.18), auto_dismiss=True,
                      separator_color=C_PRIMARY)
        Clock.schedule_once(lambda _dt: popup.open(), 0)
        Clock.schedule_once(lambda _dt: popup.dismiss(), 2)


if __name__ == "__main__":
    ResellMonitorMobile().run()
