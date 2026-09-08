# -*- coding: utf-8 -*-
"""B站会员购转售监控 - Android 端 (Kivy 现代沉浸式重构版)

架构与设计：
- 现代 B 站粉色主题设计风格，圆角卡片、柔和阴影边框与精致视觉层级；
- 完整的商品缩略图展示 (AsyncImage 异步拉取与缓存)；
- 交互式详情弹窗 (ProductDetailModal)：展示商品规格、历史走势与 B 站近期买家真实成交记录；
- 实时搜索、筛选芯片 (低于成交价/3折神价/降价商品) 与多维度排序；
- 捡漏雷达、后台抓取实时日志控制台与局域网数据同步功能；
- 保持纯 Python + Kivy 依赖，适配 Buildozer 官方 Docker 镜像云端构建。
"""
import json
import os
import sys
import threading
import time
import webbrowser

# ---- 中文字体注册（必须置于其他 Kivy 模块导入之前！）----
from kivy.config import Config

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "NotoSansCJKsc-Regular.otf")
if os.path.exists(_FONT_PATH):
    Config.set("kivy", "default_font",
               repr(["CJK", _FONT_PATH, _FONT_PATH, _FONT_PATH]))

# 基础 Kivy 组件导入
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.core.text import LabelBase
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.image import AsyncImage

# 平台适配与爬虫核心模块
from android_compat import IS_ANDROID, get_out_path
import bili_resell

# 显式注册 CJK 名称（双重保障）
if os.path.exists(_FONT_PATH):
    LabelBase.register(name="CJK", fn_regular=_FONT_PATH,
                       fn_bold=_FONT_PATH, fn_italic=_FONT_PATH)

# 数据文件路径
JSON_PATH = get_out_path("3c_products.json")
HISTORY_PATH = get_out_path("3c_products_history.csv")
DEALS_CACHE_PATH = get_out_path("deals_cache.json")

# ---- 精心调校的移动端配色系统 ----
CLR_PRIMARY = (0.984, 0.447, 0.600, 1.0)       # #FB7299 B站经典粉
CLR_PRIMARY_DARK = (0.900, 0.350, 0.520, 1.0)  # 深粉色（按压态）
CLR_PRIMARY_LIGHT = (1.0, 0.930, 0.955, 1.0)   # 极浅粉色底
CLR_BG = (0.965, 0.973, 0.980, 1.0)            # #F6F8FA 页面底色
CLR_CARD = (1.0, 1.0, 1.0, 1.0)                # #FFFFFF 卡片纯白
CLR_BORDER = (0.898, 0.918, 0.941, 1.0)        # #E5EAF0 柔和浅灰边框
CLR_TEXT_MAIN = (0.133, 0.160, 0.200, 1.0)     # #222933 主文字
CLR_TEXT_MUTED = (0.540, 0.580, 0.630, 1.0)    # #8A94A0 次级灰字
CLR_PRICE_RED = (0.945, 0.243, 0.282, 1.0)     # #F13E48 售价醒目红
CLR_DEAL_BG = (0.902, 0.988, 0.961, 1.0)       # #E6FCF5 成交徽标绿底
CLR_DEAL_TXT = (0.047, 0.651, 0.471, 1.0)      # #0CA678 成交徽标绿字
CLR_DEAL_BORDER = (0.765, 0.980, 0.910, 1.0)   # #C3FAE8 成交边框
CLR_TAG_BG = (1.0, 0.941, 0.965, 1.0)          # #FFF0F6 优惠标签粉底
CLR_TAG_TXT = (0.902, 0.286, 0.502, 1.0)       # #E64980 优惠标签粉字
CLR_CHIP_BG = (0.935, 0.945, 0.960, 1.0)       # 筛选芯片默认灰底
CLR_CHIP_ACTIVE = (0.984, 0.447, 0.600, 1.0)   # 筛选芯片选中粉底
CLR_LINE = (0.920, 0.935, 0.950, 1.0)          # 分隔线颜色
CLR_TAB_INACTIVE = (0.55, 0.59, 0.63, 1.0)     # 底部未激活文字灰

Window.clearcolor = CLR_BG


def _parse_price(s):
    """提取价格浮点数，如 '¥47.80' -> 47.80，失败返回 None。"""
    try:
        return float(str(s).replace("¥", "").replace(",", "").strip())
    except Exception:
        return None


# =====================================================================
# 现代化基础通用组件
# =====================================================================

class RoundedBox(BoxLayout):
    """带圆角与平滑背景/边框的现代化容器控件。"""

    def __init__(self, bg_color=CLR_CARD, border_color=CLR_BORDER,
                 radius=dp(12), border_width=1, **kw):
        super().__init__(**kw)
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius = radius
        self.border_width = border_width
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            if self.border_color and self.border_width > 0:
                Color(*self.border_color)
                Line(rounded_rectangle=(self.pos[0], self.pos[1], self.size[0], self.size[1], self.radius),
                     width=self.border_width)


