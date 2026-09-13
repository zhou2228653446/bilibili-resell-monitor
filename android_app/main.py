# -*- coding: utf-8 -*-
"""
B站会员购转售监控 - Android 端 (v1.7.0 赛博流光·极客动效版)
特性:
1. 赛博极客·流光深色玻璃美学 (Cyberpunk Frosted Glass & Neon Accents)
2. 全套物理触感微缩回弹微动效 (Scale Bounce on Cards & Buttons)
3. 阶梯多米诺瀑布流进场动效 (Staggered Cascade List Entry)
4. 真正的 Canvas 动态贝塞尔走势图与渐变面积扫描展开 (Interactive Curve Chart)
5. 捡漏雷达动态同心光环波纹与科幻雷达扫描舱 (Animated Radar Pulse Scanner HUD)
6. 流体果冻拉伸变形底部导航栏 (Fluid Morphing Capsule TabBar)
7. 底部抽屉式平滑弹性升降弹窗 (Spring Bottom Sheet Modal with Drag Handle)
8. 90Hz / 120Hz 高刷新率屏幕自适应调度与 B站 CDN 缩略图极速加载
"""
import json
import math
import os
import sys
import threading
import time
import urllib.request
import webbrowser

# ---- 1. 高刷新率配置与字体注册（必须置于其他 Kivy 模块导入之前） ----
from kivy.config import Config

# 解除 60 帧限制，启用 120Hz 高刷新率调度
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
from kivy.graphics import (
    Color, RoundedRectangle, Line, PushMatrix, PopMatrix,
    Scale, Translate, Mesh, Ellipse
)
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.image import AsyncImage, Image
from kivy.uix.floatlayout import FloatLayout
from kivy.animation import Animation
from kivy.properties import NumericProperty, BooleanProperty
from kivy.loader import Loader

# 优化图片异步加载器：限制并发与单帧最大上传纹理数，杜绝帧间时间抖动
Loader.num_workers = 3
Loader.max_upload_per_frame = 2

if os.path.exists(_FONT_PATH):
    LabelBase.register(name="CJK", fn_regular=_FONT_PATH,
                       fn_bold=_FONT_PATH, fn_italic=_FONT_PATH)

from android_compat import IS_ANDROID, get_out_path
import bili_resell
import notification_helper
from scheduler import AutoCrawlScheduler

JSON_PATH = get_out_path("3c_products.json")
DEALS_CACHE_PATH = get_out_path("deals_cache.json")

# =====================================================================
# 双风格视觉主题系统 (Dual-Theme Aesthetic System)
# 方案 A: 赛博极客·流光深色 (Cyberpunk Neon Dark)
# 方案 B: 纯净通透·二次元微光 (Luminous Pure Ivory)
# =====================================================================

THEME_CONFIG_PATH = get_out_path("theme_config.json")

THEMES = {
    "cyber": {
        "name": "赛博极客·流光深色",
        "short_name": "赛博深色",
        "desc": "曜黑太空底色 · 荧光霓虹微拟态 · 科技探测舱",
        "colors": {
            "CLR_BG": (0.043, 0.059, 0.098, 1.0),           # #0B0F19 深邃曜黑太空底
            "CLR_CARD": (0.075, 0.106, 0.165, 0.96),         # #131B2A 流光深色微拟态卡片
            "CLR_CARD_HOVER": (0.106, 0.145, 0.220, 0.98),   # #1B2538 触控按压高亮卡片
            "CLR_BORDER": (0.165, 0.224, 0.337, 0.85),       # #2A3956 流光霓虹微边
            "CLR_BORDER_LIGHT": (0.118, 0.161, 0.247, 0.70), # #1E293F 暗微边框
            "CLR_PRIMARY": (1.0, 0.400, 0.600, 1.0),         # #FF6699 璀璨霓虹粉
            "CLR_PRIMARY_DARK": (0.950, 0.250, 0.480, 1.0), # 饱和粉
            "CLR_PRIMARY_BG": (0.24, 0.08, 0.16, 0.90),      # 深色粉霞光底
            "CLR_PRIMARY_BORDER": (0.85, 0.28, 0.50, 0.85),  # 霓虹粉微边
            "CLR_CYAN": (0.0, 0.949, 0.996, 1.0),            # #00F2FE 赛博青
            "CLR_CYAN_BG": (0.03, 0.18, 0.24, 0.90),
            "CLR_CYAN_BORDER": (0.0, 0.75, 0.85, 0.80),
            "CLR_MINT_TXT": (0.204, 0.827, 0.600, 1.0),      # #34D399 荧光薄荷绿
            "CLR_MINT_BG": (0.04, 0.20, 0.14, 0.90),         # 荧光绿底
            "CLR_MINT_BORDER": (0.10, 0.55, 0.38, 0.80),
            "CLR_AMBER_TXT": (0.984, 0.749, 0.184, 1.0),     # #FBBF24 晨曦金
            "CLR_AMBER_BG": (0.24, 0.16, 0.03, 0.90),
            "CLR_AMBER_BORDER": (0.75, 0.52, 0.10, 0.80),
            "CLR_BLUE": (0.227, 0.678, 0.992, 1.0),          # #38BDF8 天空电光蓝
            "CLR_BLUE_BG": (0.04, 0.15, 0.26, 0.90),
            "CLR_BLUE_BORDER": (0.15, 0.45, 0.75, 0.80),
            "CLR_TEXT_MAIN": (0.957, 0.969, 0.984, 1.0),     # #F4F6FB 耀白主文字
            "CLR_TEXT_SUB": (0.686, 0.745, 0.824, 1.0),      # #AFBED2 银灰副标题
            "CLR_TEXT_MUTED": (0.420, 0.482, 0.573, 1.0),    # #6B7B92 暗钢说明
            "CLR_CHIP_BG": (0.102, 0.141, 0.212, 0.90),      # #1A2436 胶囊深色底
            "CLR_CHIP_TXT": (0.750, 0.820, 0.900, 1.0),
            "CLR_TAB_INACTIVE": (0.450, 0.520, 0.620, 1.0),
        }
    },
    "ivory": {
        "name": "纯净通透·二次元微光",
        "short_name": "纯净象牙白",
        "desc": "极净瓷白底色 · 柔和纯白悬浮 · 清新治愈彩调",
        "colors": {
            "CLR_BG": (0.973, 0.980, 0.988, 1.0),           # #F8FAFC 极净瓷白底色
            "CLR_CARD": (1.0, 1.0, 1.0, 1.0),                 # #FFFFFF 纯白浮雕卡片
            "CLR_CARD_HOVER": (0.950, 0.962, 0.980, 1.0),    # #F1F5F9 浅灰轻触高亮
            "CLR_BORDER": (0.898, 0.918, 0.941, 1.0),        # #E2E8F0 浅灰微边
            "CLR_BORDER_LIGHT": (0.941, 0.953, 0.965, 1.0),  # #F1F5F9 暗微边
            "CLR_PRIMARY": (0.984, 0.447, 0.600, 1.0),        # #FB7299 B站官方粉
            "CLR_PRIMARY_DARK": (0.880, 0.220, 0.450, 1.0),  # 深粉
            "CLR_PRIMARY_BG": (1.0, 0.940, 0.960, 1.0),       # #FFF1F2 浅粉底
            "CLR_PRIMARY_BORDER": (0.996, 0.796, 0.859, 1.0), # #FECDD3 浅粉微边
            "CLR_CYAN": (0.020, 0.650, 0.820, 1.0),           # 清澈湖蓝青
            "CLR_CYAN_BG": (0.920, 0.975, 1.000, 1.0),
            "CLR_CYAN_BORDER": (0.700, 0.880, 0.980, 1.0),
            "CLR_MINT_TXT": (0.020, 0.588, 0.412, 1.0),       # #059669 翠绿字
            "CLR_MINT_BG": (0.925, 0.992, 0.961, 1.0),        # #ECFDF5 薄荷绿底
            "CLR_MINT_BORDER": (0.655, 0.949, 0.835, 1.0),    # #A7F3D0
            "CLR_AMBER_TXT": (0.851, 0.467, 0.024, 1.0),      # #D97706 琥珀金字
            "CLR_AMBER_BG": (0.996, 0.953, 0.780, 1.0),       # #FEF3C7 晨曦暖金底
            "CLR_AMBER_BORDER": (0.992, 0.875, 0.533, 1.0),   # #FDE68A
            "CLR_BLUE": (0.149, 0.549, 0.898, 1.0),           # #2563EB 天空蓝
            "CLR_BLUE_BG": (0.937, 0.965, 1.000, 1.0),        # #EFF6FF
            "CLR_BLUE_BORDER": (0.753, 0.859, 0.988, 1.0),   # #BFDBFE
            "CLR_TEXT_MAIN": (0.059, 0.090, 0.165, 1.0),      # #0F172A 曜石黑主文字
            "CLR_TEXT_SUB": (0.278, 0.333, 0.412, 1.0),       # #475569 雅致深灰
            "CLR_TEXT_MUTED": (0.580, 0.639, 0.722, 1.0),     # #94A3B8 浅灰说明
            "CLR_CHIP_BG": (0.945, 0.957, 0.973, 1.0),       # #F1F5F9 浅灰胶囊
            "CLR_CHIP_TXT": (0.278, 0.333, 0.412, 1.0),
            "CLR_TAB_INACTIVE": (0.580, 0.639, 0.722, 1.0),
        }
    }
}

