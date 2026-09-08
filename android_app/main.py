# -*- coding: utf-8 -*-
"""
B站会员购转售监控 - Android 端 (v1.4.0 现代化高刷流畅版)
特性:
1. 90Hz / 120Hz 高刷新率屏幕自适应调度
2. Canvas 指令持久化重构，滑动 0 内存抖动，极致流畅
3. 底部导航栏平滑滑动指示条与页面淡入渐变动效
4. 实时抓取支持多品类 (3C数码/手办/模型/周边/全部分类) 与多排序维度
5. 现代化视觉美化、精致标签与深色控制台终端
"""
import json
import os
import sys
import threading
import time
import urllib.request
import webbrowser

# ---- 1. 高刷新率配置与字体注册（置于其他 Kivy 模块导入之前） ----
from kivy.config import Config

# 解除 60 帧限制，启用 120Hz 高刷新率模式
Config.set("graphics", "maxfps", "120")

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "NotoSansCJKsc-Regular.otf")
if os.path.exists(_FONT_PATH):
    Config.set("kivy", "default_font",
               repr(["CJK", _FONT_PATH, _FONT_PATH, _FONT_PATH]))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.core.text import LabelBase
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.image import AsyncImage
from kivy.animation import Animation
from kivy.properties import NumericProperty

if os.path.exists(_FONT_PATH):
    LabelBase.register(name="CJK", fn_regular=_FONT_PATH,
                       fn_bold=_FONT_PATH, fn_italic=_FONT_PATH)

from android_compat import IS_ANDROID, get_out_path
import bili_resell

JSON_PATH = get_out_path("3c_products.json")
DEALS_CACHE_PATH = get_out_path("deals_cache.json")

# ---- 高级感主题色卡 ----
CLR_PRIMARY = (0.984, 0.447, 0.600, 1.0)       # #FB7299 B站主粉
CLR_PRIMARY_DARK = (0.860, 0.300, 0.460, 1.0)  # 深粉色
CLR_PRIMARY_BG = (1.0, 0.945, 0.965, 1.0)      # #FFF1F6 极浅粉底
CLR_BLUE = (0.137, 0.678, 0.898, 1.0)          # #23ADE5 B站蓝
CLR_BG = (0.960, 0.965, 0.975, 1.0)            # #F5F7FA 页面底灰
CLR_CARD = (1.0, 1.0, 1.0, 1.0)                # #FFFFFF 卡片纯白
CLR_BORDER = (0.910, 0.925, 0.945, 1.0)        # #E8ECF1 边框浅灰
CLR_TEXT_MAIN = (0.118, 0.141, 0.180, 1.0)     # #1E242E 主黑
CLR_TEXT_SUB = (0.333, 0.376, 0.435, 1.0)      # #55606F 次黑
CLR_TEXT_MUTED = (0.580, 0.624, 0.678, 1.0)    # #949FA7 弱灰
CLR_PRICE_RED = (0.945, 0.220, 0.260, 1.0)     # #F13842 醒目红
CLR_DEAL_TXT = (0.086, 0.647, 0.290, 1.0)      # #16A54A 绿色
CLR_DEAL_BG = (0.910, 0.984, 0.933, 1.0)       # #E8FAEE 绿底
CLR_CHIP_BG = (0.930, 0.941, 0.957, 1.0)       # 筛选芯片默认灰底
CLR_CHIP_TXT = (0.28, 0.32, 0.38, 1.0)
CLR_TAB_INACTIVE = (0.55, 0.59, 0.65, 1.0)

Window.clearcolor = CLR_BG

def _parse_price(s):
    try:
        return float(str(s).replace("¥", "").replace(",", "").strip())
    except Exception:
        return None

# =====================================================================
# 高性能持久化指令 UI 组件 (Zero Canvas Allocations on Scroll)
# =====================================================================

class RoundedBox(BoxLayout):
    """
    高性能圆角容器：指令只在 __init__ 创建一次，后续位置/尺寸变动仅更新属性，
    彻底杜绝滑动过程中高频 clear() 重建引起的 GC 卡顿与掉帧。
    """
    def __init__(self, bg_color=CLR_CARD, border_color=CLR_BORDER,
                 radius=dp(12), border_width=1, **kw):
        super().__init__(**kw)
        self._bg_color_val = list(bg_color)
        self._border_color_val = list(border_color) if border_color else None
        self._radius_val = radius
        self._border_width_val = border_width

        with self.canvas.before:
            self._bg_color_inst = Color(*self._bg_color_val)
            r_list = [self._radius_val] if isinstance(self._radius_val, (int, float)) else self._radius_val
            self._rect_inst = RoundedRectangle(pos=self.pos, size=self.size, radius=r_list)
            if self._border_color_val and self._border_width_val > 0:
                self._border_color_inst = Color(*self._border_color_val)
                self._line_inst = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius_val),
                    width=self._border_width_val
                )
            else:
                self._border_color_inst = None
                self._line_inst = None

        self.bind(pos=self._update_geometry, size=self._update_geometry)

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size
            if self._line_inst:
                self._line_inst.rounded_rectangle = (
                    self.x, self.y, self.width, self.height, self._radius_val
                )

    def set_bg_color(self, clr):
        self._bg_color_val = list(clr)
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = clr

    def set_border_color(self, clr):
        if self._border_color_inst:
            self._border_color_inst.rgba = clr


class ModernButton(Button):
    """
    高性能圆角按钮：状态切换仅更新 _bg_color_inst.rgba，
    完全杜绝重新绘制与 Canvas 抖动。
    """
    def __init__(self, bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1),
                 radius=dp(8), border_color=None, border_width=0, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.normal_bg = list(bg_color)
        self.down_bg = [bg_color[0] * 0.86, bg_color[1] * 0.86, bg_color[2] * 0.86, bg_color[3]]
        self.radius = radius
        self.border_color = list(border_color) if border_color else None
        self.border_width = border_width
        self.color = text_color

        with self.canvas.before:
            self._bg_color_inst = Color(*self.normal_bg)
            r_list = [self.radius] if isinstance(self.radius, (int, float)) else self.radius
            self._rect_inst = RoundedRectangle(pos=self.pos, size=self.size, radius=r_list)
            if self.border_color and self.border_width > 0:
                self._border_color_inst = Color(*self.border_color)
                self._line_inst = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius),
                    width=self.border_width
                )
            else:
                self._border_color_inst = None
                self._line_inst = None

        self.bind(pos=self._update_geometry, size=self._update_geometry, state=self._update_state)

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size
            if self._line_inst:
                self._line_inst.rounded_rectangle = (
                    self.x, self.y, self.width, self.height, self.radius
                )

    def _update_state(self, *args):
        if hasattr(self, "_bg_color_inst"):
            bg = self.down_bg if self.state == "down" else self.normal_bg
            self._bg_color_inst.rgba = bg

    def set_bg_color(self, clr):
        self.normal_bg = list(clr)
        self.down_bg = [clr[0] * 0.86, clr[1] * 0.86, clr[2] * 0.86, clr[3]]
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = self.normal_bg


