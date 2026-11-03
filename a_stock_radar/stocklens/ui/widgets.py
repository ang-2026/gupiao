# -*- coding: utf-8 -*-
"""可复用的 Kivy 组件：卡片、标签、表格行、走势图、标签页按钮。"""
from __future__ import annotations

from kivy.clock import Clock
from kivy.graphics import Color, InstructionGroup, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from . import theme


def _font() -> str:
    return theme.CJK_FONT if theme._FONT_READY else "Roboto"


# --------------------------------------------------------------------------- #
# 卡片
# --------------------------------------------------------------------------- #
class Card(BoxLayout):
    """圆角卡片。"""

    bg = ListProperty(theme.SURFACE)

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(12))
        kwargs.setdefault("spacing", dp(6))
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color = Color(rgba=self.bg)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync, bg=self._sync_color)

    def _sync(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _sync_color(self, *_):
        self._bg_color.rgba = self.bg


class TapCard(ButtonBehavior, Card):
    """可点击卡片（按下时高亮）。"""

    def on_press(self):
        self.bg = theme.SURFACE_2

    def on_release(self):
        self.bg = theme.SURFACE


class AutoCard(Card):
    """高度随内容自动计算的卡片（放在滚动列表里用）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(minimum_height=self._fit)
        Clock.schedule_once(self._fit, 0)

    def _fit(self, *_):
        self.height = self.minimum_height


class TapAutoCard(ButtonBehavior, AutoCard):
    """可点击 + 自适应高度卡片。"""

    def on_press(self):
        self.bg = theme.SURFACE_2

    def on_release(self):
        self.bg = theme.SURFACE


# --------------------------------------------------------------------------- #
# 文本
# --------------------------------------------------------------------------- #
class Txt(Label):
    """统一字体、颜色的单行文本（文本块尺寸随控件尺寸变化）。"""

    def __init__(self, text: str = "", size: float = 13, color=None, bold: bool = False,
                 align: str = "left", valign: str = "middle", **kwargs):
        super().__init__(
            text=text,
            font_name=_font(),
            font_size=sp(size),
            bold=bold,
            color=color or theme.TEXT,
            halign=align,
            valign=valign,
            markup=kwargs.pop("markup", False),
            **kwargs,
        )
        self.bind(size=lambda inst, val: setattr(inst, "text_size", val))


class WrapLabel(Txt):
    """可换行的多行文本，高度随内容自动变化。"""

    def __init__(self, text: str = "", size: float = 12, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(18))
        super().__init__(text=text, size=size, valign="top", **kwargs)
        self.bind(width=self._relayout, text=self._relayout)
        Clock.schedule_once(self._relayout, 0)

    def _relayout(self, *_):
        self.text_size = (max(dp(10), self.width), None)
        self.texture_update()
        self.height = self.texture_size[1] + dp(2)


class Cell(Txt):
    """表格单元格。"""

    def __init__(self, weight: float = 1, **kwargs):
        kwargs.setdefault("size_hint_x", weight)
        super().__init__(**kwargs)


class TableRow(BoxLayout):
    """一行数据；weights 为各列宽度比例。"""

    def __init__(self, values: list[str], weights: list[float], colors=None,
                 height: float = dp(30), size: float = 11.5, bold: bool = False,
                 align: str = "center", **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", height)
        kwargs.setdefault("spacing", dp(2))
        super().__init__(orientation="horizontal", **kwargs)
        colors = colors or [theme.TEXT] * len(values)
        aligns = align if isinstance(align, list) else [align] * len(values)
        for idx, value in enumerate(values):
            self.add_widget(
                Cell(
                    weight=weights[idx] if idx < len(weights) else 1,
                    text=str(value),
                    size=size,
                    color=colors[idx] if idx < len(colors) else theme.TEXT,
                    bold=bold,
                    align=aligns[idx] if idx < len(aligns) else "center",
                )
            )


class Divider(Widget):
    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(1))
        super().__init__(**kwargs)
        with self.canvas:
            self._color = Color(rgba=theme.LINE)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class Chip(Label):
    """小标签（相关度、方向、涨跌）。"""

    def __init__(self, text: str = "", color=None, bg=None, size: float = 10, **kwargs):
        self.chip_bg = bg or [0.2, 0.25, 0.32, 0.9]
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(40), dp(18)))
        super().__init__(
            text=text,
            font_name=_font(),
            font_size=sp(size),
            color=color or theme.MUTED,
            halign="center",
            valign="middle",
            **kwargs,
        )
        with self.canvas.before:
            self._bg_color = Color(rgba=self.chip_bg)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
        self.bind(pos=self._sync, size=self._sync)
        self.bind(texture_size=self._fit)

    def _sync(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _fit(self, *_):
        width = max(dp(34), self.texture_size[0] + dp(14))
        height = max(dp(18), self.texture_size[1] + dp(4))
        if abs(width - self.width) > 1 or abs(height - self.height) > 1:
            self.size = (width, height)


class FlatButton(ButtonBehavior, Label):
    """扁平按钮，外观完全自绘。"""

    bg = ListProperty(theme.SURFACE_2)
    pressed_bg = ListProperty(theme.LINE)
    radius = NumericProperty(10)

    def __init__(self, text: str = "", color=None, font_size: float = 13, **kwargs):
        if not any(k in kwargs for k in ("size_hint", "size_hint_x", "size_hint_y")):
            kwargs["size_hint"] = (None, None)
        kwargs.setdefault("size", (dp(80), dp(34)))
        super().__init__(
            text=text,
            font_name=_font(),
            font_size=sp(font_size),
            color=color or theme.TEXT,
            halign="center",
            valign="middle",
            **kwargs,
        )
        with self.canvas.before:
            self._bg_color = Color(rgba=self.bg)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size,
                                             radius=[dp(self.radius)])
        self.bind(pos=self._sync, size=self._sync, bg=self._color)

    def _sync(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self.text_size = (max(dp(4), self.width - dp(8)), self.height)

    def _color(self, *_):
        self._bg_color.rgba = self.bg

    def on_press(self):
        self._bg_color.rgba = self.pressed_bg

    def on_release(self):
        self._bg_color.rgba = self.bg


class TabButton(ButtonBehavior, Label):
    """标签页按钮，选中时下方有高亮条。"""

    active = BooleanProperty(False)

    def __init__(self, text: str = "", **kwargs):
        super().__init__(
            text=text,
            font_name=_font(),
            font_size=sp(13),
            color=theme.MUTED,
            halign="center",
            valign="middle",
            **kwargs,
        )
        with self.canvas.after:
            self._bar_color = Color(rgba=theme.ACCENT[:3] + [0.0])
            self._bar = Line(points=[], width=dp(2))
        self.bind(pos=self._sync, size=self._sync, active=self._on_active)
        self._on_active()
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_):
        y = self.y + dp(2)
        self._bar.points = [self.x + dp(8), y, self.right - dp(8), y]

    def _on_active(self, *_):
        self.color = theme.TEXT if self.active else theme.MUTED
        self._bar_color.a = 1.0 if self.active else 0.0
        self.bold = self.active


# --------------------------------------------------------------------------- #
# 走势图：收盘价折线 + 成交量柱
# --------------------------------------------------------------------------- #
class PriceVolumeChart(Widget):
    """轻量走势图（纯 canvas 绘制，不依赖 matplotlib）。"""

    rows = ListProperty([])

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(170))
        super().__init__(**kwargs)
        self._group = InstructionGroup()
        self.canvas.add(self._group)
        self._labels: list = []
        self.bind(pos=self._redraw, size=self._redraw, rows=self._redraw)

    def set_rows(self, rows):
        self.rows = list(rows or [])
        self._redraw()

    # ------------------------------------------------------------------ #
    def _redraw(self, *_):
        rows = self.rows
        self._clear()
        if not rows or self.width <= dp(20) or self.height <= dp(20):
            return

        pad_l, pad_r = dp(8), dp(8)
        pad_t, pad_b = dp(16), dp(16)
        plot_w = max(1.0, self.width - pad_l - pad_r)
        body_h = max(1.0, self.height - pad_t - pad_b)
        price_h = body_h * 0.72
        vol_h = body_h * 0.20
        vol_top = self.y + pad_b

        highs = [r.high for r in rows] or [r.close for r in rows]
        lows = [r.low for r in rows] or [r.close for r in rows]
        hi, lo = max(highs), min(lows)
        if hi <= lo:
            hi, lo = hi + 0.01, lo - 0.01
        span = hi - lo
        hi += span * 0.05
        lo -= span * 0.05
        span = hi - lo

        max_vol = max((r.volume for r in rows), default=1.0) or 1.0
        n = len(rows)
        step = plot_w / max(1, n - 1) if n > 1 else 0.0
        bar_w = max(dp(1), plot_w / max(1, n) * 0.6)

        def px(idx: int) -> float:
            return self.x + pad_l + (step * idx if n > 1 else plot_w / 2)

        def py(price: float) -> float:
            return vol_top + vol_h + dp(6) + (price - lo) / span * price_h

        self._group.add(Color(1, 1, 1, 0.05))
        for i in range(1, 4):
            y = vol_top + vol_h + dp(6) + price_h * i / 4
            self._group.add(Line(points=[self.x + pad_l, y, self.right - pad_r, y],
                                 width=dp(0.6)))

        for idx, row in enumerate(rows):
            rgb = theme.UP if row.pct >= 0 else theme.DOWN
            self._group.add(Color(rgb[0], rgb[1], rgb[2], 0.55))
            height = max(dp(1), row.volume / max_vol * vol_h)
            self._group.add(Rectangle(pos=(px(idx) - bar_w / 2, vol_top),
                                      size=(bar_w, height)))

        accent = theme.ACCENT
        self._group.add(Color(accent[0], accent[1], accent[2], 0.95))
        if n > 1:
            points = []
            for idx, row in enumerate(rows):
                points.extend([px(idx), py(row.close)])
            self._group.add(Line(points=points, width=dp(1.4), joint="round"))
        self._group.add(Color(accent[0], accent[1], accent[2], 1))
        self._group.add(Rectangle(pos=(px(n - 1) - dp(2.5), py(rows[-1].close) - dp(2.5)),
                                  size=(dp(5), dp(5))))

        self._add_label(f"{hi:.2f}", self.x + pad_l + dp(2), self.y + self.height - dp(12))
        self._add_label(f"{lo:.2f}", self.x + pad_l + dp(2), vol_top + vol_h + dp(7))
        self._add_label(rows[0].date[5:], self.x + pad_l, self.y + dp(2), align="left")
        self._add_label(rows[-1].date[5:], self.right - pad_r - dp(34), self.y + dp(2))

    def _add_label(self, text, x, y, align="left"):
        label = Txt(text, size=9, color=theme.MUTED, size_hint=(None, None), align=align)
        label.texture_update()
        label.size = label.texture_size
        label.pos = (x, y)
        self.add_widget(label)
        self._labels.append(label)

    def _clear(self):
        self._group.clear()
        for label in self._labels:
            try:
                self.remove_widget(label)
            except Exception:
                pass
        self._labels = []


# --------------------------------------------------------------------------- #
# 其他
# --------------------------------------------------------------------------- #
class Spinner(Label):
    """极简加载提示（文字动画）。"""

    def __init__(self, text: str = "加载中", **kwargs):
        super().__init__(
            text=text,
            font_name=_font(),
            font_size=sp(12),
            color=theme.MUTED,
            **kwargs,
        )
        self._dots = 0
        self._event = None

    def start(self):
        if self._event:
            return
        self._event = Clock.schedule_interval(self._tick, 0.4)

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None

    def _tick(self, *_):
        self._dots = (self._dots + 1) % 4
        self.text = "加载中" + "." * self._dots


class StatBox(BoxLayout):
    """两行小指标：标题 + 数值。"""

    def __init__(self, title: str, value: str = "--", value_color=None,
                 size: float = 13, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(38))
        kwargs.setdefault("spacing", dp(1))
        super().__init__(**kwargs)
        self.title = Txt(title, size=10, color=theme.MUTED)
        self.value = Txt(value, size=size, color=value_color or theme.TEXT, bold=True)
        self.add_widget(self.title)
        self.add_widget(self.value)

    def update(self, value: str, color=None):
        self.value.text = value
        self.value.color = color or theme.TEXT