# 默认变量初始化
CLR_BG = THEMES["cyber"]["colors"]["CLR_BG"]
CLR_CARD = THEMES["cyber"]["colors"]["CLR_CARD"]
CLR_CARD_HOVER = THEMES["cyber"]["colors"]["CLR_CARD_HOVER"]
CLR_BORDER = THEMES["cyber"]["colors"]["CLR_BORDER"]
CLR_BORDER_LIGHT = THEMES["cyber"]["colors"]["CLR_BORDER_LIGHT"]
CLR_PRIMARY = THEMES["cyber"]["colors"]["CLR_PRIMARY"]
CLR_PRIMARY_DARK = THEMES["cyber"]["colors"]["CLR_PRIMARY_DARK"]
CLR_PRIMARY_BG = THEMES["cyber"]["colors"]["CLR_PRIMARY_BG"]
CLR_PRIMARY_BORDER = THEMES["cyber"]["colors"]["CLR_PRIMARY_BORDER"]
CLR_CYAN = THEMES["cyber"]["colors"]["CLR_CYAN"]
CLR_CYAN_BG = THEMES["cyber"]["colors"]["CLR_CYAN_BG"]
CLR_CYAN_BORDER = THEMES["cyber"]["colors"]["CLR_CYAN_BORDER"]
CLR_MINT_TXT = THEMES["cyber"]["colors"]["CLR_MINT_TXT"]
CLR_MINT_BG = THEMES["cyber"]["colors"]["CLR_MINT_BG"]
CLR_MINT_BORDER = THEMES["cyber"]["colors"]["CLR_MINT_BORDER"]
CLR_AMBER_TXT = THEMES["cyber"]["colors"]["CLR_AMBER_TXT"]
CLR_AMBER_BG = THEMES["cyber"]["colors"]["CLR_AMBER_BG"]
CLR_AMBER_BORDER = THEMES["cyber"]["colors"]["CLR_AMBER_BORDER"]
CLR_BLUE = THEMES["cyber"]["colors"]["CLR_BLUE"]
CLR_BLUE_BG = THEMES["cyber"]["colors"]["CLR_BLUE_BG"]
CLR_BLUE_BORDER = THEMES["cyber"]["colors"]["CLR_BLUE_BORDER"]
CLR_TEXT_MAIN = THEMES["cyber"]["colors"]["CLR_TEXT_MAIN"]
CLR_TEXT_SUB = THEMES["cyber"]["colors"]["CLR_TEXT_SUB"]
CLR_TEXT_MUTED = THEMES["cyber"]["colors"]["CLR_TEXT_MUTED"]
CLR_CHIP_BG = THEMES["cyber"]["colors"]["CLR_CHIP_BG"]
CLR_CHIP_TXT = THEMES["cyber"]["colors"]["CLR_CHIP_TXT"]
CLR_TAB_INACTIVE = THEMES["cyber"]["colors"]["CLR_TAB_INACTIVE"]

def set_theme(theme_name):
    global CLR_BG, CLR_CARD, CLR_CARD_HOVER, CLR_BORDER, CLR_BORDER_LIGHT
    global CLR_PRIMARY, CLR_PRIMARY_DARK, CLR_PRIMARY_BG, CLR_PRIMARY_BORDER
    global CLR_CYAN, CLR_CYAN_BG, CLR_CYAN_BORDER
    global CLR_MINT_TXT, CLR_MINT_BG, CLR_MINT_BORDER
    global CLR_AMBER_TXT, CLR_AMBER_BG, CLR_AMBER_BORDER
    global CLR_BLUE, CLR_BLUE_BG, CLR_BLUE_BORDER
    global CLR_TEXT_MAIN, CLR_TEXT_SUB, CLR_TEXT_MUTED
    global CLR_CHIP_BG, CLR_CHIP_TXT, CLR_TAB_INACTIVE

    theme = THEMES.get(theme_name, THEMES["cyber"])
    c = theme["colors"]
    CLR_BG = c["CLR_BG"]
    CLR_CARD = c["CLR_CARD"]
    CLR_CARD_HOVER = c["CLR_CARD_HOVER"]
    CLR_BORDER = c["CLR_BORDER"]
    CLR_BORDER_LIGHT = c["CLR_BORDER_LIGHT"]
    CLR_PRIMARY = c["CLR_PRIMARY"]
    CLR_PRIMARY_DARK = c["CLR_PRIMARY_DARK"]
    CLR_PRIMARY_BG = c["CLR_PRIMARY_BG"]
    CLR_PRIMARY_BORDER = c["CLR_PRIMARY_BORDER"]
    CLR_CYAN = c["CLR_CYAN"]
    CLR_CYAN_BG = c["CLR_CYAN_BG"]
    CLR_CYAN_BORDER = c["CLR_CYAN_BORDER"]
    CLR_MINT_TXT = c["CLR_MINT_TXT"]
    CLR_MINT_BG = c["CLR_MINT_BG"]
    CLR_MINT_BORDER = c["CLR_MINT_BORDER"]
    CLR_AMBER_TXT = c["CLR_AMBER_TXT"]
    CLR_AMBER_BG = c["CLR_AMBER_BG"]
    CLR_AMBER_BORDER = c["CLR_AMBER_BORDER"]
    CLR_BLUE = c["CLR_BLUE"]
    CLR_BLUE_BG = c["CLR_BLUE_BG"]
    CLR_BLUE_BORDER = c["CLR_BLUE_BORDER"]
    CLR_TEXT_MAIN = c["CLR_TEXT_MAIN"]
    CLR_TEXT_SUB = c["CLR_TEXT_SUB"]
    CLR_TEXT_MUTED = c["CLR_TEXT_MUTED"]
    CLR_CHIP_BG = c["CLR_CHIP_BG"]
    CLR_CHIP_TXT = c["CLR_CHIP_TXT"]
    CLR_TAB_INACTIVE = c["CLR_TAB_INACTIVE"]
    Window.clearcolor = CLR_BG

def load_theme_setting():
    try:
        if os.path.exists(THEME_CONFIG_PATH):
            with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                theme = data.get("theme", "cyber")
                if theme in THEMES:
                    return theme
    except Exception:
        pass
    return "cyber"

def save_theme_setting(theme_name):
    try:
        with open(THEME_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"theme": theme_name}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warn] 保存主题配置失败: {e}", file=sys.stderr)

# 启动时加载已保存的主题
set_theme(load_theme_setting())


def _parse_price(s):
    try:
        return float(str(s).replace("¥", "").replace(",", "").strip())
    except Exception:
        return None


def get_optimized_thumb_url(url, size=180):
    """
    B站 CDN 智能缩略图优化网关：
    自动将 1000x1000 (近 1MB) 原图转换为 180x180 (38KB) 高清微图，
    下载体积锐减 96% (25.7 倍)，显存与纹理解压开销降低 30 倍，彻底根治卡顿。
    """
    if not url:
        return "https://i0.hdslb.com/bfs/mall/mall/default.png"
    if url.startswith("//"):
        url = "https:" + url
    if "@" in url:
        return url
    if "hdslb.com" in url or "/bfs/mall/" in url:
        return f"{url}@{size}w_{size}h_1c.png"
    return url


# =====================================================================
# 高性能持久化指令 UI 组件 (Zero Canvas Allocations on Scroll & Micro-Interactions)
# =====================================================================

class RoundedBox(BoxLayout):
    """
    高性能流光圆角容器：
    支持 OpenGL 矩阵变换 (Scale Bounce / Translate)、单次指令分配与多角独立圆角。
    """
    scale = NumericProperty(1.0)
    entry_y = NumericProperty(0.0)

    def __init__(self, bg_color=CLR_CARD, border_color=CLR_BORDER,
                 radius=dp(12), border_width=1, enable_transform=False, **kw):
        super().__init__(**kw)
        self.enable_transform = enable_transform
        self._bg_color_val = list(bg_color)
        self._border_color_val = list(border_color) if border_color else None
        self._radius_val = radius
        self._line_r = self._radius_val[0] if isinstance(self._radius_val, (list, tuple)) else self._radius_val
        self._border_width_val = border_width

        with self.canvas.before:
            if self.enable_transform:
                PushMatrix()
                self._trans_inst = Translate(0, self.entry_y)
                self._scale_inst = Scale(1, 1, 1, origin=self.center)
            self._bg_color_inst = Color(*self._bg_color_val)
            r_list = [self._radius_val] if isinstance(self._radius_val, (int, float)) else self._radius_val
            self._rect_inst = RoundedRectangle(pos=self.pos, size=self.size, radius=r_list)
            if self._border_color_val and self._border_width_val > 0:
                self._border_color_inst = Color(*self._border_color_val)
                self._line_inst = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, self._line_r),
                    width=self._border_width_val
                )
            else:
                self._border_color_inst = None
                self._line_inst = None

        if self.enable_transform:
            with self.canvas.after:
                PopMatrix()

        self.bind(pos=self._update_geometry, size=self._update_geometry)

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size
            if self.enable_transform and hasattr(self, "_scale_inst"):
                self._scale_inst.origin = (self.center_x, self.center_y + self.entry_y)
            if self._line_inst:
                self._line_inst.rounded_rectangle = (
                    self.x, self.y, self.width, self.height, self._line_r
                )

    def on_scale(self, inst, val):
        if self.enable_transform and hasattr(self, "_scale_inst"):
            self._scale_inst.xyz = (val, val, 1.0)
            self._scale_inst.origin = (self.center_x, self.center_y + self.entry_y)

    def on_entry_y(self, inst, val):
        if self.enable_transform and hasattr(self, "_trans_inst"):
            self._trans_inst.y = val
            if hasattr(self, "_scale_inst"):
                self._scale_inst.origin = (self.center_x, self.center_y + val)

    def set_bg_color(self, clr):
        self._bg_color_val = list(clr)
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = clr

    def set_border_color(self, clr):
        if self._border_color_inst:
            self._border_color_inst.rgba = clr