class FilterChip(Button):
    """
    高性能筛选胶囊芯片：圆角 15dp，点击状态切换仅更新指令颜色。
    """
    def __init__(self, text, active=False, on_select=None, **kw):
        super().__init__(text=text, font_size=sp(12), size_hint=(None, None),
                         height=dp(30), padding=(dp(12), dp(4)), **kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.active = active
        self.on_select = on_select
        self._calc_width()

        with self.canvas.before:
            self._bg_color_inst = Color(*(CLR_PRIMARY if self.active else CLR_CHIP_BG))
            self._rect_inst = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])

        self.color = (1, 1, 1, 1) if self.active else CLR_CHIP_TXT
        self.bind(pos=self._update_geometry, size=self._update_geometry, on_press=self._on_press)

    def _calc_width(self):
        self.width = max(dp(54), len(self.text) * dp(13) + dp(24))

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size

    def _on_press(self, *args):
        if self.on_select:
            self.on_select(self)

    def set_active(self, val):
        self.active = val
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = CLR_PRIMARY if self.active else CLR_CHIP_BG
        self.color = (1, 1, 1, 1) if self.active else CLR_CHIP_TXT


# =====================================================================
# 商品卡片与详情弹窗组件
# =====================================================================

class ProductCardWidget(RoundedBox):
    """
    极速流畅商品卡片：层次分明、图片防越界、多状态标签与优雅间距。
    """
    def __init__(self, product, on_open_detail=None, **kw):
        super().__init__(orientation="horizontal", padding=dp(10), spacing=dp(10),
                         size_hint=(1, None), height=dp(116),
                         bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12), **kw)
        self.product = product
        self.on_open_detail = on_open_detail

        # 1. 缩略图底框 (96x96dp)
        thumb_frame = RoundedBox(size_hint=(None, None), size=(dp(96), dp(96)),
                                 bg_color=(0.96, 0.97, 0.98, 1),
                                 border_color=(0.91, 0.93, 0.95, 1),
                                 radius=dp(8), border_width=1)
        img_url = product.get("img") or "https://i0.hdslb.com/bfs/mall/mall/default.png"
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        self.thumb = AsyncImage(source=img_url, size_hint=(1, 1), fit_mode="contain")
        thumb_frame.add_widget(self.thumb)
        self.add_widget(thumb_frame)

        # 2. 右侧信息主布局 (垂直排列)
        info_layout = BoxLayout(orientation="vertical", spacing=dp(4), size_hint=(1, 1))

        # 标题 (限制最多 2 行)
        title_text = product.get("title") or "（未命名商品）"
        self.title_lbl = Label(
            text=title_text, font_size=sp(12.5), bold=True,
            color=CLR_TEXT_MAIN, halign="left", valign="top",
            size_hint=(1, None), height=dp(34),
            shorten=True, shorten_from="right", max_lines=2
        )
        self.title_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        info_layout.add_widget(self.title_lbl)

        # 标签行 (优惠标签 / 捡漏差额 / 3折神价)
        tags_layout = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(18), spacing=dp(4))
        discount_tag = product.get("discount")
        ref_p = _parse_price(product.get("reference_price"))
        cur_p = _parse_price(product.get("price"))
        deal_p = _parse_price(product.get("latest_deal_price"))

        if discount_tag:
            tag_box = RoundedBox(size_hint=(None, 1), width=min(dp(110), len(discount_tag) * dp(10) + dp(12)),
                                 bg_color=CLR_PRIMARY_BG, border_color=(1.0, 0.85, 0.9, 1),
                                 radius=dp(4), border_width=1)
            tag_box.add_widget(Label(text=discount_tag, font_size=sp(9.5), color=CLR_PRIMARY_DARK,
                                     halign="center", valign="middle"))
            tags_layout.add_widget(tag_box)

        if cur_p and ref_p and ref_p > 0 and (cur_p / ref_p) <= 0.3:
            s_box = RoundedBox(size_hint=(None, 1), width=dp(52),
                               bg_color=(1.0, 0.96, 0.90, 1), border_color=(1.0, 0.88, 0.75, 1),
                               radius=dp(4), border_width=1)
            s_box.add_widget(Label(text="3折神价", font_size=sp(9.5), color=(0.95, 0.5, 0.05, 1),
                                   halign="center", valign="middle"))
            tags_layout.add_widget(s_box)

        if cur_p and deal_p and cur_p < deal_p:
            gap = round(deal_p - cur_p, 1)
            gap_str = f"低于成交¥{gap:g}"
            g_box = RoundedBox(size_hint=(None, 1), width=min(dp(96), len(gap_str) * dp(10) + dp(10)),
                               bg_color=CLR_DEAL_BG, border_color=(0.75, 0.95, 0.82, 1),
                               radius=dp(4), border_width=1)
            g_box.add_widget(Label(text=gap_str, font_size=sp(9.5), bold=True,
                                   color=CLR_DEAL_TXT, halign="center", valign="middle"))
            tags_layout.add_widget(g_box)

        info_layout.add_widget(tags_layout)

        # 价格行
        price_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(26), spacing=dp(6))
        price_str = product.get("price") or "¥--"
        price_row.add_widget(Label(text=f"[b]{price_str}[/b]", markup=True, font_size=sp(16),
                                   color=CLR_PRICE_RED, size_hint=(None, 1), width=dp(66),
                                   halign="left", valign="middle"))

        # 最近成交标签
        if deal_p:
            deal_box = RoundedBox(size_hint=(None, 1), width=dp(80),
                                  bg_color=(0.95, 0.96, 0.97, 1), border_color=(0.88, 0.90, 0.93, 1),
                                  radius=dp(4), border_width=1)
            deal_box.add_widget(Label(text=f"成交 {product.get('latest_deal_price')}",
                                      font_size=sp(10), color=CLR_TEXT_SUB,
                                      halign="center", valign="middle"))
            price_row.add_widget(deal_box)

        # 原价
        if product.get("reference_price"):
            ref_lbl = Label(text=f"原价 {product.get('reference_price')}", font_size=sp(10),
                            color=CLR_TEXT_MUTED, size_hint=(1, 1),
                            halign="left", valign="middle")
            ref_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
            price_row.add_widget(ref_lbl)

        info_layout.add_widget(price_row)
        self.add_widget(info_layout)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["card_touch_down"] = touch.pos
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.ud.get("card_touch_down"):
            dx = abs(touch.x - touch.ud["card_touch_down"][0])
            dy = abs(touch.y - touch.ud["card_touch_down"][1])
            if dx < dp(10) and dy < dp(10) and self.collide_point(*touch.pos):
                if self.on_open_detail:
                    self.on_open_detail(self.product)
                return True
        return super().on_touch_up(touch)


