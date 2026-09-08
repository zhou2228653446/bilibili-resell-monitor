# -*- coding: utf-8 -*-
import os, sys
os.chdir(r"d:\bili")
sys.path.insert(0, r"d:\bili\android_app")

from kivy.config import Config
_FONT_PATH = os.path.join(r"d:\bili\android_app", "NotoSansCJKsc-Regular.otf")
if os.path.exists(_FONT_PATH):
    Config.set("kivy", "default_font", repr(["CJK", _FONT_PATH, _FONT_PATH, _FONT_PATH]))

from kivy.core.window import Window
Window.size = (480, 800)

from kivy.app import App
from kivy.clock import Clock
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
import json
import threading
import webbrowser

if os.path.exists(_FONT_PATH):
    LabelBase.register(name="CJK", fn_regular=_FONT_PATH, fn_bold=_FONT_PATH, fn_italic=_FONT_PATH)

from android_compat import get_out_path
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
CLR_TEXT_MUTED = (0.580, 0.624, 0.678, 1.0)    # #949FA- 弱灰
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

class RoundedBox(BoxLayout):
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
    def __init__(self, bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1),
                 radius=dp(8), border_color=None, border_width=0, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.normal_bg = bg_color
        self.down_bg = (bg_color[0] * 0.88, bg_color[1] * 0.88, bg_color[2] * 0.88, bg_color[3])
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
    def __init__(self, text, active=False, on_select=None, **kw):
        super().__init__(text=text, font_size=sp(12), size_hint=(None, None),
                         height=dp(30), padding=(dp(12), dp(4)), **kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.active = active
        self.on_select = on_select
        self.bind(on_press=self._on_press)
        self._calc_width()
        Clock.schedule_once(self._redraw, 0)

    def _calc_width(self, *args):
        self.width = max(dp(54), len(self.text) * dp(13) + dp(24))

    def _on_press(self, *args):
        if self.on_select:
            self.on_select(self)

    def set_active(self, val):
        self.active = val
        self._redraw()

    def _redraw(self, *args):
        self.canvas.before.clear()
        bg = CLR_PRIMARY if self.active else CLR_CHIP_BG
        self.color = (1, 1, 1, 1) if self.active else CLR_CHIP_TXT
        with self.canvas.before:
            Color(*bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])

class ProductCardWidget(RoundedBox):
    """重构版商品卡片：完全消除重叠、精致圆角相框、多维度价格徽标。"""

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

        # 标题 (限制最多 2 行，绝对不重叠)
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
    """重构版商品详情弹窗：无乱码符号、精致层次与买家订单展示。"""

    def __init__(self, product, on_price_updated=None, **kw):
        super().__init__(size_hint=(0.94, 0.88), auto_dismiss=True, **kw)
        self.background_color = (0, 0, 0, 0.6)
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
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
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

class ModernTabBar(RoundedBox):
    def __init__(self, app_ref, **kw):
        super().__init__(size_hint=(1, None), height=dp(52), padding=(dp(8), dp(2)),
                         spacing=dp(4), bg_color=CLR_CARD, border_color=CLR_BORDER,
                         radius=0, border_width=1, **kw)
        self.app_ref = app_ref
        self.tabs = [
            ("市集大盘", app_ref.show_list),
            ("捡漏雷达", app_ref.show_radar),
            ("实时抓取", app_ref.show_crawl),
            ("系统设置", app_ref.show_settings),
        ]
        self.buttons = []
        self.active_index = 0
        for idx, (title, cb) in enumerate(self.tabs):
            btn = Button(text=title, font_size=sp(12.5), bold=False,
                         background_normal="", background_down="",
                         background_color=(0, 0, 0, 0))
            btn.bind(on_press=lambda _b, i=idx, f=cb: self._switch_tab(i, f))
            self.add_widget(btn)
            self.buttons.append(btn)
        self.bind(pos=self._redraw_indicator, size=self._redraw_indicator)
        self.set_active_index(0)

    def _switch_tab(self, index, callback):
        self.set_active_index(index)
        callback()

    def set_active_index(self, active_idx):
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
        Clock.schedule_once(self._redraw_indicator, 0)

    def _redraw_indicator(self, *args):
        self.canvas.after.clear()
        if 0 <= self.active_index < len(self.buttons):
            btn = self.buttons[self.active_index]
            if btn.width > 0:
                bar_w = dp(32)
                bar_x = btn.x + (btn.width - bar_w) / 2
                bar_y = self.y + dp(3)
                with self.canvas.after:
                    Color(*CLR_PRIMARY)
                    RoundedRectangle(pos=(bar_x, bar_y), size=(bar_w, dp(3)), radius=[dp(1.5)])