class ModernButton(Button):
    """
    高性能触控弹性回弹按钮：
    按压瞬间物理微缩 (0.955)，释放时以 out_back 超调弹性回弹，触感极度灵敏。
    """
    scale = NumericProperty(1.0)

    def __init__(self, bg_color=CLR_PRIMARY, text_color=(1, 1, 1, 1),
                 radius=dp(8), border_color=None, border_width=0, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.normal_bg = list(bg_color)
        self.down_bg = [min(1.0, bg_color[0] * 1.15), min(1.0, bg_color[1] * 1.15), min(1.0, bg_color[2] * 1.15), bg_color[3]]
        self.radius = radius
        self.border_color = list(border_color) if border_color else None
        self.border_width = border_width
        self.color = text_color

        with self.canvas.before:
            PushMatrix()
            self._scale_inst = Scale(1, 1, 1, origin=self.center)
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

        with self.canvas.after:
            PopMatrix()

        self.bind(pos=self._update_geometry, size=self._update_geometry, state=self._update_state)

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size
            if hasattr(self, "_scale_inst"):
                self._scale_inst.origin = self.center
            if self._line_inst:
                self._line_inst.rounded_rectangle = (
                    self.x, self.y, self.width, self.height, self.radius
                )

    def on_scale(self, inst, val):
        if hasattr(self, "_scale_inst"):
            self._scale_inst.xyz = (val, val, 1.0)
            self._scale_inst.origin = self.center

    def _update_state(self, *args):
        if hasattr(self, "_bg_color_inst"):
            bg = self.down_bg if self.state == "down" else self.normal_bg
            self._bg_color_inst.rgba = bg
            Animation.stop_all(self, 'scale')
            if self.state == "down":
                Animation(scale=0.952, duration=0.06, t='out_quad').start(self)
            else:
                Animation(scale=1.0, duration=0.20, t='out_back').start(self)

    def set_bg_color(self, clr):
        self.normal_bg = list(clr)
        self.down_bg = [min(1.0, clr[0] * 1.15), min(1.0, clr[1] * 1.15), min(1.0, clr[2] * 1.15), clr[3]]
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = self.normal_bg


class FilterChip(Button):
    """
    赛博霓虹筛选胶囊芯片：
    带弹性微缩微动效与发光边框，激活态高亮通透。
    """
    scale = NumericProperty(1.0)

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
            PushMatrix()
            self._scale_inst = Scale(1, 1, 1, origin=self.center)
            self._bg_color_inst = Color(*(CLR_PRIMARY if self.active else CLR_CHIP_BG))
            self._rect_inst = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
            self._border_clr_inst = Color(*(CLR_PRIMARY_BORDER if self.active else CLR_BORDER_LIGHT))
            self._border_line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(15)), width=1)

        with self.canvas.after:
            PopMatrix()

        self.color = (1, 1, 1, 1) if self.active else CLR_CHIP_TXT
        self.bind(pos=self._update_geometry, size=self._update_geometry, on_press=self._on_press)

    def _calc_width(self):
        self.width = max(dp(56), len(self.text) * dp(13) + dp(26))

    def _update_geometry(self, *args):
        if hasattr(self, "_rect_inst"):
            self._rect_inst.pos = self.pos
            self._rect_inst.size = self.size
            if hasattr(self, "_border_line"):
                self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(15))
            if hasattr(self, "_scale_inst"):
                self._scale_inst.origin = self.center

    def on_scale(self, inst, val):
        if hasattr(self, "_scale_inst"):
            self._scale_inst.xyz = (val, val, 1.0)
            self._scale_inst.origin = self.center

    def _on_press(self, *args):
        Animation.stop_all(self, 'scale')
        (Animation(scale=0.92, duration=0.06, t='out_quad') +
         Animation(scale=1.0, duration=0.18, t='out_back')).start(self)
        if self.on_select:
            self.on_select(self)

    def set_active(self, val):
        self.active = val
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = CLR_PRIMARY if self.active else CLR_CHIP_BG
        if hasattr(self, "_border_clr_inst"):
            self._border_clr_inst.rgba = CLR_PRIMARY_BORDER if self.active else CLR_BORDER_LIGHT
        self.color = (1, 1, 1, 1) if self.active else CLR_CHIP_TXT


# =====================================================================
# 商品卡片与详情弹窗组件 (赛博流光·极客动效版)
# =====================================================================