class ProductDetailModal(ModalView):
    """
    商品详情弹窗：带有轻柔淡入动效、官方历史成交明细与走势图表。
    """
    def __init__(self, product, on_price_updated=None, **kw):
        super().__init__(size_hint=(0.94, 0.88), auto_dismiss=True, **kw)
        self.background_color = (0, 0, 0, 0)
        self.opacity = 0
        self.product = product
        self.cluster_id = str(product.get("cluster_id") or "")
        self.on_price_updated = on_price_updated

        # 弹窗主卡片
        main_card = RoundedBox(orientation="vertical", padding=dp(16), spacing=dp(10),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(16))

        # 1. 顶部标题栏 + 关闭按钮
        top_bar = BoxLayout(size_hint=(1, None), height=dp(34), spacing=dp(8))
        top_lbl = Label(text="商品行情与走势明细", font_size=sp(15), bold=True,
                        color=CLR_TEXT_MAIN, size_hint=(1, 1), halign="left", valign="middle")
        top_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        top_bar.add_widget(top_lbl)

        close_btn = ModernButton(text="关闭", font_size=sp(12), size_hint=(None, None),
                                 size=(dp(54), dp(30)), bg_color=CLR_CHIP_BG,
                                 text_color=CLR_TEXT_SUB, radius=dp(15))
        close_btn.bind(on_press=lambda _b: self.dismiss())
        top_bar.add_widget(close_btn)
        main_card.add_widget(top_bar)

        # 2. 头部缩略信息卡片
        summary_card = RoundedBox(orientation="horizontal", padding=dp(10), spacing=dp(10),
                                  size_hint=(1, None), height=dp(88),
                                  bg_color=CLR_BG, border_color=CLR_BORDER, radius=dp(10))
        img_url = product.get("img") or ""
        if img_url.startswith("//"):
            img_url = "https:" + img_url

        thumb_box = RoundedBox(size_hint=(None, None), size=(dp(68), dp(68)),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(6))
        thumb = AsyncImage(source=img_url, size_hint=(1, 1), fit_mode="contain")
        thumb_box.add_widget(thumb)
        summary_card.add_widget(thumb_box)

        desc_box = BoxLayout(orientation="vertical", spacing=dp(3), size_hint=(1, 1))
        title_lbl = Label(text=product.get("title", ""), font_size=sp(12), bold=True,
                          color=CLR_TEXT_MAIN, halign="left", valign="top",
                          size_hint=(1, None), height=dp(32),
                          shorten=True, shorten_from="right", max_lines=2)
        title_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        desc_box.add_widget(title_lbl)

        cur_p = product.get("price") or "¥--"
        deal_p = product.get("latest_deal_price") or "暂无"
        price_line = f"当前在售: [b]{cur_p}[/b]   最近成交: [b]{deal_p}[/b]"
        self.summary_price_lbl = Label(text=price_line, markup=True, font_size=sp(11.5),
                                       color=CLR_PRIMARY, halign="left", valign="middle",
                                       size_hint=(1, 1))
        self.summary_price_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        desc_box.add_widget(self.summary_price_lbl)
        summary_card.add_widget(desc_box)
        main_card.add_widget(summary_card)

        # 3. 快捷操作栏 (刷新成交 / 直达购买)
        btn_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(8))
        self.refresh_btn = ModernButton(text="实时刷新成交明细", font_size=sp(12.5), bold=True,
                                        bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1), radius=dp(8))
        self.refresh_btn.bind(on_press=lambda _b: self._fetch_live_deals())
        btn_row.add_widget(self.refresh_btn)

        url_btn = ModernButton(text="直达B站市集", font_size=sp(12.5), bold=True,
                               bg_color=CLR_BLUE, text_color=(1, 1, 1, 1), radius=dp(8))
        url_btn.bind(on_press=lambda _b: self._open_bili_url())
        btn_row.add_widget(url_btn)
        main_card.add_widget(btn_row)

        # 4. 可滚动的成交明细与属性列表
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                            scroll_distance=dp(5))
        self.detail_content = BoxLayout(orientation="vertical", size_hint_y=None,
                                        spacing=dp(8), padding=(0, dp(4)))
        self.detail_content.bind(minimum_height=self.detail_content.setter("height"))

        self.status_lbl = Label(text="点击上方「实时刷新成交明细」拉取 B 站官方订单…",
                                font_size=sp(12), color=CLR_TEXT_MUTED, size_hint_y=None, height=dp(32))
        self.detail_content.add_widget(self.status_lbl)
        scroll.add_widget(self.detail_content)
        main_card.add_widget(scroll)

        self.add_widget(main_card)
        Clock.schedule_once(lambda _dt: self._fetch_live_deals(), 0.1)

    def on_open(self):
        super().on_open()
        # 打开弹窗淡入动效
        Animation.stop_all(self)
        anim = Animation(opacity=1.0, background_color=(0, 0, 0, 0.65), d=0.22, t="out_quad")
        anim.start(self)

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
        self.refresh_btn.text = "实时刷新成交明细"
        self.status_lbl.text = f"拉取失败: {err_msg}"

    def _render_live_info(self, info):
        self.refresh_btn.text = "实时刷新成交明细"
        if not info:
            self.status_lbl.text = "未获取到该商品的市集成交信息（可能暂无挂售或已下架）。"
            return

        self.detail_content.clear_widgets()

        ldp = info.get("latest_deal_price")
        if ldp:
            self.product["latest_deal_price"] = ldp
            cur_p = self.product.get("price") or "¥--"
            self.summary_price_lbl.text = f"当前在售: [b]{cur_p}[/b]   最近成交: [b]{ldp}[/b]"
            if self.on_price_updated:
                self.on_price_updated(self.cluster_id, ldp)

        deals = info.get("deals") or []
        deals_header = BoxLayout(size_hint=(1, None), height=dp(26))
        dh_lbl = Label(text=f"近期买家成交订单 ({len(deals)} 笔)",
                       font_size=sp(13), bold=True, color=CLR_TEXT_MAIN,
                       size_hint=(1, 1), halign="left", valign="middle")
        dh_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        deals_header.add_widget(dh_lbl)
        self.detail_content.add_widget(deals_header)

        if deals:
            for d in deals:
                row = RoundedBox(orientation="horizontal", padding=(dp(12), dp(6)),
                                 size_hint=(1, None), height=dp(40),
                                 bg_color=CLR_BG, border_color=CLR_BORDER, radius=dp(8))
                u_name = d.get("userName") or "匿名买家"
                u_time = d.get("dealTime") or ""
                u_lbl = Label(text=f"{u_name} ({u_time})", font_size=sp(11.5),
                              color=CLR_TEXT_SUB, size_hint=(1, 1), halign="left", valign="middle")
                u_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
                row.add_widget(u_lbl)

                p_val = d.get("dealPrice") or "¥--"
                p_lbl = Label(text=p_val, font_size=sp(13.5), bold=True,
                              color=CLR_DEAL_TXT, size_hint=(None, 1), width=dp(70),
                              halign="right", valign="middle")
                row.add_widget(p_lbl)
                self.detail_content.add_widget(row)
        else:
            self.detail_content.add_widget(Label(text="官方暂未开放近期待收单明细记录",
                                                 font_size=sp(11.5), color=CLR_TEXT_MUTED,
                                                 size_hint_y=None, height=dp(28)))

        points = info.get("chart_points") or []
        if points:
            pt_header = BoxLayout(size_hint=(1, None), height=dp(26), padding=(0, dp(4)))
            pth_lbl = Label(text=f"官方成交均价走势 ({len(points)} 个节点)",
                            font_size=sp(13), bold=True, color=CLR_TEXT_MAIN,
                            size_hint=(1, 1), halign="left", valign="middle")
            pth_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
            pt_header.add_widget(pth_lbl)
            self.detail_content.add_widget(pt_header)

            chart_box = RoundedBox(orientation="horizontal", padding=dp(8), spacing=dp(6),
                                   size_hint=(1, None), height=dp(46),
                                   bg_color=CLR_PRIMARY_BG, border_color=(1.0, 0.85, 0.9, 1), radius=dp(8))
            for pt in points[-5:]:
                pt_date = pt.get("dateLabel") or ""
                pt_price = pt.get("avgPrice") or pt.get("price") or ""
                pt_lbl = Label(text=f"{pt_date}\n{pt_price}", font_size=sp(10),
                               bold=True, color=CLR_PRIMARY_DARK, halign="center")
                chart_box.add_widget(pt_lbl)
            self.detail_content.add_widget(chart_box)

        attrs = info.get("attributes") or []
        if attrs:
            attr_header = BoxLayout(size_hint=(1, None), height=dp(26), padding=(0, dp(4)))
            ath_lbl = Label(text="商品规格与属性", font_size=sp(13), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, 1), halign="left", valign="middle")
            ath_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
            attr_header.add_widget(ath_lbl)
            self.detail_content.add_widget(attr_header)

            for a in attrs:
                aname = a.get("attrName") or ""
                aval = a.get("attrValue") or ""
                arow = BoxLayout(size_hint=(1, None), height=dp(22), spacing=dp(8))
                an_lbl = Label(text=aname, font_size=sp(11), color=CLR_TEXT_MUTED,
                               size_hint=(0.35, 1), halign="left", valign="middle")
                an_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
                arow.add_widget(an_lbl)
                av_lbl = Label(text=aval, font_size=sp(11), color=CLR_TEXT_MAIN,
                               size_hint=(0.65, 1), halign="left", valign="middle")
                av_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
                arow.add_widget(av_lbl)
                self.detail_content.add_widget(arow)