# =====================================================================
# 应用核心逻辑 (ResellMonitorMobile)
# =====================================================================

class ResellMonitorMobile(App):
    title = "B站转售监控"

    def build(self):
        self.root_box = BoxLayout(orientation="vertical")

        # 顶部全局导航栏 (B站粉 + 胶囊在售徽标)
        self.header_bar = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(48),
                                     padding=(dp(16), dp(8)), spacing=dp(8),
                                     bg_color=CLR_PRIMARY, radius=0, border_width=0)
        self.header_title = Label(text="哔哩转售捡漏监控", font_size=sp(16), bold=True,
                                  color=(1, 1, 1, 1), halign="left", valign="middle")
        self.header_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))

        badge_box = RoundedBox(size_hint=(None, None), size=(dp(84), dp(26)),
                               bg_color=(1, 1, 1, 0.22), border_color=(1, 1, 1, 0.4),
                               radius=dp(13), border_width=1)
        self.header_count_badge = Label(text="实时 --件", font_size=sp(11), bold=True,
                                        color=(1, 1, 1, 1), halign="center", valign="middle")
        badge_box.add_widget(self.header_count_badge)

        self.header_bar.add_widget(self.header_title)
        self.header_bar.add_widget(badge_box)
        self.root_box.add_widget(self.header_bar)

        # 中间内容区域
        self.content = BoxLayout(orientation="vertical", padding=(dp(12), dp(10)), spacing=dp(8))
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
        self.page_render_limit = 50

        # 启动时加载列表
        Clock.schedule_once(lambda _dt: self.show_list(), 0.1)
        return self.root_box

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
                pass

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
        self.content.clear_widgets()
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
            self.page_render_limit = 50
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
                                 do_scroll_x=True, do_scroll_y=False, bar_width=0)
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
                               size_hint=(None, 1), width=dp(84), font_size=sp(10.5),
                               background_normal="", background_color=CLR_CHIP_BG,
                               color=CLR_TEXT_SUB)

        def _on_sort_change(_s, val):
            name_to_key = {v: k for k, v in sort_map_names.items()}
            self.active_sort = name_to_key.get(val, "default")
            self.page_render_limit = 50
            self.apply_filters()
            self._repopulate_list()

        sort_spinner.bind(text=_on_sort_change)
        meta_bar.add_widget(sort_spinner)
        self.content.add_widget(meta_bar)

        # D. 滚动商品列表
        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
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
        self.page_render_limit = 50
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
        self.tab_bar.set_active_index(1)
        self.content.clear_widgets()
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

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
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
    # 页面三：实时抓取控制台 (show_crawl)
    # =====================================================================
    def show_crawl(self):
        self.current_tab = "crawl"
        self.tab_bar.set_active_index(2)
        self.content.clear_widgets()
        self.load_data()

        prices = [_parse_price(p.get("price")) for p in self.all_products if _parse_price(p.get("price"))]
        avg_p = f"¥{sum(prices)/len(prices):.1f}" if prices else "¥--"
        min_p = f"¥{min(prices):.1f}" if prices else "¥--"

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

        cfg_panel = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(10),
                               size_hint=(1, None), height=dp(120),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))

        row1 = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(30), spacing=dp(6))
        row1.add_widget(Label(text="抓取深度:", font_size=sp(12), color=CLR_TEXT_MAIN, size_hint=(None, 1), width=dp(64)))

        self.crawl_pages = 15
        self.page_btns = []
        for pg_num, pg_label in [(5, "快速 5页"), (15, "常规 15页"), (50, "全量 50页")]:
            p_btn = ModernButton(text=pg_label, font_size=sp(11.5), size_hint=(1, 1),
                                 bg_color=CLR_PRIMARY if pg_num == self.crawl_pages else CLR_CHIP_BG,
                                 text_color=(1, 1, 1, 1) if pg_num == self.crawl_pages else CLR_TEXT_SUB,
                                 radius=dp(6))
            p_btn.bind(on_press=lambda _b, n=pg_num: self._set_crawl_pages(n))
            row1.add_widget(p_btn)
            self.page_btns.append((pg_num, p_btn))
        cfg_panel.add_widget(row1)

        self.crawl_action_btn = ModernButton(
            text="开始实时抓取数据", font_size=sp(13.5), bold=True,
            size_hint=(1, None), height=dp(38),
            bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1), radius=dp(8)
        )
        self.crawl_action_btn.bind(on_press=lambda _b: self._start_crawl())
        cfg_panel.add_widget(self.crawl_action_btn)
        self.content.add_widget(cfg_panel)

        term_card = RoundedBox(orientation="vertical", padding=dp(10), spacing=dp(4),
                               size_hint=(1, 1), bg_color=(0.10, 0.12, 0.16, 1.0),
                               border_color=(0.20, 0.22, 0.28, 1.0), radius=dp(10))

        term_title = Label(text="实时控制台输出", font_size=sp(11), bold=True,
                           color=(0.6, 0.7, 0.8, 1), size_hint=(1, None), height=dp(20), halign="left")
        term_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        term_card.add_widget(term_title)

        log_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
        self.crawl_log_lbl = Label(
            text="准备就绪。点击上方「开始实时抓取数据」启动爬虫。\n抓取完成后主列表与雷达将自动无感更新。",
            font_size=sp(11), color=(0.4, 0.85, 0.55, 1.0),
            size_hint_y=None, halign="left", valign="top"
        )
        self.crawl_log_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        self.crawl_log_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', max(dp(80), val[1])))
        log_scroll.add_widget(self.crawl_log_lbl)
        term_card.add_widget(log_scroll)
        self.content.add_widget(term_card)

    def _set_crawl_pages(self, num):
        self.crawl_pages = num
        for pg_num, btn in self.page_btns:
            btn.normal_bg = CLR_PRIMARY if pg_num == num else CLR_CHIP_BG
            btn.color = (1, 1, 1, 1) if pg_num == num else CLR_TEXT_SUB
            btn._redraw()

    def _start_crawl(self):
        if self.crawling:
            return
        self.crawling = True
        self.crawl_action_btn.text = "正在抓取中，请稍候…"
        self.crawl_action_btn.normal_bg = (0.7, 0.7, 0.7, 1)
        self.crawl_action_btn._redraw()
        self.crawl_log_lbl.text = f"[启动] 开始从 B 站会员购抓取前 {self.crawl_pages} 页转售商品…\n"

        def log_cb(msg):
            Clock.schedule_once(lambda dt: self._append_crawl_log(msg), 0)

        def worker():
            try:
                bili_resell.crawl_and_process(
                    category="3C",
                    sort_type="TIME_DESC",
                    max_pages=self.crawl_pages,
                    log_fn=log_cb
                )
                log_cb("\n[完成] 本轮数据抓取与大盘入库已成功完成！")
            except Exception as e:
                log_cb(f"\n[异常] 抓取失败: {e}")
            finally:
                self.crawling = False
                Clock.schedule_once(lambda dt: self._crawl_done(), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _append_crawl_log(self, msg):
        self.crawl_log_lbl.text += msg + "\n"

    def _crawl_done(self):
        if hasattr(self, "crawl_action_btn") and self.crawl_action_btn:
            self.crawl_action_btn.text = "开始实时抓取数据"
            self.crawl_action_btn.normal_bg = CLR_PRIMARY
            self.crawl_action_btn._redraw()
        self.load_data()

    # =====================================================================
    # 页面四：系统设置与同步 (show_settings)
    # =====================================================================
    def show_settings(self):
        self.current_tab = "settings"
        self.tab_bar.set_active_index(3)
        self.content.clear_widgets()

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
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
                                size_hint=(1, None), height=dp(100),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))
        about_title = Label(text="关于哔哩转售捡漏监控", font_size=sp(14), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, None), height=dp(22), halign="left")
        about_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(about_title)

        ver_lbl = Label(text="版本: v1.2.0 (现代沉浸高级版)", font_size=sp(12),
                        color=CLR_PRIMARY, size_hint=(1, None), height=dp(20), halign="left")
        ver_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(ver_lbl)

        sub_lbl = Label(text="支持 B 站会员购数码转售行情监控、真实成交价穿透与捡漏预警。",
                        font_size=sp(11), color=CLR_TEXT_MUTED, size_hint=(1, None), height=dp(20), halign="left")
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
                req = urllib.request.Request(url, headers={"User-Agent": "BiliResellAndroid/1.0"})
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