class ModernButton(Button):
    """具有圆角背景、按压视觉反馈与主题配色的现代按钮。"""

    def __init__(self, bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1),
                 radius=dp(8), border_color=None, border_width=0, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)  # 完全自绘
        self.normal_bg = bg_color
        self.down_bg = (bg_color[0] * 0.85, bg_color[1] * 0.85, bg_color[2] * 0.85, bg_color[3])
        self.text_color = text_color
        self.color = text_color
        self.radius = radius
        self.border_color = border_color
        self.border_width = border_width
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _redraw(self, *args):
        self.canvas.before.clear()
        bg = self.down_bg if self.state == "down" else self.normal_bg
        with self.canvas.before:
            Color(*bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            if self.border_color and self.border_width > 0:
                Color(*self.border_color)
                Line(rounded_rectangle=(self.pos[0], self.pos[1], self.size[0], self.size[1], self.radius),
                     width=self.border_width)


class FilterChip(Button):
    """筛选胶囊标签。"""

    def __init__(self, text, active=False, on_select=None, **kw):
        super().__init__(text=text, font_size=sp(12), size_hint=(None, None),
                         height=dp(30), padding=(dp(10), dp(4)), **kw)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.active = active
        self.on_select = on_select
        self.bind(size=self._calc_width, pos=self._redraw)
        self.bind(on_press=self._on_press)
        Clock.schedule_once(self._redraw, 0)

    def _calc_width(self, *args):
        self.width = max(dp(56), len(self.text) * dp(14) + dp(22))

    def _on_press(self, *args):
        if self.on_select:
            self.on_select(self)

    def set_active(self, val):
        self.active = val
        self._redraw()

    def _redraw(self, *args):
        self.canvas.before.clear()
        bg = CLR_CHIP_ACTIVE if self.active else CLR_CHIP_BG
        self.color = (1, 1, 1, 1) if self.active else CLR_TEXT_MAIN
        with self.canvas.before:
            Color(*bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])


# =====================================================================
# 商品卡片控件 (ProductCardWidget)
# =====================================================================

class ProductCardWidget(RoundedBox):
    """现代化商品卡片：缩略图 / 双行标题 / 售价 / 成交价徽标 / 原价 / 快捷直达。"""

    def __init__(self, product, on_open_detail=None, **kw):
        super().__init__(orientation="horizontal", padding=dp(10), spacing=dp(10),
                         size_hint_y=None, height=dp(108),
                         bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12), **kw)
        self.product = product
        self.on_open_detail = on_open_detail

        # 1. 左侧缩略图容器 (88x88dp)
        img_box = AnchorLayout(size_hint=(None, 1), width=dp(88))
        img_url = product.get("img") or "https://i0.hdslb.com/bfs/mall/mall/default.png"
        if img_url.startswith("//"):
            img_url = "https:" + img_url

        self.thumb = AsyncImage(source=img_url, size_hint=(None, None),
                                size=(dp(88), dp(88)), fit_mode="contain")
        img_box.add_widget(self.thumb)
        self.add_widget(img_box)

        # 2. 右侧信息主布局 (垂直排列)
        info_layout = BoxLayout(orientation="vertical", spacing=dp(3))

        # 标题 (最多两行，绑定宽度自适应换行)
        title_text = product.get("title") or "（未命名商品）"
        self.title_lbl = Label(text=title_text, font_size=sp(13), bold=True,
                               color=CLR_TEXT_MAIN, halign="left", valign="top",
                               size_hint_y=None, height=dp(36))
        self.title_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        info_layout.add_widget(self.title_lbl)

        # 标签行 (如 "最低价仅3件" / "3折神价")
        tags_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(18), spacing=dp(4))
        discount_tag = product.get("discount")
        ref_p = _parse_price(product.get("reference_price"))
        cur_p = _parse_price(product.get("price"))
        deal_p = _parse_price(product.get("latest_deal_price"))

        if discount_tag:
            tags_layout.add_widget(Label(text=discount_tag, font_size=sp(10),
                                         color=CLR_TAG_TXT, size_hint_x=None,
                                         width=min(dp(130), len(discount_tag) * dp(10) + dp(8))))

        if cur_p and ref_p and ref_p > 0 and (cur_p / ref_p) <= 0.3:
            tags_layout.add_widget(Label(text="🏷️ 3折神价", font_size=sp(10),
                                         color=(0.95, 0.55, 0.1, 1), size_hint_x=None, width=dp(60)))
        info_layout.add_widget(tags_layout)

        # 价格与成交徽标行
        price_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24), spacing=dp(6))
        price_str = product.get("price") or "¥--"
        price_row.add_widget(Label(text=price_str, font_size=sp(16), bold=True,
                                   color=CLR_PRICE_RED, size_hint_x=None, width=dp(64),
                                   halign="left", valign="middle"))

        # 成交价徽标
        deal_text = f"成交 {product.get('latest_deal_price')}" if deal_p else "查成交…"
        deal_color = CLR_DEAL_TXT if deal_p else CLR_TEXT_MUTED
        deal_lbl = Label(text=deal_text, font_size=sp(11), bold=True,
                         color=deal_color, size_hint_x=None, width=dp(96),
                         halign="left", valign="middle")
        price_row.add_widget(deal_lbl)

        # 原价划线
        if product.get("reference_price"):
            ref_lbl = Label(text=f"原价 {product.get('reference_price')}", font_size=sp(11),
                            color=CLR_TEXT_MUTED, size_hint_x=None, width=dp(80),
                            halign="left", valign="middle")
            price_row.add_widget(ref_lbl)

        info_layout.add_widget(price_row)
        self.add_widget(info_layout)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_open_detail:
                self.on_open_detail(self.product)
                return True
        return super().on_touch_down(touch)


# =====================================================================
# 商品详情弹窗 (ProductDetailModal)
# =====================================================================