# =====================================================================
# 丝滑滑动指示条底部导航栏 (ModernTabBar with Animation)
# =====================================================================

class ModernTabBar(BoxLayout):
    """
    带有平滑动效指示条的现代化底部导航栏：
    点击切换时，粉色胶囊通过 Animation(indicator_x) 丝滑平移，彻底告别生硬突兀。
    """
    indicator_x = NumericProperty(0)

    def __init__(self, app_ref, **kw):
        super().__init__(size_hint=(1, None), height=dp(54), padding=(dp(6), dp(2)),
                         spacing=dp(4), orientation="horizontal", **kw)
        self.app_ref = app_ref
        self.tabs = [
            ("市集大盘", app_ref.show_list),
            ("捡漏雷达", app_ref.show_radar),
            ("实时抓取", app_ref.show_crawl),
            ("系统设置", app_ref.show_settings),
        ]
        self.buttons = []
        self.active_index = 0
        self.indicator_width = dp(36)

        # 底部背景与上边框 (持久化指令)
        with self.canvas.before:
            Color(*CLR_CARD)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
            Color(*CLR_BORDER)
            self._border_line = Line(points=[self.x, self.top, self.right, self.top], width=1)

        # 平滑滑动指示条 (持久化指令)
        with self.canvas.after:
            Color(*CLR_PRIMARY)
            self._indicator = RoundedRectangle(
                pos=(self.x, self.y + dp(3)),
                size=(self.indicator_width, dp(3)),
                radius=[dp(1.5)]
            )

        self.bind(pos=self._update_bar_geometry, size=self._update_bar_geometry)

        for idx, (title, cb) in enumerate(self.tabs):
            btn = Button(text=title, font_size=sp(12.5), bold=False,
                         background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=CLR_TAB_INACTIVE)
            btn.bind(on_press=lambda _b, i=idx, f=cb: self._switch_tab(i, f))
            self.add_widget(btn)
            self.buttons.append(btn)

        Clock.schedule_once(lambda _dt: self.set_active_index(0, animate=False), 0)

    def on_indicator_x(self, inst, val):
        if hasattr(self, "_indicator"):
            self._indicator.pos = (val, self.y + dp(3))

    def _update_bar_geometry(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border_line.points = [self.x, self.top, self.right, self.top]
        self._position_indicator(self.active_index, animate=False)

    def _switch_tab(self, index, callback):
        if index == self.active_index:
            return
        self.set_active_index(index, animate=True)
        callback()

    def set_active_index(self, active_idx, animate=True):
        self.active_index = active_idx
        for idx, btn in enumerate(self.buttons):
            if idx == active_idx:
                btn.color = CLR_PRIMARY
                btn.bold = True
                btn.font_size = sp(13)
            else:
                btn.color = CLR_TAB_INACTIVE
                btn.bold = False
                btn.font_size = sp(12.5)
        self._position_indicator(active_idx, animate=animate)

    def _position_indicator(self, active_idx, animate=True):
        if 0 <= active_idx < len(self.buttons):
            btn = self.buttons[active_idx]
            if btn.width > 0:
                target_x = btn.x + (btn.width - self.indicator_width) / 2
                if animate:
                    Animation.stop_all(self)
                    anim = Animation(indicator_x=target_x, d=0.22, t="out_quad")
                    anim.start(self)
                else:
                    self.indicator_x = target_x


# =====================================================================
# 应用核心逻辑 (ResellMonitorMobile)
# =====================================================================

class ResellMonitorMobile(App):
    title = "B站转售监控"

    def build(self):
        self.root_box = BoxLayout(orientation="vertical")

        # 顶部全局导航栏 (B站粉 + 胶囊在售徽标)
        self.header_bar = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(50),
                                     padding=(dp(16), dp(8)), spacing=dp(8),
                                     bg_color=CLR_PRIMARY, radius=0, border_width=0)
        self.header_title = Label(text="哔哩转售捡漏监控", font_size=sp(16), bold=True,
                                  color=(1, 1, 1, 1), halign="left", valign="middle")
        self.header_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))

        badge_box = RoundedBox(size_hint=(None, None), size=(dp(88), dp(28)),
                               bg_color=(1, 1, 1, 0.22), border_color=(1, 1, 1, 0.4),
                               radius=dp(14), border_width=1)
        self.header_count_badge = Label(text="实时 --件", font_size=sp(11), bold=True,
                                        color=(1, 1, 1, 1), halign="center", valign="middle")
        badge_box.add_widget(self.header_count_badge)

        self.header_bar.add_widget(self.header_title)
        self.header_bar.add_widget(badge_box)
        self.root_box.add_widget(self.header_bar)

        # 中间内容区域 (带淡入动效的容器)
        self.content = BoxLayout(orientation="vertical", padding=(dp(12), dp(10)), spacing=dp(8))
        self.root_box.add_widget(self.content)

        # 底部平滑导航栏
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
        self.page_render_limit = 40

        # 抓取控制台配置（与电脑端对齐）
        self.crawl_category = "898"       # 默认 3C数码
        self.crawl_sort = "hot"           # 默认 综合推荐
        self.crawl_pages = 15             # 默认 常规 15页

        # 启动时加载列表
        Clock.schedule_once(lambda _dt: self.show_list(), 0.1)
        return self.root_box

    def on_start(self):
        """应用启动后尝试设置 Android 原生 120Hz 高刷新率调度。"""
        if IS_ANDROID:
            self._enable_android_high_refresh_rate()

    def _enable_android_high_refresh_rate(self):
        """利用 PyJNIus 申请 Android 系统窗口最高刷新率 (90Hz / 120Hz / 144Hz)。"""
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            window = activity.getWindow()
            layout_params = window.getAttributes()

            display = activity.getWindowManager().getDefaultDisplay()
            modes = display.getSupportedModes()
            if modes:
                best_mode = max(modes, key=lambda m: m.getRefreshRate())
                max_rr = float(best_mode.getRefreshRate())
                if max_rr > 60.0:
                    layout_params.preferredDisplayModeId = best_mode.getModeId()
                    layout_params.preferredRefreshRate = max_rr
                    window.setAttributes(layout_params)
                    print(f"[Android Display] 已成功激活高刷新率模式: {max_rr:.1f}Hz (Mode ID: {best_mode.getModeId()})")
                    return

            layout_params.preferredRefreshRate = 120.0
            window.setAttributes(layout_params)
            print("[Android Display] 已请求 120Hz 优先刷新率")
        except Exception as e:
            print(f"[Android Display] 高刷申请降级 (使用系统默认): {e}")

    # ---------- 屏幕平滑过渡切换 ----------
    def _switch_screen(self, screen_builder):
        """页面切换淡入过渡动画，消除画面硬切的生硬感。"""
        Animation.stop_all(self.content)
        self.content.opacity = 0
        self.content.clear_widgets()
        screen_builder()
        anim = Animation(opacity=1.0, d=0.20, t="out_quad")
        anim.start(self.content)

    # ---------- 数据读取与过滤 ----------
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

        deals_cache = {}
        if os.path.exists(DEALS_CACHE_PATH):
            try:
                with open(DEALS_CACHE_PATH, "r", encoding="utf-8") as f:
                    deals_cache = json.load(f)
            except Exception:
                deals_cache = {}

        for p in self.all_products:
            cid = str(p.get("cluster_id") or "")
            if cid in deals_cache and deals_cache[cid].get("latest_deal_price"):
                p["latest_deal_price"] = deals_cache[cid]["latest_deal_price"]

        if hasattr(self, "header_count_badge") and self.header_count_badge:
            self.header_count_badge.text = f"实时 {len(self.all_products)}件"

    def apply_filters(self):
        """根据搜索词、筛选胶囊与排序模式过滤商品。"""
        items = list(self.all_products)

        # 1. 关键词搜索
        if self.search_keyword:
            kw = self.search_keyword.strip().lower()
            items = [p for p in items if kw in str(p.get("title", "")).lower() or kw in str(p.get("cluster_id", ""))]

        # 2. 筛选标签过滤
        if self.active_filter == "below_deal":
            def is_below(p):
                cur = _parse_price(p.get("price"))
                deal = _parse_price(p.get("latest_deal_price"))
                return cur and deal and cur < deal
            items = [p for p in items if is_below(p)]
        elif self.active_filter == "super_discount":
            def is_super(p):
                cur = _parse_price(p.get("price"))
                ref = _parse_price(p.get("reference_price"))
                return cur and ref and ref > 0 and (cur / ref) <= 0.3
            items = [p for p in items if is_super(p)]
        elif self.active_filter == "has_deal":
            items = [p for p in items if _parse_price(p.get("latest_deal_price"))]

        # 3. 排序规则
        if self.active_sort == "deal_gap":
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
        for p in self.all_products:
            if str(p.get("cluster_id")) == str(cluster_id):
                p["latest_deal_price"] = new_price
                break

    # =====================================================================
    # 页面一：市集大盘 (show_list)
    # =====================================================================
    def show_list(self):
        self.current_tab = "list"
        self.tab_bar.set_active_index(0)
        self._switch_screen(self._build_list_screen)

    def _build_list_screen(self):
        self.load_data()
        self.apply_filters()

        # A. 搜索框 (优雅圆角白框)
        search_card = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(38),
                                 padding=(dp(12), dp(4)), spacing=dp(8),
                                 bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(19))
        search_lbl = Label(text="搜索", font_size=sp(11), bold=True,
                           color=CLR_PRIMARY, size_hint=(None, 1), width=dp(28))
        search_card.add_widget(search_lbl)

        search_input = TextInput(
            text=self.search_keyword, hint_text="输入商品标题、型号或关键词…",
            font_size=sp(12.5), multiline=False,
            background_normal="", background_active="",
            background_color=(0, 0, 0, 0), foreground_color=CLR_TEXT_MAIN,
            cursor_color=CLR_PRIMARY, size_hint=(1, 1),
            padding=(dp(4), dp(8), dp(4), dp(4))
        )

        def _on_search_change(_inst, val):
            self.search_keyword = val
            self.page_render_limit = 40
            self.apply_filters()
            self._repopulate_list()

        search_input.bind(text=_on_search_change)
        search_card.add_widget(search_input)

        if self.search_keyword:
            clear_btn = Button(text="清空", font_size=sp(11), size_hint=(None, 1), width=dp(36),
                               background_normal="", background_color=(0, 0, 0, 0), color=CLR_TEXT_MUTED)
            clear_btn.bind(on_press=lambda _b: setattr(search_input, 'text', ''))
            search_card.add_widget(clear_btn)

        self.content.add_widget(search_card)

        # B. 筛选标签芯片栏 (横向丝滑滑动条)
        chip_scroll = ScrollView(size_hint=(1, None), height=dp(32),
                                 do_scroll_x=True, do_scroll_y=False, bar_width=0,
                                 scroll_distance=dp(5))
        chip_box = BoxLayout(orientation="horizontal", size_hint_x=None, spacing=dp(8))
        chip_box.bind(minimum_width=chip_box.setter("width"))

        self.chip_all = FilterChip("全部", active=(self.active_filter == "all"),
                                   on_select=lambda _c: self._switch_filter("all"))
        self.chip_below = FilterChip("超值捡漏", active=(self.active_filter == "below_deal"),
                                     on_select=lambda _c: self._switch_filter("below_deal"))
        self.chip_super = FilterChip("3折神价", active=(self.active_filter == "super_discount"),
                                     on_select=lambda _c: self._switch_filter("super_discount"))
        self.chip_has = FilterChip("已查成交", active=(self.active_filter == "has_deal"),
                                   on_select=lambda _c: self._switch_filter("has_deal"))

        for c in (self.chip_all, self.chip_below, self.chip_super, self.chip_has):
            chip_box.add_widget(c)
        chip_scroll.add_widget(chip_box)
        self.content.add_widget(chip_scroll)

        # C. 统计与排序子栏
        meta_bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(24))
        count_str = f"展示 {len(self.filtered_products)} 件商品"
        if len(self.filtered_products) < len(self.all_products):
            count_str += f" (总计 {len(self.all_products)} 件)"
        self.filter_count_lbl = Label(text=count_str, font_size=sp(11), color=CLR_TEXT_MUTED,
                                      size_hint=(1, 1), halign="left", valign="middle")
        self.filter_count_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        meta_bar.add_widget(self.filter_count_lbl)

        sort_map_names = {
            "default": "默认排序",
            "deal_gap": "差价最大",
            "price_asc": "价格升序",
            "price_desc": "价格降序",
            "discount_rate": "折扣最大",
        }
        sort_spinner = Spinner(text=sort_map_names.get(self.active_sort, "默认排序"),
                               values=("默认排序", "差价最大", "价格升序", "价格降序", "折扣最大"),
                               size_hint=(None, 1), width=dp(86), font_size=sp(10.5),
                               background_normal="", background_color=CLR_CHIP_BG,
                               color=CLR_TEXT_SUB)

        def _on_sort_change(_s, val):
            name_to_key = {v: k for k, v in sort_map_names.items()}
            self.active_sort = name_to_key.get(val, "default")
            self.page_render_limit = 40
            self.apply_filters()
            self._repopulate_list()

        sort_spinner.bind(text=_on_sort_change)
        meta_bar.add_widget(sort_spinner)
        self.content.add_widget(meta_bar)

        # D. 高帧率平滑滚动商品列表
        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                                      scroll_distance=dp(5),
                                      smooth_scroll_end=12, bar_width=dp(3),
                                      bar_color=(0.984, 0.447, 0.600, 0.35))
        self.list_grid = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.list_grid.bind(minimum_height=self.list_grid.setter("height"))
        self.scroll_view.add_widget(self.list_grid)
        self.content.add_widget(self.scroll_view)

        self._repopulate_list()

    def _switch_filter(self, filter_key):
        self.active_filter = filter_key
        for k, chip in (("all", self.chip_all), ("below_deal", self.chip_below),
                        ("super_discount", self.chip_super), ("has_deal", self.chip_has)):
            chip.set_active(k == filter_key)
        self.page_render_limit = 40
        self.apply_filters()
        self._repopulate_list()

    def _repopulate_list(self):
        self.list_grid.clear_widgets()
        count_str = f"展示 {len(self.filtered_products)} 件商品"
        if len(self.filtered_products) < len(self.all_products):
            count_str += f" (总计 {len(self.all_products)} 件)"
        self.filter_count_lbl.text = count_str

        if not self.filtered_products:
            empty_box = RoundedBox(orientation="vertical", size_hint=(1, None), height=dp(140),
                                   padding=dp(20), spacing=dp(8), bg_color=CLR_CARD)
            empty_box.add_widget(Label(text="未找到匹配的商品", font_size=sp(14), bold=True,
                                       color=CLR_TEXT_MAIN, halign="center"))
            empty_box.add_widget(Label(text="可尝试切换顶部筛选标签或清空搜索关键词",
                                       font_size=sp(12), color=CLR_TEXT_MUTED, halign="center"))
            self.list_grid.add_widget(empty_box)
            return

        visible_items = self.filtered_products[:self.page_render_limit]
        for p in visible_items:
            card = ProductCardWidget(p, on_open_detail=self.open_detail_modal)
            self.list_grid.add_widget(card)

        if len(self.filtered_products) > self.page_render_limit:
            more_btn = ModernButton(
                text=f"加载更多 (已展示 {len(visible_items)}/{len(self.filtered_products)} 件)…",
                font_size=sp(12.5), bold=True, size_hint=(1, None), height=dp(40),
                bg_color=CLR_CARD, text_color=CLR_PRIMARY, radius=dp(10),
                border_color=CLR_BORDER, border_width=1
            )
            more_btn.bind(on_press=self._load_more_items)
            self.list_grid.add_widget(more_btn)

    def _load_more_items(self, *args):
        self.page_render_limit += 40
        self._repopulate_list()

    def open_detail_modal(self, product):
        modal = ProductDetailModal(product, on_price_updated=self._on_price_updated)
        modal.open()

    # =====================================================================
    # 页面二：捡漏雷达 (show_radar)
    # =====================================================================
    def show_radar(self):
        self.current_tab = "radar"
        self.tab_bar.set_active_index(1)
        self._switch_screen(self._build_radar_screen)

    def _build_radar_screen(self):
        self.load_data()

        hot_deals = []
        for p in self.all_products:
            cur = _parse_price(p.get("price"))
            deal = _parse_price(p.get("latest_deal_price"))
            if cur and deal and cur < deal:
                gap = round(deal - cur, 1)
                pct = round((gap / deal) * 100, 1)
                hot_deals.append((p, gap, pct))

        hot_deals.sort(key=lambda x: x[1], reverse=True)

        banner = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(4),
                            size_hint=(1, None), height=dp(72),
                            bg_color=CLR_PRIMARY_BG, border_color=(1.0, 0.85, 0.9, 1), radius=dp(12))
        banner.add_widget(Label(text="超值捡漏雷达", font_size=sp(15), bold=True,
                                color=CLR_PRIMARY_DARK, halign="left", valign="middle"))
        banner.add_widget(Label(text=f"共发现 {len(hot_deals)} 件当前售价低于市集成交价的超值好物",
                                font_size=sp(11.5), color=CLR_TEXT_SUB, halign="left", valign="middle"))
        self.content.add_widget(banner)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                            scroll_distance=dp(5),
                            bar_width=dp(3), bar_color=(0.984, 0.447, 0.600, 0.35))
        list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        list_box.bind(minimum_height=list_box.setter("height"))

        if hot_deals:
            for item, gap, pct in hot_deals:
                card = ProductCardWidget(item, on_open_detail=self.open_detail_modal)
                list_box.add_widget(card)
        else:
            empty_card = RoundedBox(orientation="vertical", padding=dp(24), spacing=dp(8),
                                    size_hint=(1, None), height=dp(160), bg_color=CLR_CARD)
            empty_card.add_widget(Label(text="暂未发现低于成交价的捡漏商品", font_size=sp(14), bold=True,
                                        color=CLR_TEXT_MAIN, halign="center"))
            empty_card.add_widget(Label(text="可前往「市集大盘」点击商品卡片拉取官方成交价，\n或在「实时抓取」中获取更多最新商品。",
                                        font_size=sp(12), color=CLR_TEXT_MUTED, halign="center"))
            list_box.add_widget(empty_card)

        scroll.add_widget(list_box)
        self.content.add_widget(scroll)

    # =====================================================================
    # 页面三：实时抓取控制台 (show_crawl - 电脑端对齐品类/排序/深度)
    # =====================================================================
    def show_crawl(self):
        self.current_tab = "crawl"
        self.tab_bar.set_active_index(2)
        self._switch_screen(self._build_crawl_screen)

    def _build_crawl_screen(self):
        self.load_data()

        prices = [_parse_price(p.get("price")) for p in self.all_products if _parse_price(p.get("price"))]
        avg_p = f"¥{sum(prices)/len(prices):.1f}" if prices else "¥--"
        min_p = f"¥{min(prices):.1f}" if prices else "¥--"

        # 1. 统计卡片指标行
        kpi_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(64), spacing=dp(8))
        kpi_data = [
            ("在售总量", f"{len(self.all_products)} 件", CLR_PRIMARY),
            ("大盘均价", avg_p, CLR_BLUE),
            ("最低现价", min_p, CLR_PRICE_RED),
        ]
        for label_text, val_text, val_clr in kpi_data:
            box = RoundedBox(orientation="vertical", padding=(dp(8), dp(6)), spacing=dp(2),
                             bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(10))
            box.add_widget(Label(text=label_text, font_size=sp(11), color=CLR_TEXT_MUTED, halign="center"))
            box.add_widget(Label(text=val_text, font_size=sp(15), bold=True, color=val_clr, halign="center"))
            kpi_row.add_widget(box)
        self.content.add_widget(kpi_row)

        # 2. 抓取参数配置卡片 (多品类 + 多排序 + 翻页深度)
        cfg_panel = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(8),
                               size_hint=(1, None), height=dp(170),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))

        # A. 分类维度选择 (对齐电脑端 898/142/807/175/all)
        cat_scroll = ScrollView(size_hint=(1, None), height=dp(28),
                                do_scroll_x=True, do_scroll_y=False, bar_width=0)
        cat_box = BoxLayout(orientation="horizontal", size_hint_x=None, spacing=dp(6))
        cat_box.bind(minimum_width=cat_box.setter("width"))

        cat_lbl = Label(text="品类:", font_size=sp(11.5), bold=True, color=CLR_TEXT_MAIN,
                        size_hint=(None, 1), width=dp(36))
        cat_box.add_widget(cat_lbl)

        self.cat_chip_btns = []
        categories = [
            ("3C数码", "898"),
            ("模玩手办", "142"),
            ("拼装模型", "807"),
            ("动漫周边", "175"),
            ("全站商品", "all"),
        ]
        for name, cid in categories:
            is_active = (self.crawl_category == cid)
            c_btn = ModernButton(
                text=name, font_size=sp(11), size_hint=(None, 1), width=dp(68),
                bg_color=CLR_PRIMARY if is_active else CLR_CHIP_BG,
                text_color=(1, 1, 1, 1) if is_active else CLR_TEXT_SUB,
                radius=dp(6)
            )
            c_btn.bind(on_press=lambda _b, code=cid: self._set_crawl_category(code))
            cat_box.add_widget(c_btn)
            self.cat_chip_btns.append((cid, c_btn))

        cat_scroll.add_widget(cat_box)
        cfg_panel.add_widget(cat_scroll)

        # B. 排序规则选择 (对齐电脑端 hot/mostListings/priceFirst)
        sort_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(28), spacing=dp(6))
        sort_lbl = Label(text="排序:", font_size=sp(11.5), bold=True, color=CLR_TEXT_MAIN,
                         size_hint=(None, 1), width=dp(36))
        sort_row.add_widget(sort_lbl)

        self.sort_chip_btns = []
        sort_options = [
            ("综合最热", "hot"),
            ("挂售最多", "mostListings"),
            ("价格最低", "priceFirst"),
        ]
        for sname, scode in sort_options:
            is_active = (self.crawl_sort == scode)
            s_btn = ModernButton(
                text=sname, font_size=sp(11), size_hint=(1, 1),
                bg_color=CLR_PRIMARY if is_active else CLR_CHIP_BG,
                text_color=(1, 1, 1, 1) if is_active else CLR_TEXT_SUB,
                radius=dp(6)
            )
            s_btn.bind(on_press=lambda _b, code=scode: self._set_crawl_sort(code))
            sort_row.add_widget(s_btn)
            self.sort_chip_btns.append((scode, s_btn))
        cfg_panel.add_widget(sort_row)

        # C. 深度选择 (5页 / 15页 / 50页 / 全量)
        depth_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(28), spacing=dp(6))
        depth_lbl = Label(text="深度:", font_size=sp(11.5), bold=True, color=CLR_TEXT_MAIN,
                          size_hint=(None, 1), width=dp(36))
        depth_row.add_widget(depth_lbl)

        self.page_btns = []
        depth_options = [
            (5, "5页"),
            (15, "15页"),
            (50, "50页"),
            (None, "全量防漏"),
        ]
        for pg_num, pg_label in depth_options:
            is_active = (self.crawl_pages == pg_num)
            p_btn = ModernButton(
                text=pg_label, font_size=sp(11), size_hint=(1, 1),
                bg_color=CLR_PRIMARY if is_active else CLR_CHIP_BG,
                text_color=(1, 1, 1, 1) if is_active else CLR_TEXT_SUB,
                radius=dp(6)
            )
            p_btn.bind(on_press=lambda _b, n=pg_num: self._set_crawl_pages(n))
            depth_row.add_widget(p_btn)
            self.page_btns.append((pg_num, p_btn))
        cfg_panel.add_widget(depth_row)

        # D. 开始执行按钮
        self.crawl_action_btn = ModernButton(
            text="开始实时抓取数据", font_size=sp(13.5), bold=True,
            size_hint=(1, None), height=dp(36),
            bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1), radius=dp(8)
        )
        self.crawl_action_btn.bind(on_press=lambda _b: self._start_crawl())
        cfg_panel.add_widget(self.crawl_action_btn)
        self.content.add_widget(cfg_panel)

        # 3. 现代化深色控制台终端
        term_card = RoundedBox(orientation="vertical", padding=dp(10), spacing=dp(4),
                               size_hint=(1, 1), bg_color=(0.06, 0.08, 0.12, 1.0),
                               border_color=(0.16, 0.20, 0.28, 1.0), radius=dp(10))

        term_top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20), spacing=dp(6))
        term_dot = Label(text="●", font_size=sp(10), color=(0.2, 0.8, 0.4, 1), size_hint=(None, 1), width=dp(14))
        term_title = Label(text="实时控制台输出 (Terminal Log)", font_size=sp(11), bold=True,
                           color=(0.7, 0.78, 0.88, 1), size_hint=(1, 1), halign="left")
        term_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        term_top.add_widget(term_dot)
        term_top.add_widget(term_title)
        term_card.add_widget(term_top)

        self.crawl_log_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                                           scroll_distance=dp(5))
        cat_str = self._get_cat_name(self.crawl_category)
        self.crawl_log_lbl = Label(
            text=f"系统准备就绪。\n当前配置: 品类={cat_str} | 排序={self._get_sort_name(self.crawl_sort)} | 深度={self.crawl_pages or '全量'}\n点击上方「开始实时抓取数据」启动爬虫。",
            font_size=sp(11), color=(0.4, 0.88, 0.55, 1.0),
            size_hint_y=None, halign="left", valign="top"
        )
        self.crawl_log_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        self.crawl_log_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', max(dp(80), val[1])))
        self.crawl_log_scroll.add_widget(self.crawl_log_lbl)
        term_card.add_widget(self.crawl_log_scroll)
        self.content.add_widget(term_card)

    def _get_cat_name(self, cid):
        names = {"898": "3C数码", "142": "模玩手办", "807": "拼装模型", "175": "动漫周边", "all": "全站商品"}
        return names.get(str(cid), str(cid))

    def _get_sort_name(self, scode):
        names = {"hot": "综合最热", "mostListings": "挂售最多", "priceFirst": "价格最低"}
        return names.get(scode, scode)

    def _set_crawl_category(self, cid):
        self.crawl_category = cid
        for code, btn in self.cat_chip_btns:
            active = (code == cid)
            btn.set_bg_color(CLR_PRIMARY if active else CLR_CHIP_BG)
            btn.color = (1, 1, 1, 1) if active else CLR_TEXT_SUB

    def _set_crawl_sort(self, scode):
        self.crawl_sort = scode
        for code, btn in self.sort_chip_btns:
            active = (code == scode)
            btn.set_bg_color(CLR_PRIMARY if active else CLR_CHIP_BG)
            btn.color = (1, 1, 1, 1) if active else CLR_TEXT_SUB

    def _set_crawl_pages(self, num):
        self.crawl_pages = num
        for pg_num, btn in self.page_btns:
            active = (pg_num == num)
            btn.set_bg_color(CLR_PRIMARY if active else CLR_CHIP_BG)
            btn.color = (1, 1, 1, 1) if active else CLR_TEXT_SUB

    def _start_crawl(self):
        if self.crawling:
            return
        self.crawling = True
        self.crawl_action_btn.text = "正在抓取中，请稍候…"
        self.crawl_action_btn.set_bg_color((0.6, 0.6, 0.6, 1))

        cat_title = self._get_cat_name(self.crawl_category)
        sort_title = self._get_sort_name(self.crawl_sort)
        depth_title = f"{self.crawl_pages}页" if self.crawl_pages else "全量防漏模式"

        self.crawl_log_lbl.text = (
            f"[启动] 开始从 B 站会员购抓取【{cat_title}】转售商品…\n"
            f"       排序模式: {sort_title} | 深度: {depth_title}\n"
            f"       正在建立网络连接并获取设备指纹…\n"
        )

        def log_cb(msg):
            Clock.schedule_once(lambda dt: self._append_crawl_log(msg), 0)

        def worker():
            try:
                res = bili_resell.crawl_and_export(
                    category=self.crawl_category,
                    sort=self.crawl_sort,
                    pages=self.crawl_pages,
                    output_json=JSON_PATH,
                    log_callback=log_cb
                )
                err = res.get("error") if isinstance(res, dict) else None
                if err:
                    log_cb(f"\n[失败] 抓取遇到问题: {err}")
                else:
                    tot = res.get("total", 0) if isinstance(res, dict) else 0
                    log_cb(f"\n[完成] 本轮数据抓取入库完成！本次累计去重商品 {tot} 条。")
            except Exception as e:
                log_cb(f"\n[异常] 抓取失败: {e}")
            finally:
                self.crawling = False
                Clock.schedule_once(lambda dt: self._crawl_done(), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _append_crawl_log(self, msg):
        self.crawl_log_lbl.text += str(msg) + "\n"
        # 自动平滑滚动到底部
        if hasattr(self, "crawl_log_scroll") and self.crawl_log_scroll:
            Clock.schedule_once(lambda _dt: setattr(self.crawl_log_scroll, "scroll_y", 0), 0.05)

    def _crawl_done(self):
        if hasattr(self, "crawl_action_btn") and self.crawl_action_btn:
            self.crawl_action_btn.text = "开始实时抓取数据"
            self.crawl_action_btn.set_bg_color(CLR_PRIMARY)
        self.load_data()

    # =====================================================================
    # 页面四：系统设置与同步 (show_settings)
    # =====================================================================
    def show_settings(self):
        self.current_tab = "settings"
        self.tab_bar.set_active_index(3)
        self._switch_screen(self._build_settings_screen)

    def _build_settings_screen(self):
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                            scroll_distance=dp(5))
        set_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12))
        set_box.bind(minimum_height=set_box.setter("height"))

        sync_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10),
                               size_hint=(1, None), height=dp(168),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))
        sync_title = Label(text="局域网电脑数据同步", font_size=sp(14), bold=True,
                           color=CLR_TEXT_MAIN, size_hint=(1, None), height=dp(22), halign="left")
        sync_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        sync_card.add_widget(sync_title)

        sync_desc = Label(text="手机与运行 web_server.py 的电脑处于同一 Wi-Fi 时，可直接输入电脑 IP 同步最新大盘与成交缓存。",
                          font_size=sp(11.5), color=CLR_TEXT_MUTED, size_hint=(1, None), height=dp(34),
                          halign="left")
        sync_desc.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        sync_card.add_widget(sync_desc)

        ip_box = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(38),
                            padding=(dp(10), dp(4)), bg_color=CLR_BG, radius=dp(8))
        self.ip_input = TextInput(
            text="192.168.1.100:8000", hint_text="输入电脑 IP:端口",
            font_size=sp(13), multiline=False,
            background_normal="", background_active="",
            background_color=(0, 0, 0, 0), foreground_color=CLR_TEXT_MAIN,
            size_hint=(1, 1), padding=(dp(4), dp(8), dp(4), dp(4))
        )
        ip_box.add_widget(self.ip_input)
        sync_card.add_widget(ip_box)

        self.sync_btn = ModernButton(
            text="从电脑极速同步数据", font_size=sp(12.5), bold=True,
            size_hint=(1, None), height=dp(36),
            bg_color=CLR_BLUE, text_color=(1, 1, 1, 1), radius=dp(8)
        )
        self.sync_btn.bind(on_press=lambda _b: self._sync_from_pc())
        sync_card.add_widget(self.sync_btn)
        set_box.add_widget(sync_card)

        cache_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10),
                                size_hint=(1, None), height=dp(110),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))
        cache_title = Label(text="存储与缓存管理", font_size=sp(14), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, None), height=dp(22), halign="left")
        cache_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        cache_card.add_widget(cache_title)

        cache_desc = Label(text="清除本地保存的市集成交价缓存，下次点击商品详情时将重新从官方获取。",
                           font_size=sp(11.5), color=CLR_TEXT_MUTED, size_hint=(1, None), height=dp(20),
                           halign="left")
        cache_desc.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        cache_card.add_widget(cache_desc)

        self.clear_cache_btn = ModernButton(
            text="清除本地成交价缓存", font_size=sp(12.5), bold=True,
            size_hint=(1, None), height=dp(34),
            bg_color=CLR_CHIP_BG, text_color=CLR_TEXT_MAIN, radius=dp(8)
        )
        self.clear_cache_btn.bind(on_press=lambda _b: self._clear_cache())
        cache_card.add_widget(self.clear_cache_btn)
        set_box.add_widget(cache_card)

        about_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(6),
                                size_hint=(1, None), height=dp(104),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))
        about_title = Label(text="关于哔哩转售捡漏监控", font_size=sp(14), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, None), height=dp(22), halign="left")
        about_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(about_title)

        ver_lbl = Label(text="版本: v1.4.0 (120Hz 高刷流光版)", font_size=sp(12),
                        color=CLR_PRIMARY, size_hint=(1, None), height=dp(20), halign="left")
        ver_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(ver_lbl)

        sub_lbl = Label(text="全面支持 90/120Hz 屏幕、多品类抓取、零内存抖动流畅滑动与实时成交走势穿透。",
                        font_size=sp(10.5), color=CLR_TEXT_MUTED, size_hint=(1, None), height=dp(24), halign="left")
        sub_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(sub_lbl)
        set_box.add_widget(about_card)

        scroll.add_widget(set_box)
        self.content.add_widget(scroll)

    def _sync_from_pc(self):
        ip_port = self.ip_input.text.strip()
        if not ip_port:
            return
        self.sync_btn.text = "正在同步中…"

        def worker():
            err = None
            try:
                url = f"http://{ip_port}/3c_products.json"
                req = urllib.request.Request(url, headers={"User-Agent": "BiliResellAndroid/1.4"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read()
                with open(JSON_PATH, "wb") as f:
                    f.write(data)
            except Exception as e:
                err = str(e)

            def update_ui(dt):
                if err:
                    self.sync_btn.text = f"同步失败: {err[:16]}"
                else:
                    self.sync_btn.text = "同步成功！数据已更新"
                    self.load_data()
                Clock.schedule_once(lambda _d: setattr(self.sync_btn, 'text', '从电脑极速同步数据'), 3.0)

            Clock.schedule_once(update_ui, 0)

        threading.Thread(target=worker, daemon=True).start()

    def _clear_cache(self):
        try:
            if os.path.exists(DEALS_CACHE_PATH):
                os.remove(DEALS_CACHE_PATH)
            self.clear_cache_btn.text = "已清空成交价缓存"
        except Exception as e:
            self.clear_cache_btn.text = f"清理失败: {e}"
        Clock.schedule_once(lambda _d: setattr(self.clear_cache_btn, 'text', '清除本地成交价缓存'), 2.0)


# =====================================================================
# 程序入口
# =====================================================================
if __name__ == "__main__":
    if not IS_ANDROID:
        Window.size = (420, 840)
    ResellMonitorMobile().run()