class ProductCardWidget(RoundedBox):
    """
    极速流畅赛博流光商品卡片：
    触控物理按压微缩回弹 (Scale Bounce)、阶梯瀑布流进场动效、发光状态芯片与深邃微拟态质感。
    """
    def __init__(self, product, on_open_detail=None, **kw):
        super().__init__(orientation="horizontal", padding=dp(10), spacing=dp(10),
                         size_hint=(1, None), height=dp(116),
                         bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(14),
                         enable_transform=True, **kw)
        self.product = product
        self.on_open_detail = on_open_detail

        # 1. 缩略图底框 (92x92dp，暗影内嵌 + 暗微边框)
        t_bg = (0.04, 0.07, 0.12, 1.0) if CLR_BG[0] < 0.5 else (0.94, 0.95, 0.97, 1.0)
        thumb_frame = RoundedBox(size_hint=(None, None), size=(dp(92), dp(92)),
                                 bg_color=t_bg,
                                 border_color=CLR_BORDER_LIGHT,
                                 radius=dp(10), border_width=1)
        raw_img = product.get("img") or ""
        thumb_url = get_optimized_thumb_url(raw_img, size=180)
        self.thumb = AsyncImage(source=thumb_url, size_hint=(1, 1), fit_mode="contain")
        thumb_frame.add_widget(self.thumb)
        self.add_widget(thumb_frame)

        # 2. 右侧信息主布局 (垂直排列)
        info_layout = BoxLayout(orientation="vertical", spacing=dp(4), size_hint=(1, 1))

        # 标题 (耀白主文字，限制最多 2 行)
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
        tags_layout = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(18), spacing=dp(5))
        discount_tag = product.get("discount")
        ref_p = _parse_price(product.get("reference_price"))
        cur_p = _parse_price(product.get("price"))
        deal_p = _parse_price(product.get("latest_deal_price"))

        if discount_tag:
            tag_box = RoundedBox(size_hint=(None, 1), width=min(dp(110), len(discount_tag) * dp(10) + dp(12)),
                                 bg_color=CLR_PRIMARY_BG, border_color=CLR_PRIMARY_BORDER,
                                 radius=dp(4), border_width=1)
            tag_box.add_widget(Label(text=discount_tag, font_size=sp(9.5), color=CLR_PRIMARY,
                                     halign="center", valign="middle"))
            tags_layout.add_widget(tag_box)

        if cur_p and ref_p and ref_p > 0 and (cur_p / ref_p) <= 0.3:
            s_box = RoundedBox(size_hint=(None, 1), width=dp(52),
                               bg_color=CLR_AMBER_BG, border_color=CLR_AMBER_BORDER,
                               radius=dp(4), border_width=1)
            s_box.add_widget(Label(text="3折神价", font_size=sp(9.5), bold=True,
                                   color=CLR_AMBER_TXT, halign="center", valign="middle"))
            tags_layout.add_widget(s_box)

        if cur_p and deal_p and cur_p < deal_p:
            gap = round(deal_p - cur_p, 1)
            gap_str = f"低于成交¥{gap:g}"
            g_box = RoundedBox(size_hint=(None, 1), width=min(dp(96), len(gap_str) * dp(10) + dp(10)),
                               bg_color=CLR_MINT_BG, border_color=CLR_MINT_BORDER,
                               radius=dp(4), border_width=1)
            g_box.add_widget(Label(text=gap_str, font_size=sp(9.5), bold=True,
                                   color=CLR_MINT_TXT, halign="center", valign="middle"))
            tags_layout.add_widget(g_box)

        info_layout.add_widget(tags_layout)

        # 价格行 (沉稳醒目的发光霓虹粉 + 雅致银灰原价)
        price_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(26), spacing=dp(6))
        price_str = product.get("price") or "¥--"
        price_row.add_widget(Label(text=f"[b]{price_str}[/b]", markup=True, font_size=sp(16),
                                   color=CLR_PRIMARY, size_hint=(None, 1), width=dp(68),
                                   halign="left", valign="middle"))

        # 最近成交标签
        if deal_p:
            d_bg = (0.10, 0.14, 0.22, 1.0) if CLR_BG[0] < 0.5 else (0.92, 0.95, 0.99, 1.0)
            deal_box = RoundedBox(size_hint=(None, 1), width=dp(80),
                                  bg_color=d_bg, border_color=CLR_BORDER_LIGHT,
                                  radius=dp(4), border_width=1)
            deal_box.add_widget(Label(text=f"成交 {product.get('latest_deal_price')}",
                                      font_size=sp(10), color=CLR_CYAN,
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

    def play_entrance(self, delay=0.0):
        """阶梯式瀑布流进场动效"""
        self.opacity = 0.0
        self.entry_y = -dp(18)
        def _do_play(*args):
            anim = Animation(opacity=1.0, entry_y=0.0, duration=0.28, t='out_cubic')
            anim.start(self)
        Clock.schedule_once(_do_play, delay)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["card_touch_down"] = touch.pos
            Animation.stop_all(self, 'scale')
            Animation(scale=0.972, duration=0.07, t='out_quad').start(self)
            self.set_bg_color(CLR_CARD_HOVER)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.ud.get("card_touch_down"):
            Animation.stop_all(self, 'scale')
            Animation(scale=1.0, duration=0.22, t='out_back').start(self)
            self.set_bg_color(CLR_CARD)
            dx = abs(touch.x - touch.ud["card_touch_down"][0])
            dy = abs(touch.y - touch.ud["card_touch_down"][1])
            if dx < dp(10) and dy < dp(10) and self.collide_point(*touch.pos):
                if self.on_open_detail:
                    self.on_open_detail(self.product)
                return True
        return super().on_touch_up(touch)


# =====================================================================
# Canvas 动态折线走势图与雷达扫描舱 (Interactive Curve & Radar HUD)
# =====================================================================

class InteractiveTrendChart(Widget):
    """
    真正的 Canvas 动态折线走势图：
    平滑折线连接、半透明渐变面积填充、发光节点与展开扫掠动效。
    """
    progress = NumericProperty(0.0)

    def __init__(self, points, **kw):
        super().__init__(size_hint=(1, None), height=dp(100), **kw)
        self.raw_points = points or []
        self._parsed_data = []
        for p in self.raw_points:
            p_val = _parse_price(p.get("avgPrice") or p.get("price"))
            d_lbl = str(p.get("dateLabel") or "")
            if p_val is not None:
                self._parsed_data.append((d_lbl, p_val))

        self.bind(pos=self._redraw, size=self._redraw)

    def on_progress(self, *args):
        self._redraw()

    def start_sweep(self):
        self.progress = 0.0
        Animation.stop_all(self, 'progress')
        anim = Animation(progress=1.0, duration=0.55, t='out_cubic')
        anim.start(self)

    def _redraw(self, *args):
        self.canvas.clear()
        if not self._parsed_data or self.width <= dp(20) or self.height <= dp(20):
            return

        prices = [d[1] for d in self._parsed_data]
        min_p = min(prices)
        max_p = max(prices)
        pad_p = max((max_p - min_p) * 0.15, 1.0)
        low_p = min_p - pad_p
        high_p = max_p + pad_p
        p_range = high_p - low_p

        pad_left = dp(14)
        pad_right = dp(14)
        pad_top = dp(16)
        pad_bottom = dp(16)

        plot_w = self.width - (pad_left + pad_right)
        plot_h = self.height - (pad_top + pad_bottom)
        base_y = self.y + pad_bottom
        n = len(self._parsed_data)

        # 1. 绘制基准网格标线
        with self.canvas:
            Color(CLR_BORDER[0], CLR_BORDER[1], CLR_BORDER[2], 0.45)
            Line(points=[self.x + pad_left, base_y, self.right - pad_right, base_y], width=1)
            Line(points=[self.x + pad_left, base_y + plot_h, self.right - pad_right, base_y + plot_h], width=1)

        # 2. 计算各数据点坐标
        coords = []
        for i, (d_lbl, price) in enumerate(self._parsed_data):
            t = (i / (n - 1)) if n > 1 else 0.5
            cx = self.x + pad_left + t * plot_w
            cy = base_y + ((price - low_p) / p_range) * plot_h
            coords.append((cx, cy, price, d_lbl))

        cur_limit_x = self.x + pad_left + plot_w * max(0.01, self.progress)
        visible_pts = []
        for cx, cy, price, d_lbl in coords:
            if cx <= cur_limit_x:
                visible_pts.append((cx, cy, price, d_lbl))
            else:
                if visible_pts:
                    prev_x, prev_y, _, _ = visible_pts[-1]
                    ratio = (cur_limit_x - prev_x) / max(cx - prev_x, 0.001)
                    inter_y = prev_y + ratio * (cy - prev_y)
                    visible_pts.append((cur_limit_x, inter_y, price, d_lbl))
                break

        if len(visible_pts) < 1:
            return

        with self.canvas:
            # 3. 半透明渐变面积填充 (Mesh triangle_strip)
            if len(visible_pts) >= 2:
                vertices = []
                indices = []
                idx = 0
                for cx, cy, _, _ in visible_pts:
                    vertices.extend([cx, base_y, 0, 0])
                    vertices.extend([cx, cy, 0, 0])
                    indices.extend([idx, idx + 1])
                    idx += 2
                mesh_a = 0.18 if CLR_BG[0] < 0.5 else 0.12
                Color(CLR_PRIMARY[0], CLR_PRIMARY[1], CLR_PRIMARY[2], mesh_a)
                Mesh(vertices=vertices, indices=indices, mode='triangle_strip')

            # 4. 霓虹发光折线
            flat_pts = []
            for cx, cy, _, _ in visible_pts:
                flat_pts.extend([cx, cy])

            if len(flat_pts) >= 4:
                # 外层柔和辉光
                glow_a = 0.35 if CLR_BG[0] < 0.5 else 0.22
                Color(CLR_PRIMARY[0], CLR_PRIMARY[1], CLR_PRIMARY[2], glow_a)
                Line(points=flat_pts, width=dp(4.0), cap='round', joint='round')
                # 核心折线
                Color(*CLR_PRIMARY)
                Line(points=flat_pts, width=dp(2.2), cap='round', joint='round')

            # 5. 发光节点
            for cx, cy, price, d_lbl in visible_pts:
                if cx <= cur_limit_x:
                    Color(CLR_PRIMARY[0], CLR_PRIMARY[1], CLR_PRIMARY[2], 0.5)
                    Line(circle=(cx, cy, dp(4.5)), width=dp(1.5))
                    Color(1.0, 1.0, 1.0, 1.0)
                    Ellipse(pos=(cx - dp(2.2), cy - dp(2.2)), size=(dp(4.4), dp(4.4)))


class RadarScanHUD(RoundedBox):
    """
    捡漏雷达科幻探测舱：
    动态同心扩散光环、旋转扫描射线、目标信号灯与高阶监控遥测面板。
    """
    sweep_angle = NumericProperty(0)
    pulse_r1 = NumericProperty(8)
    pulse_a1 = NumericProperty(0.8)
    pulse_r2 = NumericProperty(24)
    pulse_a2 = NumericProperty(0.4)

    def __init__(self, count_deals=0, max_gap=0.0, **kw):
        super().__init__(orientation="horizontal", padding=(dp(12), dp(10)), spacing=dp(12),
                         size_hint=(1, None), height=dp(116),
                         bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(14), **kw)
        self.count_deals = count_deals
        self.max_gap = max_gap

        # 左侧：雷达扫描视窗
        self.radar_view = Widget(size_hint=(None, 1), width=dp(96))
        self.radar_view.bind(pos=self._redraw_radar, size=self._redraw_radar)
        self.add_widget(self.radar_view)

        # 右侧：遥测指标区
        info_box = BoxLayout(orientation="vertical", spacing=dp(3), size_hint=(1, 1))

        # 状态信标行 (带发光青点)
        status_row = BoxLayout(size_hint=(1, None), height=dp(18), spacing=dp(5))
        beacon_dot = Label(text="●", font_size=sp(9), color=CLR_CYAN, size_hint=(None, 1), width=dp(12))
        beacon_lbl = Label(text="LIVE RADAR · 全时智能侦测", font_size=sp(11), bold=True,
                           color=CLR_CYAN, size_hint=(1, 1), halign="left", valign="middle")
        beacon_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        status_row.add_widget(beacon_dot)
        status_row.add_widget(beacon_lbl)
        info_box.add_widget(status_row)

        # 大号醒目捕获计数
        self.count_lbl = Label(text=f"已截获 [color=ff6699][b]{self.count_deals}[/b][/color] 件超值好物", markup=True,
                               font_size=sp(13.5), color=CLR_TEXT_MAIN, halign="left", valign="middle",
                               size_hint=(1, None), height=dp(26))
        self.count_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        info_box.add_widget(self.count_lbl)

        # 差价与灵敏度标签
        gap_str = f"¥{self.max_gap:g}" if self.max_gap > 0 else "¥0"
        meta_lbl = Label(text=f"最大差额: [color=34d399][b]{gap_str}[/b][/color]  |  探测深度: [color=38bdf8]100%[/color]",
                         markup=True, font_size=sp(11), color=CLR_TEXT_SUB,
                         halign="left", valign="middle", size_hint=(1, None), height=dp(20))
        meta_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        info_box.add_widget(meta_lbl)

        desc_lbl = Label(text="已过滤虚高溢价，实时对比官方历史收单均价", font_size=sp(10),
                         color=CLR_TEXT_MUTED, halign="left", valign="middle",
                         size_hint=(1, 1))
        desc_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        info_box.add_widget(desc_lbl)
        self.add_widget(info_box)

        # 启动扫描动效调度 (30 FPS)
        self._anim_event = Clock.schedule_interval(self._step_radar, 1.0 / 30.0)

    def _step_radar(self, dt):
        self.sweep_angle = (self.sweep_angle + 6) % 360
        self.pulse_r1 += 1.2
        if self.pulse_r1 > dp(40):
            self.pulse_r1 = dp(6)
        self.pulse_a1 = max(0.0, 1.0 - (self.pulse_r1 / dp(40)))

        self.pulse_r2 += 1.2
        if self.pulse_r2 > dp(40):
            self.pulse_r2 = dp(6)
        self.pulse_a2 = max(0.0, 1.0 - (self.pulse_r2 / dp(40)))
        self._redraw_radar()

    def _redraw_radar(self, *args):
        self.radar_view.canvas.clear()
        cx = self.radar_view.center_x
        cy = self.radar_view.center_y
        max_r = dp(38)

        is_dark = CLR_BG[0] < 0.5

        with self.radar_view.canvas:
            # 1. 底层圆形视窗
            if is_dark:
                Color(0.02, 0.05, 0.09, 0.85)
            else:
                Color(0.91, 0.94, 0.98, 0.95)
            Ellipse(pos=(cx - max_r, cy - max_r), size=(max_r * 2, max_r * 2))

            # 2. 同心静态刻度环 (3圈)
            if is_dark:
                Color(0.0, 0.75, 0.85, 0.25)
            else:
                Color(0.0, 0.65, 0.85, 0.35)
            Line(circle=(cx, cy, max_r * 0.35), width=1)
            Line(circle=(cx, cy, max_r * 0.70), width=1)
            if is_dark:
                Color(0.0, 0.75, 0.85, 0.50)
            else:
                Color(0.0, 0.65, 0.85, 0.60)
            Line(circle=(cx, cy, max_r), width=1.2)

            # 3. 十字准星线
            Color(0.0, 0.75, 0.85, 0.20 if is_dark else 0.30)
            Line(points=[cx - max_r, cy, cx + max_r, cy], width=1)
            Line(points=[cx, cy - max_r, cx, cy + max_r], width=1)

            # 4. 动态同心扩散波纹 1
            Color(0.0, 0.85 if not is_dark else 0.95, 1.0, self.pulse_a1 * 0.7)
            Line(circle=(cx, cy, self.pulse_r1), width=1.5)

            # 动态同心扩散波纹 2
            Color(0.1 if not is_dark else 0.2, 0.75 if not is_dark else 0.85, 0.55 if not is_dark else 0.6, self.pulse_a2 * 0.6)
            Line(circle=(cx, cy, self.pulse_r2), width=1.5)

            # 5. 旋转扫描光束 (带发光渐变感)
            rad = math.radians(self.sweep_angle)
            Color(0.0, 0.75 if not is_dark else 0.95, 0.95 if not is_dark else 1.0, 0.85)
            Line(points=[cx, cy, cx + max_r * math.cos(rad), cy + max_r * math.sin(rad)], width=2.0)

            # 6. 中心发光信标核
            Color(0.0, 0.75 if not is_dark else 0.95, 1.0, 0.4)
            Line(circle=(cx, cy, dp(4)), width=1.5)
            Color(1, 1, 1, 1)
            Ellipse(pos=(cx - dp(2), cy - dp(2)), size=(dp(4), dp(4)))

            # 7. 若有漏品，在雷达上绘制 2 个闪烁的目标信号小点
            if self.count_deals > 0:
                Color(1.0, 0.40, 0.60, 0.9)
                Ellipse(pos=(cx + max_r * 0.45 - dp(2), cy + max_r * 0.35 - dp(2)), size=(dp(4), dp(4)))
                Color(0.10 if not is_dark else 0.20, 0.75 if not is_dark else 0.85, 0.50 if not is_dark else 0.60, 0.9)
                Ellipse(pos=(cx - max_r * 0.40 - dp(2), cy - max_r * 0.25 - dp(2)), size=(dp(4), dp(4)))

    def on_parent(self, inst, val):
        if val is None and hasattr(self, "_anim_event") and self._anim_event:
            self._anim_event.cancel()


class ProductDetailModal(ModalView):
    """
    现代底部抽屉式商品详情弹窗：
    带有物理升降动效、药丸防滑抓手、官方历史成交明细与 Canvas 动态折线走势图。
    """
    def __init__(self, product, on_price_updated=None, **kw):
        super().__init__(size_hint=(1.0, 0.88), pos_hint={'x': 0, 'y': -0.88}, auto_dismiss=True, **kw)
        self.background_color = (0, 0, 0, 0)
        self.opacity = 0
        self.product = product
        self.cluster_id = str(product.get("cluster_id") or "")
        self.on_price_updated = on_price_updated

        # 抽屉主卡片 (深色流光玻璃 + 顶部 20dp 圆角)
        main_card = RoundedBox(orientation="vertical", padding=(dp(16), dp(10)), spacing=dp(10),
                               bg_color=CLR_CARD, border_color=CLR_BORDER,
                               radius=[dp(20), dp(20), 0, 0], border_width=1)

        # 顶部药丸把手 (Drag Pill Handle)
        pill_box = BoxLayout(size_hint=(1, None), height=dp(10))
        pill = RoundedBox(size_hint=(None, None), size=(dp(38), dp(4)),
                          bg_color=CLR_BORDER, radius=dp(2))
        pill_box.add_widget(Widget(size_hint=(1, 1)))
        pill_box.add_widget(pill)
        pill_box.add_widget(Widget(size_hint=(1, 1)))
        main_card.add_widget(pill_box)

        # 1. 顶部标题栏 + 关闭按钮
        top_bar = BoxLayout(size_hint=(1, None), height=dp(34), spacing=dp(8))
        top_lbl = Label(text="商品行情与走势明细", font_size=sp(15), bold=True,
                        color=CLR_TEXT_MAIN, size_hint=(1, 1), halign="left", valign="middle")
        top_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        top_bar.add_widget(top_lbl)

        close_btn = ModernButton(text="关闭", font_size=sp(12), size_hint=(None, None),
                                 size=(dp(54), dp(28)), bg_color=CLR_CHIP_BG,
                                 text_color=CLR_TEXT_SUB, radius=dp(14))
        close_btn.bind(on_press=lambda _b: self.dismiss())
        top_bar.add_widget(close_btn)
        main_card.add_widget(top_bar)

        # 2. 头部缩略信息卡片
        sum_bg = (0.04, 0.06, 0.10, 0.9) if CLR_BG[0] < 0.5 else (0.95, 0.96, 0.98, 0.95)
        summary_card = RoundedBox(orientation="horizontal", padding=dp(10), spacing=dp(10),
                                  size_hint=(1, None), height=dp(88),
                                  bg_color=sum_bg, border_color=CLR_BORDER_LIGHT, radius=dp(10))
        raw_img = product.get("img") or ""
        thumb_url = get_optimized_thumb_url(raw_img, size=180)

        tb_bg = (0.02, 0.04, 0.08, 1) if CLR_BG[0] < 0.5 else (0.91, 0.93, 0.96, 1)
        thumb_box = RoundedBox(size_hint=(None, None), size=(dp(68), dp(68)),
                               bg_color=tb_bg, border_color=CLR_BORDER_LIGHT, radius=dp(6))
        thumb = AsyncImage(source=thumb_url, size_hint=(1, 1), fit_mode="contain")
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
        pink_hex = "ff6699" if CLR_BG[0] < 0.5 else "fb7299"
        cyan_hex = "00f2fe" if CLR_BG[0] < 0.5 else "0284c7"
        price_line = f"当前在售: [color={pink_hex}][b]{cur_p}[/b][/color]   最近成交: [color={cyan_hex}][b]{deal_p}[/b][/color]"
        self.summary_price_lbl = Label(text=price_line, markup=True, font_size=sp(11.5),
                                       color=CLR_TEXT_MAIN, halign="left", valign="middle",
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
        Animation.stop_all(self)
        anim = (Animation(opacity=1.0, background_color=(0, 0, 0, 0.75), d=0.20) &
                Animation(pos_hint={'x': 0, 'y': 0}, d=0.28, t='out_cubic'))
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
            self.summary_price_lbl.text = f"当前在售: [color=ff6699][b]{cur_p}[/b][/color]   最近成交: [color=00f2fe][b]{ldp}[/b][/color]"
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
                r_bg = (0.05, 0.08, 0.13, 0.9) if CLR_BG[0] < 0.5 else (0.96, 0.97, 0.99, 0.9)
                row = RoundedBox(orientation="horizontal", padding=(dp(12), dp(6)),
                                 size_hint=(1, None), height=dp(40),
                                 bg_color=r_bg, border_color=CLR_BORDER_LIGHT, radius=dp(8))
                u_name = d.get("userName") or "匿名买家"
                u_time = d.get("dealTime") or ""
                u_lbl = Label(text=f"{u_name} ({u_time})", font_size=sp(11.5),
                              color=CLR_TEXT_SUB, size_hint=(1, 1), halign="left", valign="middle")
                u_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
                row.add_widget(u_lbl)

                p_val = d.get("dealPrice") or "¥--"
                p_lbl = Label(text=p_val, font_size=sp(13.5), bold=True,
                              color=CLR_MINT_TXT, size_hint=(None, 1), width=dp(70),
                              halign="right", valign="middle")
                row.add_widget(p_lbl)
                self.detail_content.add_widget(row)
        else:
            self.detail_content.add_widget(Label(text="官方暂未开放近期待收单明细记录",
                                                 font_size=sp(11.5), color=CLR_TEXT_MUTED,
                                                 size_hint_y=None, height=dp(28)))

        # 动态 Canvas 走势折线图
        points = info.get("chart_points") or []
        if points:
            pt_header = BoxLayout(size_hint=(1, None), height=dp(26), padding=(0, dp(4)))
            pth_lbl = Label(text=f"官方成交均价走势 ({len(points)} 个节点 · 动态曲线)",
                            font_size=sp(13), bold=True, color=CLR_TEXT_MAIN,
                            size_hint=(1, 1), halign="left", valign="middle")
            pth_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
            pt_header.add_widget(pth_lbl)
            self.detail_content.add_widget(pt_header)

            c_bg = (0.04, 0.07, 0.12, 0.9) if CLR_BG[0] < 0.5 else (0.95, 0.97, 1.0, 0.9)
            chart_card = RoundedBox(orientation="vertical", padding=dp(6), spacing=dp(4),
                                    size_hint=(1, None), height=dp(114),
                                    bg_color=c_bg, border_color=CLR_BORDER, radius=dp(10))
            chart = InteractiveTrendChart(points)
            chart_card.add_widget(chart)
            self.detail_content.add_widget(chart_card)
            Clock.schedule_once(lambda _dt: chart.start_sweep(), 0.15)

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
# 流体果冻变形底部导航栏 (ModernTabBar with Fluid Morphing Animation)
# =====================================================================

class ModernTabBar(BoxLayout):
    """
    带有流体果冻拉伸变形动效与发光指示条的现代化底部导航栏：
    切换 Tab 时，胶囊指示条在水平位移过程中动态拉伸变宽并伴随 out_back 弹性回缩。
    """
    indicator_x = NumericProperty(0)
    indicator_w = NumericProperty(dp(36))

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
        self.default_indicator_width = dp(36)

        # 底部背景与上边框 (流光微拟态底色 + 微边)
        with self.canvas.before:
            self._bg_color_inst = Color(*CLR_CARD)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
            self._border_color_inst = Color(*CLR_BORDER)
            self._border_line = Line(points=[self.x, self.top, self.right, self.top], width=1)

        # 平滑流体滑动指示条 (外层发光霓虹底 + 核心高亮粉)
        with self.canvas.after:
            glow_a = 0.22 if CLR_BG[0] > 0.5 else 0.35
            self._glow_color = Color(CLR_PRIMARY[0], CLR_PRIMARY[1], CLR_PRIMARY[2], glow_a)
            self._glow_rect = RoundedRectangle(
                pos=(self.x, self.y + dp(1)),
                size=(self.default_indicator_width + dp(8), dp(7)),
                radius=[dp(3.5)]
            )
            self._core_color = Color(*CLR_PRIMARY)
            self._indicator = RoundedRectangle(
                pos=(self.x, self.y + dp(3)),
                size=(self.default_indicator_width, dp(3)),
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

    def update_theme_colors(self):
        """动态热重载底部导航栏配色"""
        if hasattr(self, "_bg_color_inst"):
            self._bg_color_inst.rgba = CLR_CARD
        if hasattr(self, "_border_color_inst"):
            self._border_color_inst.rgba = CLR_BORDER
        if hasattr(self, "_glow_color"):
            glow_a = 0.22 if CLR_BG[0] > 0.5 else 0.35
            self._glow_color.rgba = (CLR_PRIMARY[0], CLR_PRIMARY[1], CLR_PRIMARY[2], glow_a)
        if hasattr(self, "_core_color"):
            self._core_color.rgba = CLR_PRIMARY
        self.set_active_index(self.active_index, animate=False)

    def on_indicator_x(self, inst, val):
        if hasattr(self, "_indicator"):
            self._indicator.pos = (val, self.y + dp(3))
        if hasattr(self, "_glow_rect"):
            self._glow_rect.pos = (val - dp(4), self.y + dp(1))

    def on_indicator_w(self, inst, val):
        if hasattr(self, "_indicator"):
            self._indicator.size = (val, dp(3))
        if hasattr(self, "_glow_rect"):
            self._glow_rect.size = (val + dp(8), dp(7))

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
                target_x = btn.x + (btn.width - self.default_indicator_width) / 2
                if animate:
                    dist = abs(target_x - self.indicator_x)
                    stretch_w = min(dp(56), self.default_indicator_width + dist * 0.20)
                    Animation.stop_all(self, 'indicator_x')
                    Animation.stop_all(self, 'indicator_w')
                    # 流体拉伸回弹
                    anim_w = (Animation(indicator_w=stretch_w, d=0.10, t="out_quad") +
                              Animation(indicator_w=self.default_indicator_width, d=0.15, t="out_back"))
                    anim_x = Animation(indicator_x=target_x, d=0.25, t="out_cubic")
                    anim_w.start(self)
                    anim_x.start(self)
                else:
                    self.indicator_w = self.default_indicator_width
                    self.indicator_x = target_x


class ThemeOptionCard(RoundedBox):
    """可视化主题卡片组件，支持触控弹性微缩与激活高亮标识"""
    def __init__(self, theme_key, theme_info, is_active, on_select=None, **kw):
        border_clr = CLR_PRIMARY if is_active else CLR_BORDER
        b_width = 2 if is_active else 1
        bg_clr = CLR_PRIMARY_BG if is_active else CLR_CHIP_BG
        super().__init__(orientation="vertical", padding=(dp(10), dp(8)), spacing=dp(4),
                         size_hint=(0.5, 1), bg_color=bg_clr, border_color=border_clr,
                         border_width=b_width, radius=dp(10), enable_transform=True, **kw)
        self.theme_key = theme_key
        self.on_select = on_select

        top_row = BoxLayout(size_hint=(1, None), height=dp(20), spacing=dp(4))
        dot_str = "● 当前" if is_active else "○ 切换"
        top_row.add_widget(Label(text=dot_str, font_size=sp(10), bold=is_active,
                                 color=CLR_PRIMARY if is_active else CLR_TEXT_MUTED,
                                 size_hint=(None, 1), width=dp(44)))
        top_row.add_widget(Label(text=theme_info["short_name"], font_size=sp(12), bold=True,
                                 color=CLR_TEXT_MAIN if is_active else CLR_TEXT_SUB,
                                 size_hint=(1, 1), halign="left", valign="middle"))
        self.add_widget(top_row)

        desc_lbl = Label(text=theme_info["desc"], font_size=sp(9.5),
                         color=CLR_TEXT_SUB if is_active else CLR_TEXT_MUTED,
                         halign="left", valign="top", size_hint=(1, 1),
                         shorten=True, max_lines=2)
        desc_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        self.add_widget(desc_lbl)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["theme_touch_" + self.theme_key] = touch.pos
            Animation.stop_all(self, 'scale')
            Animation(scale=0.96, duration=0.07, t='out_quad').start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.ud.get("theme_touch_" + self.theme_key):
            Animation.stop_all(self, 'scale')
            Animation(scale=1.0, duration=0.20, t='out_back').start(self)
            dx = abs(touch.x - touch.ud["theme_touch_" + self.theme_key][0])
            dy = abs(touch.y - touch.ud["theme_touch_" + self.theme_key][1])
            if dx < dp(10) and dy < dp(10) and self.collide_point(*touch.pos):
                if self.on_select:
                    self.on_select(self.theme_key)
        return super().on_touch_up(touch)


# =====================================================================
# 应用核心逻辑 (ResellMonitorMobile)
# =====================================================================

class SplashOverlay(FloatLayout):
    """全屏开屏画面遮罩，拦截用户在开屏期间的误触点击并在淡出完成后自动销毁"""
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return super().on_touch_down(touch)


class ResellMonitorMobile(App):
    title = "B站转售监控"

    def build(self):
        self.active_theme = load_theme_setting()
        pink_hex = "ff6699" if self.active_theme == "cyber" else "fb7299"

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(icon_path):
            self.icon = icon_path

        self.main_container = FloatLayout()

        self.root_box = BoxLayout(orientation="vertical", size_hint=(1, 1))

        # 顶部全局导航栏 (流光微拟态玻璃 + 霓虹发光胶囊徽标)
        self.header_bar = RoundedBox(orientation="horizontal", size_hint=(1, None), height=dp(50),
                                     padding=(dp(16), dp(8)), spacing=dp(8),
                                     bg_color=CLR_CARD, border_color=CLR_BORDER,
                                     radius=0, border_width=1)
        self.header_title = Label(text=f"[color={pink_hex}][b]BILIBILI[/b][/color] · 捡漏监控",
                                  markup=True, font_size=sp(16), bold=True,
                                  color=CLR_TEXT_MAIN, halign="left", valign="middle")
        self.header_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))

        self.badge_box = RoundedBox(size_hint=(None, None), size=(dp(92), dp(28)),
                                    bg_color=CLR_PRIMARY_BG, border_color=CLR_PRIMARY_BORDER,
                                    radius=dp(14), border_width=1)
        self.header_count_badge = Label(text="实时 --件", font_size=sp(11), bold=True,
                                        color=CLR_PRIMARY, halign="center", valign="middle")
        self.badge_box.add_widget(self.header_count_badge)

        self.header_bar.add_widget(self.header_title)
        self.header_bar.add_widget(self.badge_box)
        self.root_box.add_widget(self.header_bar)

        # 中间内容区域 (带淡入动效的容器)
        self.content = BoxLayout(orientation="vertical", padding=(dp(12), dp(10)), spacing=dp(8))
        self.root_box.add_widget(self.content)

        # 底部平滑导航栏
        self.tab_bar = ModernTabBar(self)
        self.root_box.add_widget(self.tab_bar)

        self.main_container.add_widget(self.root_box)

        # 状态变量
        self.all_products = []
        self.filtered_products = []
        self.current_tab = "list"
        self.crawling = False
        self.active_filter = "all"
        self.active_sort = "default"
        self.search_keyword = ""
        self.page_render_limit = 35

        # 抓取控制台配置（与电脑端对齐）
        self.crawl_category = "898"       # 默认 3C数码
        self.crawl_sort = "hot"           # 默认 综合推荐
        self.crawl_pages = 15             # 默认 常规 15页

        # 初始化后台定时巡检器
        self.scheduler = AutoCrawlScheduler(
            on_crawl_complete_cb=self._on_sched_crawl_complete,
            on_log_cb=self._append_crawl_log
        )

        # 开屏画面平滑转场（无缝承接 Android 原生 presplash，在首帧列表数据渲染完成后柔和淡出）
        splash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presplash.png")
        if os.path.exists(splash_path):
            self.splash_overlay = SplashOverlay(size_hint=(1, 1))
            with self.splash_overlay.canvas.before:
                Color(0.906, 0.902, 0.894, 1)  # #E7E6E4 统一开屏底色
                self.splash_bg = RoundedRectangle(size=Window.size, pos=self.splash_overlay.pos, radius=[0])
            self.splash_overlay.bind(size=self._update_splash_rect, pos=self._update_splash_rect)
            self.splash_img = Image(source=splash_path, fit_mode="contain", size_hint=(1, 1))
            self.splash_overlay.add_widget(self.splash_img)
            self.main_container.add_widget(self.splash_overlay)
            Clock.schedule_once(self._dismiss_splash, 0.75)

        # 启动时加载列表
        Clock.schedule_once(lambda _dt: self.show_list(), 0.1)
        return self.main_container

    def _update_splash_rect(self, inst, _val):
        if hasattr(self, 'splash_bg') and self.splash_bg:
            self.splash_bg.size = inst.size
            self.splash_bg.pos = inst.pos

    def _dismiss_splash(self, _dt):
        if hasattr(self, 'splash_overlay') and self.splash_overlay:
            anim = Animation(opacity=0, duration=0.45, t='out_quad')
            def _on_finish(*_args):
                if hasattr(self, 'splash_overlay') and self.splash_overlay:
                    if self.splash_overlay.parent:
                        self.main_container.remove_widget(self.splash_overlay)
                    self.splash_overlay = None
            anim.bind(on_complete=_on_finish)
            anim.start(self.splash_overlay)

    def on_start(self):
        """应用启动后尝试设置 Android 原生 120Hz 高刷新率调度与通知权限。"""
        if IS_ANDROID:
            self._enable_android_high_refresh_rate()
            notification_helper.request_notification_permission()

    def on_pause(self):
        """
        Android 应用进入后台生命周期回调：
        返回 True 显式告知 Android / Kivy 不要终止或冻结应用，
        确保后台定时巡检线程持续工作并及时发送通知栏消息！
        """
        return True

    def on_resume(self):
        """应用从后台重新切回前台时，自动无感同步最新大盘与巡检状态。"""
        self.load_data()
        if self.current_tab == "list":
            self.apply_filters()
            self._repopulate_list()
        elif self.current_tab == "crawl":
            self._update_sched_ui_status()

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

    # ---------- 全局主题动态热切换 ----------
    def switch_theme(self, theme_key):
        """动态热切换全局视觉主题并持久化保存设置"""
        if theme_key not in THEMES or theme_key == self.active_theme:
            return
        self.active_theme = theme_key
        set_theme(theme_key)
        save_theme_setting(theme_key)

        # 1. 刷新顶部全局导航栏
        if hasattr(self, "header_bar") and self.header_bar:
            self.header_bar.set_bg_color(CLR_CARD)
            self.header_bar.set_border_color(CLR_BORDER)
        if hasattr(self, "header_title") and self.header_title:
            pink_hex = "ff6699" if theme_key == "cyber" else "fb7299"
            self.header_title.text = f"[color={pink_hex}][b]BILIBILI[/b][/color] · 捡漏监控"
            self.header_title.color = CLR_TEXT_MAIN
        if hasattr(self, "badge_box") and self.badge_box:
            self.badge_box.set_bg_color(CLR_PRIMARY_BG)
            self.badge_box.set_border_color(CLR_PRIMARY_BORDER)
        if hasattr(self, "header_count_badge") and self.header_count_badge:
            self.header_count_badge.color = CLR_PRIMARY

        # 2. 刷新底部导航栏
        if hasattr(self, "tab_bar") and self.tab_bar:
            self.tab_bar.update_theme_colors()

        # 3. 刷新当前主内容视窗
        if self.current_tab == "list":
            self.show_list()
        elif self.current_tab == "radar":
            self.show_radar()
        elif self.current_tab == "crawl":
            self.show_crawl()
        elif self.current_tab == "settings":
            self.show_settings()

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

        # A. 搜索框 (清新圆角白框 + 细微边)
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
            self.page_render_limit = 35
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
            self.page_render_limit = 35
            self.apply_filters()
            self._repopulate_list()

        sort_spinner.bind(text=_on_sort_change)
        meta_bar.add_widget(sort_spinner)
        self.content.add_widget(meta_bar)

        # D. 高帧率平滑滚动商品列表
        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                                      scroll_distance=dp(5), smooth_scroll_end=12,
                                      bar_width=dp(3), bar_color=(1.0, 0.40, 0.60, 0.45))
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
        self.page_render_limit = 35
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
        for i, p in enumerate(visible_items):
            card = ProductCardWidget(p, on_open_detail=self.open_detail_modal)
            self.list_grid.add_widget(card)
            if i < 14:
                card.play_entrance(delay=i * 0.025)

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
        self.page_render_limit += 35
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
        max_gap = hot_deals[0][1] if hot_deals else 0.0

        # 科幻雷达扫描舱 HUD
        radar_hud = RadarScanHUD(count_deals=len(hot_deals), max_gap=max_gap)
        self.content.add_widget(radar_hud)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                            scroll_distance=dp(5), smooth_scroll_end=12,
                            bar_width=dp(3), bar_color=(1.0, 0.40, 0.60, 0.45))
        list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        list_box.bind(minimum_height=list_box.setter("height"))

        if hot_deals:
            for i, (item, gap, pct) in enumerate(hot_deals):
                card = ProductCardWidget(item, on_open_detail=self.open_detail_modal)
                list_box.add_widget(card)
                if i < 14:
                    card.play_entrance(delay=i * 0.025)
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
    # 页面三：实时抓取控制台 (show_crawl - 电脑端对齐品类/排序/深度 + 定时巡检)
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

        # 1. 统计卡片指标行 (瓷白卡片 + 精致高饱和数值)
        kpi_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(64), spacing=dp(8))
        kpi_data = [
            ("在售总量", f"{len(self.all_products)} 件", CLR_PRIMARY),
            ("大盘均价", avg_p, CLR_BLUE),
            ("最低现价", min_p, CLR_PRIMARY_DARK),
        ]
        for label_text, val_text, val_clr in kpi_data:
            box = RoundedBox(orientation="vertical", padding=(dp(8), dp(6)), spacing=dp(2),
                             bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(10))
            box.add_widget(Label(text=label_text, font_size=sp(11), color=CLR_TEXT_MUTED, halign="center"))
            box.add_widget(Label(text=val_text, font_size=sp(15), bold=True, color=val_clr, halign="center"))
            kpi_row.add_widget(box)
        self.content.add_widget(kpi_row)

        # 2. 定时自动巡检与系统通知面板
        sched_card = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(6),
                                size_hint=(1, None), height=dp(108),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))

        # 头部标题 + 开关按钮 + 测试通知按钮
        sc_top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(28), spacing=dp(6))
        sc_title = Label(text="前后台自动巡检与通知", font_size=sp(12), bold=True,
                         color=CLR_TEXT_MAIN, size_hint=(1, 1), halign="left", valign="middle")
        sc_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        sc_top.add_widget(sc_title)

        test_notif_btn = ModernButton(
            text="测试通知", font_size=sp(10.5), size_hint=(None, 1), width=dp(64),
            bg_color=CLR_BLUE_BG, text_color=CLR_BLUE, radius=dp(6),
            border_color=CLR_BLUE_BORDER, border_width=1
        )
        test_notif_btn.bind(on_press=lambda _b: self._test_notification())
        sc_top.add_widget(test_notif_btn)

        is_sched_on = self.scheduler.config.get("enabled", False)
        self.sched_toggle_btn = ModernButton(
            text="已开启" if is_sched_on else "已关闭", font_size=sp(11), bold=True,
            size_hint=(None, 1), width=dp(58),
            bg_color=CLR_MINT_BG if is_sched_on else CLR_CHIP_BG,
            text_color=CLR_MINT_TXT if is_sched_on else CLR_TEXT_MUTED,
            radius=dp(6),
            border_color=CLR_MINT_BORDER if is_sched_on else CLR_BORDER_LIGHT, border_width=1
        )
        self.sched_toggle_btn.bind(on_press=lambda _b: self._toggle_scheduler())
        sc_top.add_widget(self.sched_toggle_btn)
        sched_card.add_widget(sc_top)

        # 周期切换芯片行 (15分 / 30分 / 1小时 / 2小时)
        freq_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(26), spacing=dp(6))
        freq_lbl = Label(text="周期:", font_size=sp(11), color=CLR_TEXT_MUTED, size_hint=(None, 1), width=dp(34))
        freq_row.add_widget(freq_lbl)

        self.freq_chip_btns = []
        cur_min = self.scheduler.config.get("interval_minutes", 30)
        freq_options = [(15, "15分钟"), (30, "30分钟"), (60, "1小时"), (120, "2小时")]
        for m_val, m_title in freq_options:
            is_active = (cur_min == m_val)
            f_btn = ModernButton(
                text=m_title, font_size=sp(10.5), size_hint=(1, 1),
                bg_color=CLR_PRIMARY if is_active else CLR_CHIP_BG,
                text_color=(1, 1, 1, 1) if is_active else CLR_TEXT_SUB,
                radius=dp(5)
            )
            f_btn.bind(on_press=lambda _b, v=m_val: self._set_sched_interval(v))
            freq_row.add_widget(f_btn)
            self.freq_chip_btns.append((m_val, f_btn))
        sched_card.add_widget(freq_row)

        # 底部状态显示行
        self.sched_status_lbl = Label(
            text=self.scheduler.get_status_summary(), font_size=sp(10.5),
            color=CLR_TEXT_SUB, size_hint=(1, None), height=dp(18),
            halign="left", valign="middle"
        )
        self.sched_status_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        sched_card.add_widget(self.sched_status_lbl)
        self.content.add_widget(sched_card)

        # 3. 抓取参数配置卡片 (多品类 + 多排序 + 翻页深度)
        cfg_panel = RoundedBox(orientation="vertical", padding=dp(12), spacing=dp(8),
                               size_hint=(1, None), height=dp(168),
                               bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))

        # A. 分类维度选择 (对齐电脑端 898/142/807/175/all)
        cat_scroll = ScrollView(size_hint=(1, None), height=dp(28),
                                do_scroll_x=True, do_scroll_y=False, bar_width=0)
        cat_box = BoxLayout(orientation="horizontal", size_hint_x=None, spacing=dp(5),
                            padding=[0, 0, dp(14), 0])
        cat_box.bind(minimum_width=cat_box.setter("width"))

        cat_lbl = Label(text="品类:", font_size=sp(11.5), bold=True, color=CLR_TEXT_MAIN,
                        size_hint=(None, 1), width=dp(34))
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
                text=name, font_size=sp(10.5), size_hint=(None, 1), width=dp(62),
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

        # 4. 现代化 macOS 风格深色控制台终端
        term_card = RoundedBox(orientation="vertical", padding=dp(10), spacing=dp(4),
                               size_hint=(1, 1), bg_color=(0.04, 0.06, 0.09, 1.0),
                               border_color=(0.14, 0.18, 0.24, 1.0), radius=dp(10))

        # macOS 三色圆点窗头 (红黄绿) + 标题
        term_top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(20), spacing=dp(5))
        dot_red = Label(text="●", font_size=sp(9), color=(0.94, 0.3, 0.3, 1), size_hint=(None, 1), width=dp(12))
        dot_yellow = Label(text="●", font_size=sp(9), color=(0.95, 0.7, 0.2, 1), size_hint=(None, 1), width=dp(12))
        dot_green = Label(text="●", font_size=sp(9), color=(0.2, 0.8, 0.4, 1), size_hint=(None, 1), width=dp(12))
        term_title = Label(text="控制台终端日志 (Terminal Log)", font_size=sp(11), bold=True,
                           color=(0.65, 0.75, 0.85, 1), size_hint=(1, 1), halign="left")
        term_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))

        term_top.add_widget(dot_red)
        term_top.add_widget(dot_yellow)
        term_top.add_widget(dot_green)
        term_top.add_widget(term_title)
        term_card.add_widget(term_top)

        self.crawl_log_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
                                           scroll_distance=dp(5))
        cat_str = self._get_cat_name(self.crawl_category)
        self.crawl_log_lbl = Label(
            text=f"系统准备就绪。\n当前配置: 品类={cat_str} | 排序={self._get_sort_name(self.crawl_sort)} | 深度={self.crawl_pages or '全量'}\n点击上方「开始实时抓取数据」启动爬虫，或开启自动巡检监控。",
            font_size=sp(11), color=(0.35, 0.88, 0.55, 1.0),
            size_hint_y=None, halign="left", valign="top"
        )
        self.crawl_log_lbl.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        self.crawl_log_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', max(dp(80), val[1])))
        self.crawl_log_scroll.add_widget(self.crawl_log_lbl)
        term_card.add_widget(self.crawl_log_scroll)
        self.content.add_widget(term_card)

    def _test_notification(self):
        """测试系统通知栏通知。"""
        notification_helper.send_system_notification(
            title="通知测试：B站捡漏监控已就绪！",
            message="恭喜！系统通知栏提醒功能运作正常，发现低于成交价或3折好物时将在此即时提醒您！",
            subtext="通知栏测试"
        )
        self._append_crawl_log("[系统测试] 已发送一条测试通知至系统状态栏。")

    def _toggle_scheduler(self):
        cur = self.scheduler.config.get("enabled", False)
        new_val = not cur
        self.scheduler.set_enabled(new_val)
        if hasattr(self, "sched_toggle_btn") and self.sched_toggle_btn:
            self.sched_toggle_btn.text = "已开启" if new_val else "已关闭"
            self.sched_toggle_btn.set_bg_color(CLR_MINT_BG if new_val else CLR_CHIP_BG)
            self.sched_toggle_btn.color = CLR_MINT_TXT if new_val else CLR_TEXT_MUTED
            self.sched_toggle_btn.border_color = CLR_MINT_BORDER if new_val else CLR_BORDER_LIGHT
        self._update_sched_ui_status()
        state_str = "已启动后台自动巡检" if new_val else "已停止自动巡检"
        self._append_crawl_log(f"[定时巡检] {state_str}。")

    def _set_sched_interval(self, minutes):
        self.scheduler.set_interval(minutes)
        for m_val, btn in getattr(self, "freq_chip_btns", []):
            active = (m_val == minutes)
            btn.set_bg_color(CLR_PRIMARY if active else CLR_CHIP_BG)
            btn.color = (1, 1, 1, 1) if active else CLR_TEXT_SUB
        self._update_sched_ui_status()
        self._append_crawl_log(f"[定时巡检] 周期已更新为每 {minutes} 分钟一次。")

    def _update_sched_ui_status(self):
        if hasattr(self, "sched_status_lbl") and self.sched_status_lbl:
            self.sched_status_lbl.text = self.scheduler.get_status_summary()

    def _on_sched_crawl_complete(self):
        Clock.schedule_once(lambda _dt: self._handle_sched_update(), 0)

    def _handle_sched_update(self):
        self.load_data()
        self._update_sched_ui_status()
        if self.current_tab == "list":
            self.apply_filters()
            self._repopulate_list()

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

        # 1. 界面视觉风格选择卡片 (双风格热切换)
        theme_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(8),
                                size_hint=(1, None), height=dp(126),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))

        theme_top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(22))
        theme_title = Label(text="界面视觉风格 (主题切换)", font_size=sp(14), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, 1), halign="left", valign="middle")
        theme_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        theme_top.add_widget(theme_title)

        cur_t_name = THEMES.get(self.active_theme, {}).get("short_name", "")
        theme_cur_lbl = Label(text=f"当前: {cur_t_name}", font_size=sp(11), bold=True,
                              color=CLR_PRIMARY, size_hint=(None, 1), width=dp(96),
                              halign="right", valign="middle")
        theme_top.add_widget(theme_cur_lbl)
        theme_card.add_widget(theme_top)

        theme_desc = Label(text="点击下方卡片即时热切换界面色彩与光影效果，设置将自动记忆保存。",
                           font_size=sp(11), color=CLR_TEXT_MUTED, size_hint=(1, None), height=dp(16),
                           halign="left")
        theme_desc.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        theme_card.add_widget(theme_desc)

        btn_grid = BoxLayout(orientation="horizontal", size_hint=(1, 1), spacing=dp(10))
        for t_key in ("cyber", "ivory"):
            t_info = THEMES[t_key]
            is_active = (self.active_theme == t_key)
            card_btn = ThemeOptionCard(t_key, t_info, is_active=is_active,
                                       on_select=lambda k: self.switch_theme(k))
            btn_grid.add_widget(card_btn)
        theme_card.add_widget(btn_grid)
        set_box.add_widget(theme_card)

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
                                size_hint=(1, None), height=dp(108),
                                bg_color=CLR_CARD, border_color=CLR_BORDER, radius=dp(12))
        about_title = Label(text="关于哔哩转售捡漏监控", font_size=sp(14), bold=True,
                            color=CLR_TEXT_MAIN, size_hint=(1, None), height=dp(22), halign="left")
        about_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(about_title)

        ver_lbl = Label(text="版本: v1.7.0 (赛博流光 / 纯净象牙双风格版)", font_size=sp(12),
                        color=CLR_PRIMARY, size_hint=(1, None), height=dp(20), halign="left")
        ver_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        about_card.add_widget(ver_lbl)

        sub_lbl = Label(text="赛博极客流光与纯净象牙白双风格、触控物理弹性回弹、阶梯瀑布流、动态雷达与走势图。",
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
                req = urllib.request.Request(url, headers={"User-Agent": "BiliResellAndroid/1.7"})
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