class ProductDetailModal(ModalView):
    """商品走势、真实成交记录与规格详情弹窗。"""

    def __init__(self, product, on_price_updated=None, **kw):
        super().__init__(size_hint=(0.94, 0.88), auto_dismiss=True, **kw)
        self.background_color = (0, 0, 0, 0.5)
        self.product = product
        self.cluster_id = str(product.get("cluster_id") or "")
        self.on_price_updated = on_price_updated

        # 弹窗主卡片
        main_card = RoundedBox(orientation="vertical", padding=dp(16), spacing=dp(10),
                               bg_color=CLR_CARD, radius=dp(16))

        # 1. 顶部标题栏 + 关闭按钮
        top_bar = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        top_bar.add_widget(Label(text="商品市集行情与走势", font_size=sp(16), bold=True,
                                 color=CLR_TEXT_MAIN, halign="left", valign="middle"))
        close_btn = ModernButton(text="✕", font_size=sp(15), size_hint=(None, None),
                                 size=(dp(34), dp(34)), bg_color=CLR_CHIP_BG,
                                 text_color=CLR_TEXT_MAIN, radius=dp(17))
        close_btn.bind(on_press=lambda _b: self.dismiss())
        top_bar.add_widget(close_btn)
        main_card.add_widget(top_bar)

        # 2. 商品基础信息概览卡片
        summary_card = RoundedBox(orientation="horizontal", padding=dp(10), spacing=dp(10),
                                  size_hint_y=None, height=dp(94), bg_color=CLR_BG, radius=dp(10))
        img_url = product.get("img") or ""
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        thumb = AsyncImage(source=img_url, size_hint=(None, 1), width=dp(74),
                           fit_mode="contain")
        summary_card.add_widget(thumb)

        desc_box = BoxLayout(orientation="vertical", spacing=dp(3))
        title_lbl = Label(text=product.get("title", ""), font_size=sp(13), bold=True,
                          color=CLR_TEXT_MAIN, halign="left", valign="top",
                          size_hint_y=None, height=dp(36))
        title_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        desc_box.add_widget(title_lbl)

        # 当前价与最新成交对比
        cur_p = product.get("price") or "¥--"
        deal_p = product.get("latest_deal_price") or "暂无"
        price_line = f"当前在售: [b]{cur_p}[/b]   最近成交: [b]{deal_p}[/b]"
        self.summary_price_lbl = Label(text=price_line, markup=True, font_size=sp(12),
                                       color=CLR_PRIMARY, halign="left", valign="middle")
        desc_box.add_widget(self.summary_price_lbl)
        summary_card.add_widget(desc_box)
        main_card.add_widget(summary_card)

        # 3. 操作按钮行：刷新成交走势 + 直达 B 站市集
        btn_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
        self.refresh_btn = ModernButton(text="🔄 实时刷新成交明细", font_size=sp(13), bold=True,
                                        bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1), radius=dp(8))
        self.refresh_btn.bind(on_press=lambda _b: self._fetch_live_deals())
        btn_row.add_widget(self.refresh_btn)

        url_btn = ModernButton(text="🛒 直达B站市集", font_size=sp(13), bold=True,
                               bg_color=(0.15, 0.65, 0.95, 1), text_color=(1, 1, 1, 1), radius=dp(8))
        url_btn.bind(on_press=lambda _b: self._open_bili_url())
        btn_row.add_widget(url_btn)
        main_card.add_widget(btn_row)

        # 4. 可滚动的成交明细与属性列表
        scroll = ScrollView(size_hint=(1, 1))
        self.detail_content = BoxLayout(orientation="vertical", size_hint_y=None,
                                        spacing=dp(10), padding=(0, dp(4)))
        self.detail_content.bind(minimum_height=self.detail_content.setter("height"))

        # 初始加载提示
        self.status_lbl = Label(text="点击上方「实时刷新成交明细」拉取 B 站官方订单…",
                                font_size=sp(13), color=CLR_TEXT_MUTED, size_hint_y=None, height=dp(36))
        self.detail_content.add_widget(self.status_lbl)
        scroll.add_widget(self.detail_content)
        main_card.add_widget(scroll)

        self.add_widget(main_card)

        # 自动触发一次后台拉取
        Clock.schedule_once(lambda _dt: self._fetch_live_deals(), 0.1)

    def _open_bili_url(self):
        url = self.product.get("url")
        if not url and self.cluster_id:
            url = f"https://mall.bilibili.com/neul-next/resell/detail.html?noTitleBar=1&clusterId={self.cluster_id}"
        if url:
            try:
                webbrowser.open(url)
            except Exception as e:
                print(f"打开浏览器失败: {e}")

    def _fetch_live_deals(self):
        if not self.cluster_id:
            return
        self.refresh_btn.text = "拉取中…"
        self.status_lbl.text = "正在连接 B 站官方接口获取市集成交明细…"

        def worker():
            try:
                info = bili_resell.get_cluster_info(self.cluster_id)
                Clock.schedule_once(lambda dt: self._render_live_info(info), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._render_error(str(e)), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _render_error(self, err_msg):
        self.refresh_btn.text = "🔄 实时刷新成交明细"
        self.status_lbl.text = f"拉取失败: {err_msg}"

    def _render_live_info(self, info):
        self.refresh_btn.text = "🔄 实时刷新成交明细"
        if not info:
            self.status_lbl.text = "未获取到该商品的市集成交信息（可能暂无挂售或已下架）。"
            return

        self.detail_content.clear_widgets()

        # 更新最新成交价
        ldp = info.get("latest_deal_price")
        if ldp:
            self.product["latest_deal_price"] = ldp
            cur_p = self.product.get("price") or "¥--"
            self.summary_price_lbl.text = f"当前在售: [b]{cur_p}[/b]   最近成交: [b]{ldp}[/b]"
            if self.on_price_updated:
                self.on_price_updated(self.cluster_id, ldp)

        # 1. 近期买家成交订单明细 (Order List)
        deals = info.get("deals") or []
        deals_header = BoxLayout(size_hint_y=None, height=dp(28))
        deals_header.add_widget(Label(text=f"📋 近期买家成交订单 ({len(deals)} 笔)",
                                     font_size=sp(14), bold=True, color=CLR_TEXT_MAIN,
                                     halign="left", valign="middle"))
        self.detail_content.add_widget(deals_header)

        if deals:
            for d in deals:
                row = RoundedBox(orientation="horizontal", padding=(dp(12), dp(8)),
                                 size_hint_y=None, height=dp(44), bg_color=CLR_BG, radius=dp(8))
                u_name = d.get("userName") or "匿名买家"
                u_time = d.get("dealTime") or ""
                row.add_widget(Label(text=f"{u_name}  ({u_time})", font_size=sp(12),
                                     color=CLR_TEXT_MAIN, halign="left", valign="middle"))
                p_val = d.get("dealPrice") or "¥--"
                row.add_widget(Label(text=p_val, font_size=sp(14), bold=True,
                                     color=CLR_DEAL_TXT, halign="right", valign="middle"))
                self.detail_content.add_widget(row)
        else:
            self.detail_content.add_widget(Label(text="官方暂未开放近期待收单明细记录",
                                                 font_size=sp(12), color=CLR_TEXT_MUTED,
                                                 size_hint_y=None, height=dp(28)))

        # 2. 官方成交走势均价点 (Chart Points)
        points = info.get("chart_points") or []
        if points:
            pt_header = BoxLayout(size_hint_y=None, height=dp(28), padding=(0, dp(6)))
            pt_header.add_widget(Label(text=f"📈 官方成交均价走势 ({len(points)} 个节点)",
                                       font_size=sp(14), bold=True, color=CLR_TEXT_MAIN,
                                       halign="left", valign="middle"))
            self.detail_content.add_widget(pt_header)

            chart_box = RoundedBox(orientation="horizontal", padding=dp(10), spacing=dp(6),
                                   size_hint_y=None, height=dp(48), bg_color=CLR_PRIMARY_LIGHT, radius=dp(8))
            for pt in points[-5:]:  # 展示最近最多 5 个节点
                pt_date = pt.get("dateLabel") or ""
                pt_price = pt.get("avgPrice") or pt.get("price") or ""
                pt_lbl = Label(text=f"{pt_date}\n{pt_price}", font_size=sp(11),
                               bold=True, color=CLR_PRIMARY_DARK, halign="center")
                chart_box.add_widget(pt_lbl)
            self.detail_content.add_widget(chart_box)

        # 3. 商品规格属性 (Attributes)
        attrs = info.get("attributes") or []
        if attrs:
            attr_header = BoxLayout(size_hint_y=None, height=dp(28), padding=(0, dp(6)))
            attr_header.add_widget(Label(text="🔍 规格与属性", font_size=sp(14), bold=True,
                                         color=CLR_TEXT_MAIN, halign="left", valign="middle"))
            self.detail_content.add_widget(attr_header)

            for a in attrs:
                aname = a.get("attrName") or ""
                aval = a.get("attrValue") or ""
                arow = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
                arow.add_widget(Label(text=aname, font_size=sp(12), color=CLR_TEXT_MUTED,
                                      size_hint_x=0.35, halign="left", valign="middle"))
                arow.add_widget(Label(text=aval, font_size=sp(12), color=CLR_TEXT_MAIN,
                                      size_hint_x=0.65, halign="left", valign="middle"))
                self.detail_content.add_widget(arow)


# =====================================================================
# 底部现代导航栏 (ModernTabBar)
# =====================================================================

class ModernTabBar(RoundedBox):
    """具有指示器高亮与圆润胶囊形态的现代化底部导航栏。"""

    def __init__(self, app_ref, **kw):
        super().__init__(size_hint=(1, None), height=dp(56), padding=(dp(8), dp(4)),
                         spacing=dp(6), bg_color=CLR_CARD, border_color=CLR_BORDER,
                         radius=0, border_width=1, **kw)
        self.app_ref = app_ref
        self.tabs = [
            ("🏷️ 大盘", app_ref.show_list),
            ("🎯 雷达", app_ref.show_radar),
            ("⚡ 抓取", app_ref.show_crawl),
            ("⚙️ 设置", app_ref.show_settings),
        ]
        self.buttons = []
        for idx, (title, cb) in enumerate(self.tabs):
            btn = Button(text=title, font_size=sp(13), bold=True,
                         background_normal="", background_down="",
                         background_color=(0, 0, 0, 0))
            btn.bind(on_press=lambda _b, i=idx, f=cb: self._switch_tab(i, f))
            self.add_widget(btn)
            self.buttons.append(btn)
        self.set_active_index(0)

    def _switch_tab(self, index, callback):
        self.set_active_index(index)
        callback()

    def set_active_index(self, active_idx):
        for idx, btn in enumerate(self.buttons):
            if idx == active_idx:
                btn.color = CLR_PRIMARY
                btn.font_size = sp(14)
            else:
                btn.color = CLR_TAB_INACTIVE
                btn.font_size = sp(13)


# =====================================================================
# 应用核心逻辑 (ResellMonitorMobile)
# =====================================================================

class ResellMonitorMobile(App):
    title = "B站转售监控"

    def build(self):
        self.root_box = BoxLayout(orientation="vertical")

        # 顶部全局导航栏
        self.header_bar = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(52),
                                     padding=(dp(16), dp(8)), spacing=dp(8),
                                     bg_color=CLR_PRIMARY, radius=0, border_width=0)
        self.header_title = Label(text="📦 哔哩转售捡漏监控", font_size=sp(17), bold=True,
                                  color=(1, 1, 1, 1), halign="left", valign="middle")
        self.header_count_badge = Label(text="共 -- 件", font_size=sp(12),
                                        color=(1, 1, 1, 0.85), size_hint_x=None, width=dp(64))
        self.header_bar.add_widget(self.header_title)
        self.header_bar.add_widget(self.header_count_badge)
        self.root_box.add_widget(self.header_bar)

        # 中间内容区域
        self.content = BoxLayout(orientation="vertical", padding=(dp(10), dp(8)), spacing=dp(8))
        self.root_box.add_widget(self.content)

        # 底部导航栏
        self.tab_bar = ModernTabBar(self)
        self.root_box.add_widget(self.tab_bar)

        # 状态变量
        self.all_products = []
        self.filtered_products = []
        self.current_tab = "list"
        self.crawling = False
        self.active_filter = "all"
        self.active_sort = "default"
        self.search_keyword = ""
        self.page_render_limit = 50  # 初始渲染 50 条，防止低端机渲染 700 条造成卡顿

        # 启动时异步加载数据
        Clock.schedule_once(lambda _dt: self.show_list(), 0.1)
        return self.root_box

    # ---------- 数据读取与筛选 ----------
    def load_data(self):
        """读取本地商品快照与成交价缓存。"""
        self.all_products = []
        try:
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.all_products = data.get("products", data) if isinstance(data, dict) else data
        except Exception as e:
            print(f"[Warn] 读取商品库失败: {e}", file=sys.stderr)

        # 读取成交价缓存补全
        deals_cache = {}
        if os.path.exists(DEALS_CACHE_PATH):
            try:
                with open(DEALS_CACHE_PATH, "r", encoding="utf-8") as f:
                    deals_cache = json.load(f)
            except Exception:
                pass

        for p in self.all_products:
            cid = str(p.get("cluster_id") or "")
            if cid in deals_cache and deals_cache[cid].get("latest_deal_price"):
                p["latest_deal_price"] = deals_cache[cid]["latest_deal_price"]

        if hasattr(self, "header_count_badge") and self.header_count_badge:
            self.header_count_badge.text = f"共 {len(self.all_products)} 件"

    def apply_filters(self):
        """根据搜索词、筛选胶囊与排序模式过滤商品。"""
        items = list(self.all_products)

        # 1. 关键词搜索过滤
        if self.search_keyword:
            kw = self.search_keyword.strip().lower()
            items = [p for p in items if kw in str(p.get("title", "")).lower() or kw in str(p.get("cluster_id", ""))]

        # 2. 筛选标签过滤
        if self.active_filter == "below_deal":
            # 低于上次成交价
            def is_below(p):
                cur = _parse_price(p.get("price"))
                deal = _parse_price(p.get("latest_deal_price"))
                return cur and deal and cur < deal
            items = [p for p in items if is_below(p)]
        elif self.active_filter == "super_discount":
            # 3折神价
            def is_super(p):
                cur = _parse_price(p.get("price"))
                ref = _parse_price(p.get("reference_price"))
                return cur and ref and ref > 0 and (cur / ref) <= 0.3
            items = [p for p in items if is_super(p)]
        elif self.active_filter == "has_deal":
            items = [p for p in items if _parse_price(p.get("latest_deal_price"))]

        # 3. 排序模式
        if self.active_sort == "deal_gap":
            # 捡漏差额优先 (deal - cur) 越大越优先
            def gap_val(p):
                cur = _parse_price(p.get("price"))
                deal = _parse_price(p.get("latest_deal_price"))
                return (deal - cur) if (cur and deal) else -99999
            items.sort(key=gap_val, reverse=True)
        elif self.active_sort == "price_asc":
            items.sort(key=lambda p: _parse_price(p.get("price")) or 999999)
        elif self.active_sort == "price_desc":
            items.sort(key=lambda p: _parse_price(p.get("price")) or -1, reverse=True)
        elif self.active_sort == "discount_rate":
            def disc_rate(p):
                cur = _parse_price(p.get("price"))
                ref = _parse_price(p.get("reference_price"))
                return (cur / ref) if (cur and ref and ref > 0) else 999
            items.sort(key=disc_rate)

        self.filtered_products = items

    def _on_price_updated(self, cluster_id, new_price):
        """当单个商品详情弹窗获取到新价格时，同步回流更新主数据。"""
        for p in self.all_products:
            if str(p.get("cluster_id")) == str(cluster_id):
                p["latest_deal_price"] = new_price
                break

    # =====================================================================
    # 页面一：大盘列表 (show_list)
    # =====================================================================
    def show_list(self):
        self.current_tab = "list"
        self.content.clear_widgets()
        self.load_data()
        self.apply_filters()

        # 1. 搜索框与排序栏
        search_card = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(42),
                                 padding=(dp(10), dp(4)), spacing=dp(8),
                                 bg_color=CLR_CARD, radius=dp(10))

        search_input = TextInput(text=self.search_keyword, hint_text="🔍 输入商品标题或关键词搜索…",
                                 font_size=sp(13), multiline=False,
                                 background_normal="", background_active="",
                                 background_color=(0, 0, 0, 0), foreground_color=CLR_TEXT_MAIN,
                                 cursor_color=CLR_PRIMARY, size_hint=(1, 1))

        def _on_search_change(_inst, val):
            self.search_keyword = val
            self.page_render_limit = 50
            self.apply_filters()
            self._repopulate_list()

        search_input.bind(text=_on_search_change)
        search_card.add_widget(search_input)

        # 清除按钮
        if self.search_keyword:
            clear_btn = Button(text="✕", font_size=sp(12), size_hint=(None, 1), width=dp(28),
                               background_normal="", background_color=(0, 0, 0, 0), color=CLR_TEXT_MUTED)
            clear_btn.bind(on_press=lambda _b: setattr(search_input, 'text', ''))
            search_card.add_widget(clear_btn)

        self.content.add_widget(search_card)

        # 2. 筛选标签芯片栏
        filter_bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(32), spacing=dp(6))
        self.chip_all = FilterChip("全部", active=(self.active_filter == "all"),
                                   on_select=lambda _c: self._switch_filter("all"))
        self.chip_below = FilterChip("🔥 捡漏", active=(self.active_filter == "below_deal"),
                                     on_select=lambda _c: self._switch_filter("below_deal"))
        self.chip_super = FilterChip("🏷️ 3折神价", active=(self.active_filter == "super_discount"),
                                     on_select=lambda _c: self._switch_filter("super_discount"))
        self.chip_has = FilterChip("已查成交", active=(self.active_filter == "has_deal"),
                                   on_select=lambda _c: self._switch_filter("has_deal"))

        for c in (self.chip_all, self.chip_below, self.chip_super, self.chip_has):
            filter_bar.add_widget(c)

        # 排序下拉 Spinner
        sort_map_names = {
            "default": "默认排序",
            "deal_gap": "差价最大",
            "price_asc": "价格升序",
            "price_desc": "价格降序",
            "discount_rate": "折扣最大",
        }
        sort_spinner = Spinner(text=sort_map_names.get(self.active_sort, "默认排序"),
                               values=("默认排序", "差价最大", "价格升序", "价格降序", "折扣最大"),
                               size_hint=(None, 1), width=dp(88), font_size=sp(11),
                               background_normal="", background_color=CLR_CHIP_BG,
                               color=CLR_TEXT_MAIN)

        def _on_sort_change(_s, val):
            name_to_key = {v: k for k, v in sort_map_names.items()}
            self.active_sort = name_to_key.get(val, "default")
            self.page_render_limit = 50
            self.apply_filters()
            self._repopulate_list()

        sort_spinner.bind(text=_on_sort_change)
        filter_bar.add_widget(sort_spinner)
        self.content.add_widget(filter_bar)

        # 3. 统计计数行
        count_str = f"展示 {len(self.filtered_products)} 件商品"
        if len(self.filtered_products) < len(self.all_products):
            count_str += f" (从 {len(self.all_products)} 件中筛选)"
        self.filter_count_lbl = Label(text=count_str, font_size=sp(11), color=CLR_TEXT_MUTED,
                                      size_hint_y=None, height=dp(18), halign="left", valign="middle")
        self.content.add_widget(self.filter_count_lbl)

        # 4. 滚动商品列表
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.list_grid = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.list_grid.bind(minimum_height=self.list_grid.setter("height"))
        self.scroll_view.add_widget(self.list_grid)
        self.content.add_widget(self.scroll_view)

        self._repopulate_list()

    def _switch_filter(self, filter_key):
        self.active_filter = filter_key
        for k, chip in (("all", self.chip_all), ("below_deal", self.chip_below),
                        ("super_discount", self.chip_super), ("has_deal", self.chip_has)):
            chip.set_active(k == filter_key)
        self.page_render_limit = 50
        self.apply_filters()
        self._repopulate_list()

    def _repopulate_list(self):
        """填充商品卡片到列表。"""
        self.list_grid.clear_widgets()
        count_str = f"展示 {len(self.filtered_products)} 件商品"
        if len(self.filtered_products) < len(self.all_products):
            count_str += f" (从 {len(self.all_products)} 件中筛选)"
        self.filter_count_lbl.text = count_str

        if not self.filtered_products:
            self.list_grid.add_widget(Label(text="未找到匹配的商品\n可切换筛选标签或清除搜索词",
                                            font_size=sp(14), color=CLR_TEXT_MUTED,
                                            size_hint_y=None, height=dp(100), halign="center"))
            return

        visible_items = self.filtered_products[:self.page_render_limit]
        for p in visible_items:
            card = ProductCardWidget(p, on_open_detail=self.open_detail_modal)
            self.list_grid.add_widget(card)

        # 分批加载更多按钮
        if len(self.filtered_products) > self.page_render_limit:
            more_btn = ModernButton(
                text=f"加载更多 (已展示 {len(visible_items)}/{len(self.filtered_products)} 件)…",
                font_size=sp(13), bold=True, size_hint=(1, None), height=dp(42),
                bg_color=CLR_CARD, text_color=CLR_PRIMARY, radius=dp(10),
                border_color=CLR_BORDER, border_width=1
            )
            more_btn.bind(on_press=self._load_more_items)
            self.list_grid.add_widget(more_btn)

    def _load_more_items(self, *args):
        self.page_render_limit += 50
        self._repopulate_list()

    def open_detail_modal(self, product):
        modal = ProductDetailModal(product, on_price_updated=self._on_price_updated)
        modal.open()

    # =====================================================================
    # 页面二：捡漏雷达 (show_radar)
    # =====================================================================
    def show_radar(self):
        self.current_tab = "radar"
        self.content.clear_widgets()
        self.load_data()

        # 找出当前价格低于成交价的捡漏商品
        hot_deals = []
        for p in self.all_products:
            cur = _parse_price(p.get("price"))
            deal = _parse_price(p.get("latest_deal_price"))
            if cur and deal and cur < deal:
                gap = deal - cur
                pct = round((gap / deal) * 100, 1)
                hot_deals.append((p, gap, pct))

        # 按差额从大到小排序
        hot_deals.sort(key=lambda x: x[1], reverse=True)

        # 头部概览卡片
        banner = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(4),
                            size_hint=(1, None), height=dp(70),
                            bg_color=CLR_PRIMARY_LIGHT, radius=dp(12))
        banner.add_widget(Label(text=f"🎯 实时发现 {len(hot_deals)} 款捡漏商品！",
                                font_size=sp(16), bold=True, color=CLR_PRIMARY_DARK,
                                halign="left", valign="middle"))
        banner.add_widget(Label(text="当前在售价显著低于市集最新成交价，具有明确捡漏空间",
                                font_size=sp(11), color=CLR_TEXT_MUTED,
                                halign="left", valign="middle"))
        self.content.add_widget(banner)

        scroll = ScrollView(size_hint=(1, 1))
        grid = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))

        if not hot_deals:
            grid.add_widget(Label(text="暂未发现低于市集成交价的商品\n可在「大盘」页面点击任意商品拉取成交行情",
                                  font_size=sp(13), color=CLR_TEXT_MUTED,
                                  size_hint_y=None, height=dp(120), halign="center"))
        else:
            for item, gap, pct in hot_deals:
                card = ProductCardWidget(item, on_open_detail=self.open_detail_modal)
                grid.add_widget(card)

        scroll.add_widget(grid)
        self.content.add_widget(scroll)

    # =====================================================================
    # 页面三：实时抓取 (show_crawl)
    # =====================================================================
    def show_crawl(self):
        self.current_tab = "crawl"
        self.content.clear_widgets()
        self.load_data()

        # 1. 监控大盘指标卡片
        stats_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(8),
                                size_hint=(1, None), height=dp(116),
                                bg_color=CLR_CARD, radius=dp(12))
        stats_card.add_widget(Label(text="📊 本地监控数据库概览", font_size=sp(14),
                                    bold=True, color=CLR_TEXT_MAIN, halign="left", valign="middle"))

        prices = [_parse_price(p.get("price")) for p in self.all_products if _parse_price(p.get("price"))]
        avg_p = round(sum(prices) / len(prices), 1) if prices else 0
        min_p = min(prices) if prices else 0
        max_p = max(prices) if prices else 0

        grid_stats = GridLayout(cols=3, size_hint=(1, 1), spacing=dp(6))
        for k, v in (("商品总量", f"{len(self.all_products)} 件"),
                    ("平均价格", f"¥{avg_p}"),
                    ("最低价格", f"¥{min_p}")):
            box = BoxLayout(orientation="vertical", spacing=dp(2))
            box.add_widget(Label(text=k, font_size=sp(11), color=CLR_TEXT_MUTED))
            box.add_widget(Label(text=v, font_size=sp(14), bold=True, color=CLR_PRIMARY))
            grid_stats.add_widget(box)
        stats_card.add_widget(grid_stats)
        self.content.add_widget(stats_card)

        # 2. 抓取配置与触发卡片
        cfg_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10),
                              size_hint=(1, None), height=dp(148),
                              bg_color=CLR_CARD, radius=dp(12))

        cfg_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
        self.depth_spinner = Spinner(text="常规抓取 (15页)",
                                     values=("快速抓取 (5页)", "常规抓取 (15页)", "全量抓取 (50页)"),
                                     size_hint=(0.5, 1), font_size=sp(12),
                                     background_normal="", background_color=CLR_CHIP_BG,
                                     color=CLR_TEXT_MAIN)
        self.sort_spinner = Spinner(text="热门优先",
                                    values=("热门优先", "最多在售", "价格升序"),
                                    size_hint=(0.5, 1), font_size=sp(12),
                                    background_normal="", background_color=CLR_CHIP_BG,
                                    color=CLR_TEXT_MAIN)
        cfg_row.add_widget(self.depth_spinner)
        cfg_row.add_widget(self.sort_spinner)
        cfg_card.add_widget(cfg_row)

        self.crawl_btn = ModernButton(text="⚡ 启动后台抓取任务", font_size=sp(15), bold=True,
                                      size_hint=(1, None), height=dp(46),
                                      bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1), radius=dp(10))
        self.crawl_btn.bind(on_press=lambda _b: self._start_crawl())
        cfg_card.add_widget(self.crawl_btn)
        self.content.add_widget(cfg_card)

        # 3. 实时终端运行日志卡片
        log_card = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(6),
                              size_hint=(1, 1), bg_color=(0.12, 0.14, 0.18, 1.0),
                              radius=dp(12), border_color=None, border_width=0)
        log_header = BoxLayout(size_hint_y=None, height=dp(22))
        log_header.add_widget(Label(text="💻 运行日志终端", font_size=sp(12), bold=True,
                                    color=(0.7, 0.75, 0.8, 1), halign="left", valign="middle"))
        log_card.add_widget(log_header)

        self.log_scroll = ScrollView(size_hint=(1, 1))
        self.log_lbl = Label(text="[就绪] 点击「启动后台抓取任务」更新本地商品快照\n",
                             font_size=sp(11), color=(0.85, 0.9, 0.95, 1),
                             halign="left", valign="top", size_hint_y=None)
        self.log_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        self.log_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', max(dp(120), val[1])))
        self.log_scroll.add_widget(self.log_lbl)
        log_card.add_widget(self.log_scroll)
        self.content.add_widget(log_card)

    def _start_crawl(self):
        if self.crawling:
            return
        self.crawling = True
        self.crawl_btn.text = "抓取进行中…"
        self.crawl_btn.normal_bg = (0.5, 0.5, 0.5, 1)
        self.log_lbl.text = "[启动] 正在初始化爬虫会话，抓取 B 站转售市集…\n"

        depth_map = {"快速抓取 (5页)": 5, "常规抓取 (15页)": 15, "全量抓取 (50页)": 50}
        sort_map = {"热门优先": "hot", "最多在售": "mostListings", "价格升序": "priceFirst"}
        pages = depth_map.get(self.depth_spinner.text, 15)
        sort_mode = sort_map.get(self.sort_spinner.text, "hot")

        def append_log(msg):
            def _ui():
                self.log_lbl.text += f"{msg}\n"
                self.log_scroll.scroll_y = 0  # 自动滚至底部
            Clock.schedule_once(lambda dt: _ui(), 0)

        def worker():
            try:
                res = bili_resell.crawl_and_export(
                    pages=pages,
                    sort=sort_mode,
                    output_json=JSON_PATH,
                    history_csv=HISTORY_PATH,
                    log_callback=append_log,
                )
                msg = "抓取完成 ✓"
            except Exception as e:
                msg = f"抓取失败: {e}"
                append_log(f"[异常] {e}")

            def done():
                self.crawling = False
                self.crawl_btn.text = "⚡ 启动后台抓取任务"
                self.crawl_btn.normal_bg = CLR_PRIMARY
                self.load_data()
                self.toast(msg)

            Clock.schedule_once(lambda dt: done(), 0)

        threading.Thread(target=worker, daemon=True).start()

    # =====================================================================
    # 页面四：系统设置 (show_settings)
    # =====================================================================
    def show_settings(self):
        self.current_tab = "settings"
        self.content.clear_widgets()

        scroll = ScrollView(size_hint=(1, 1))
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12), padding=(0, dp(6)))
        box.bind(minimum_height=box.setter("height"))

        # 1. 存储与运行环境卡片
        env_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(8),
                              size_hint=(1, None), height=dp(140),
                              bg_color=CLR_CARD, radius=dp(12))
        env_card.add_widget(Label(text="📱 运行环境与存储", font_size=sp(14), bold=True,
                                  color=CLR_TEXT_MAIN, halign="left", valign="middle"))

        platform_str = "Android 移动终端" if IS_ANDROID else "桌面端模拟运行 (Windows/Mac/Linux)"
        env_card.add_widget(Label(text=f"平台: {platform_str}", font_size=sp(12),
                                  color=CLR_TEXT_MUTED, halign="left", valign="middle"))
        env_card.add_widget(Label(text=f"数据文件: {os.path.basename(JSON_PATH)}", font_size=sp(12),
                                  color=CLR_TEXT_MUTED, halign="left", valign="middle"))
        env_card.add_widget(Label(text=f"成交缓存: {os.path.basename(DEALS_CACHE_PATH)}", font_size=sp(12),
                                  color=CLR_TEXT_MUTED, halign="left", valign="middle"))
        box.add_widget(env_card)

        # 2. 局域网桌面同步卡片 (直接从同一 WiFi 电脑的 web_server 同步)
        sync_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10),
                               size_hint=(1, None), height=dp(152),
                               bg_color=CLR_CARD, radius=dp(12))
        sync_card.add_widget(Label(text="🌐 局域网电脑同步 (推荐)", font_size=sp(14), bold=True,
                                   color=CLR_TEXT_MAIN, halign="left", valign="middle"))
        sync_card.add_widget(Label(text="如电脑端已启动 web_server.py，可直接通过局域网极速同步数据",
                                   font_size=sp(11), color=CLR_TEXT_MUTED, halign="left", valign="middle"))

        sync_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        self.ip_input = TextInput(hint_text="http://192.168.x.x:8000",
                                  text="http://127.0.0.1:8000",
                                  font_size=sp(12), multiline=False,
                                  background_color=CLR_CHIP_BG, foreground_color=CLR_TEXT_MAIN,
                                  size_hint=(0.7, 1))
        sync_btn = ModernButton(text="极速同步", font_size=sp(13), bold=True,
                                bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1),
                                radius=dp(8), size_hint=(0.3, 1))
        sync_btn.bind(on_press=lambda _b: self._sync_from_desktop())
        sync_row.add_widget(self.ip_input)
        sync_row.add_widget(sync_btn)
        sync_card.add_widget(sync_row)
        box.add_widget(sync_card)

        # 3. 缓存管理卡片
        cache_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10),
                                size_hint=(1, None), height=dp(112),
                                bg_color=CLR_CARD, radius=dp(12))
        cache_card.add_widget(Label(text="🧹 缓存与数据维护", font_size=sp(14), bold=True,
                                    color=CLR_TEXT_MAIN, halign="left", valign="middle"))

        btn_grid = GridLayout(cols=2, size_hint=(1, 1), spacing=dp(8))
        clr_cache_btn = ModernButton(text="清除成交价缓存", font_size=sp(12),
                                     bg_color=CLR_CHIP_BG, text_color=CLR_TEXT_MAIN,
                                     radius=dp(8))
        clr_cache_btn.bind(on_press=lambda _b: self._clear_cache())

        reload_btn = ModernButton(text="重新载入本地数据", font_size=sp(12),
                                  bg_color=CLR_CHIP_BG, text_color=CLR_TEXT_MAIN,
                                  radius=dp(8))
        reload_btn.bind(on_press=lambda _b: self._reload_local())

        btn_grid.add_widget(clr_cache_btn)
        btn_grid.add_widget(reload_btn)
        cache_card.add_widget(btn_grid)
        box.add_widget(cache_card)

        # 4. 关于项目
        about_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(6),
                                size_hint=(1, None), height=dp(90),
                                bg_color=CLR_BG, radius=dp(12))
        about_card.add_widget(Label(text="Bilibili Resell Monitor Mobile v1.2.0",
                                    font_size=sp(12), bold=True, color=CLR_TEXT_MAIN))
        about_card.add_widget(Label(text="开源地址: github.com/zhou2228653446/bilibili-resell-monitor",
                                    font_size=sp(11), color=CLR_TEXT_MUTED))
        box.add_widget(about_card)

        scroll.add_widget(box)
        self.content.add_widget(scroll)

    def _clear_cache(self):
        try:
            if os.path.exists(DEALS_CACHE_PATH):
                os.remove(DEALS_CACHE_PATH)
            self.toast("成交价缓存已清理 ✓")
        except Exception as e:
            self.toast(f"清理失败: {e}")

    def _reload_local(self):
        self.load_data()
        self.toast(f"已重新载入 {len(self.all_products)} 件商品 ✓")

    def _sync_from_desktop(self):
        url = self.ip_input.text.strip().rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        target = f"{url}/api/data"

        def worker():
            import urllib.request
            try:
                req = urllib.request.Request(target, headers={"User-Agent": "BiliResellMobile"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    # 写回本地
                    with open(JSON_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                def ok():
                    self.load_data()
                    self.toast(f"同步成功！已载入 {len(self.all_products)} 件商品 ✓")

                Clock.schedule_once(lambda dt: ok(), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.toast(f"同步失败: {e}"), 0)

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 通用 Toast 提示 ----------
    def toast(self, msg):
        view = ModalView(size_hint=(0.75, None), height=dp(48), auto_dismiss=True)
        view.background_color = (0, 0, 0, 0)
        box = RoundedBox(orientation="horizontal", padding=(dp(16), dp(8)),
                         bg_color=(0.15, 0.18, 0.22, 0.95), radius=dp(24),
                         border_color=None, border_width=0)
        box.add_widget(Label(text=str(msg), font_size=sp(13), bold=True,
                             color=(1, 1, 1, 1), halign="center", valign="middle"))
        view.add_widget(box)
        view.open()
        Clock.schedule_once(lambda _dt: view.dismiss(), 2.2)


if __name__ == "__main__":
    ResellMonitorMobile().run()
