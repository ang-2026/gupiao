# -*- coding: utf-8 -*-
"""首页（自选股列表）与个股详情页（概览 / 日线 / 汇总 / 消息）。"""
from __future__ import annotations

import threading
import webbrowser

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from .. import analyzer, eastmoney, format as fmt, service
from ..models import NewsHit, StockSnapshot
from . import theme
from .widgets import (
    AutoCard,
    Chip,
    Divider,
    FlatButton,
    PriceVolumeChart,
    Spinner,
    StatBox,
    TableRow,
    TabButton,
    TapAutoCard,
    TapCard,
    Txt,
    WrapLabel,
)

LEVEL_STYLE = {
    "高": (theme.ACCENT, [0.36, 0.28, 0.08, 0.85]),
    "中": (theme.BLUE, [0.12, 0.22, 0.36, 0.85]),
    "低": (theme.MUTED, [0.16, 0.2, 0.26, 0.85]),
}


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def VBox(spacing: float = 5, padding: float = 0) -> BoxLayout:
    box = BoxLayout(orientation="vertical", spacing=dp(spacing),
                    size_hint_y=None, padding=dp(padding))
    box.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
    return box


def HBox(spacing: float = 6, height: float = 20) -> BoxLayout:
    box = BoxLayout(orientation="horizontal", spacing=dp(spacing),
                    size_hint_y=None, height=dp(height))
    return box


def auto_grid(cols: int = 2, spacing: float = 8) -> GridLayout:
    grid = GridLayout(cols=cols, spacing=dp(spacing), size_hint_y=None)
    grid.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
    return grid


def pct_color(value: float):
    return theme.color_updown(value or 0.0)


def open_url(url: str) -> None:
    """在系统浏览器中打开链接（安卓走 Intent）。"""
    if not url:
        return
    try:
        from jnius import autoclass  # type: ignore

        intent_cls = autoclass("android.content.Intent")
        uri_cls = autoclass("android.net.Uri")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        intent = intent_cls(intent_cls.ACTION_VIEW, uri_cls.parse(url))
        activity.startActivity(intent)
        return
    except Exception:
        pass
    try:
        webbrowser.open(url)
    except Exception:
        pass


class Panel(ScrollView):
    """竖排滚动面板。"""

    def __init__(self, **kwargs):
        kwargs.setdefault("do_scroll_x", False)
        kwargs.setdefault("bar_width", dp(2))
        kwargs.setdefault("bar_color", theme.LINE)
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(8), padding=(dp(12), dp(10)))
        self.box.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
        self.add_widget(self.box)

    def clear(self) -> None:
        self.box.clear_widgets()

    def add(self, widget) -> None:
        self.box.add_widget(widget)


# --------------------------------------------------------------------------- #
# 自选股卡片 / 首页
# --------------------------------------------------------------------------- #
class StockCard(TapCard):
    def __init__(self, item: dict, on_open, on_remove, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(62))
        kwargs.setdefault("padding", (dp(12), dp(7)))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.item = item

        left = BoxLayout(orientation="vertical", spacing=0, size_hint_x=1)
        left.add_widget(Txt(item.get("name") or item["code"], size=15, bold=True))
        left.add_widget(Txt(item["code"], size=9.5, color=theme.MUTED))
        self.add_widget(left)

        self.price_lbl = Txt("--", size=15, bold=True, align="right",
                             size_hint_x=None, width=dp(80))
        self.pct_lbl = Txt("", size=10.5, align="right", color=theme.MUTED,
                           size_hint_x=None, width=dp(64))
        self.add_widget(self.price_lbl)
        self.add_widget(self.pct_lbl)

        remove = FlatButton("×", font_size=15, size=(dp(26), dp(26)),
                            bg=[0, 0, 0, 0], color=theme.MUTED)
        remove.bind(on_release=lambda *_: on_remove(item["code"]))
        self.add_widget(remove)
        self.bind(on_release=lambda *_: on_open(item))

    def set_quote(self, price: float, pct: float) -> None:
        color = pct_color(pct)
        self.price_lbl.text = f"{price:.2f}"
        self.price_lbl.color = color
        self.pct_lbl.text = fmt.fmt_pct(pct)
        self.pct_lbl.color = color

    def on_press(self):
        self.bg = theme.SURFACE_2

    def on_release(self):
        self.bg = theme.SURFACE


class HomeScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(name="home", **kwargs)
        self.app = app
        self._cards: dict[str, StockCard] = {}
        self._token = 0

        root = BoxLayout(orientation="vertical", padding=(dp(14), dp(10)), spacing=dp(10))

        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(6))
        titles = BoxLayout(orientation="vertical", spacing=0)
        titles.add_widget(Txt("A股雷达", size=21, bold=True))
        titles.add_widget(Txt("成交量 · 资金流 · 股价 · 换手率 · 消息关联", size=9, color=theme.MUTED))
        head.add_widget(titles)
        refresh = FlatButton("刷新", font_size=10.5, size=(dp(52), dp(28)), bg=theme.SURFACE_2)
        refresh.bind(on_release=lambda *_: self.refresh_quotes(force=True))
        head.add_widget(refresh)
        root.add_widget(head)

        search_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                               height=dp(44), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="输入代码 / 名称 / 拼音，如 600519 或 茅台",
            multiline=False,
            font_name=theme.CJK_FONT if theme._FONT_READY else "Roboto",
            font_size=sp(13),
            background_normal="",
            background_active="",
            background_color=theme.SURFACE_2,
            foreground_color=theme.TEXT,
            hint_text_color=theme.MUTED,
            cursor_color=theme.ACCENT,
            padding=(dp(12), dp(11)),
            size_hint_x=1,
        )
        self.search_input.bind(on_text_validate=lambda *_: self.do_search())
        search_row.add_widget(self.search_input)
        go = FlatButton("搜索", font_size=13, size=(dp(62), dp(44)),
                        bg=theme.ACCENT, color=[0.05, 0.06, 0.08, 1])
        go.bind(on_release=lambda *_: self.do_search())
        search_row.add_widget(go)
        root.add_widget(search_row)

        self.panel = Panel()
        root.add_widget(self.panel)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self, *args):
        self.reload()

    def reload(self) -> None:
        self.panel.clear()
        self._cards = {}
        items = self.app.watchlist.load()
        if not items:
            self.panel.add(Txt("还没有自选股，在上方搜索后添加。", size=12, color=theme.MUTED))
            return
        self.panel.add(Txt("点击查看详情 · 右侧 × 移除", size=9, color=theme.MUTED,
                           size_hint_y=None, height=dp(16)))
        for item in items:
            card = StockCard(item, on_open=self.open_item, on_remove=self.remove_item)
            self._cards[item["code"]] = card
            self.panel.add(card)
        self.refresh_quotes()

    def refresh_quotes(self, force: bool = False) -> None:
        items = list(self.app.watchlist.load())
        if not items:
            return
        self._token += 1
        token = self._token

        def worker():
            result = {}
            for item in items:
                try:
                    meta = service.light_quote(eastmoney.secid_for(item["code"]), force=force)
                    if meta.get("price"):
                        result[item["code"]] = meta
                except Exception:
                    continue
            if not result:
                return

            def apply(*_):
                if token != self._token:
                    return
                for code, meta in result.items():
                    card = self._cards.get(code)
                    if card is not None:
                        card.set_quote(meta["price"], meta.get("pct") or 0.0)

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    def do_search(self) -> None:
        text = (self.search_input.text or "").strip()
        if not text:
            return
        self.app.toast("正在搜索…")

        def done(results):
            if results:
                if len(results) == 1:
                    self._pick(results[0])
                else:
                    self._show_results(results)
            elif text.isdigit() and len(text) == 6:
                self._pick({"code": text, "name": text, "secid": eastmoney.secid_for(text)})
            else:
                self.app.toast("未找到该股票，请换个关键词")

        def fail(err):
            self.app.toast(f"搜索失败：{err}")

        self.app.run_async(lambda: eastmoney.search_stocks(text), done, fail)

    def _show_results(self, results: list[dict]) -> None:
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        scroll = ScrollView(do_scroll_x=False)
        inner = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        inner.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
        popup = Popup(title="选择股票", title_color=theme.TEXT, title_size=sp(14),
                      content=content, size_hint=(0.9, None),
                      height=dp(96 + 46 * min(6, len(results))),
                      background="", background_color=theme.SURFACE,
                      separator_color=theme.LINE)
        for row in results[:8]:
            btn = FlatButton(f"{row['name']}   {row['code']}   {row.get('market', '')}",
                             font_size=12.5, size_hint_y=None, height=dp(40),
                             size_hint_x=1, bg=theme.SURFACE_2)
            btn.bind(on_release=lambda inst, r=row: (popup.dismiss(), self._pick(r)))
            inner.add_widget(btn)
        scroll.add_widget(inner)
        content.add_widget(scroll)
        popup.open()

    def _pick(self, row: dict) -> None:
        code = row.get("code") or ""
        name = row.get("name") or code
        self.app.watchlist.add(code, name, row.get("secid") or "")
        self.search_input.text = ""
        self.reload()
        self.app.open_stock(code, name, row.get("secid") or "")

    def open_item(self, item: dict) -> None:
        self.app.open_stock(item["code"], item.get("name") or item["code"],
                            item.get("secid") or "")

    def remove_item(self, code: str) -> None:
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        content.add_widget(Txt(f"从自选股中移除 {code} ？", size=13, align="center"))
        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None,
                        height=dp(38))
        cancel = FlatButton("取消", font_size=13, size_hint_x=1, height=dp(38),
                            size_hint_y=None, bg=theme.SURFACE_2)
        ok = FlatButton("移除", font_size=13, size_hint_x=1, height=dp(38),
                        size_hint_y=None, bg=[0.45, 0.16, 0.18, 1], color=theme.TEXT)
        popup = Popup(title="确认", title_color=theme.TEXT, title_size=sp(14),
                      content=content, size_hint=(0.8, None), height=dp(160),
                      background="", background_color=theme.SURFACE,
                      separator_color=theme.LINE)
        cancel.bind(on_release=lambda *_: popup.dismiss())

        def do_remove(*_):
            self.app.watchlist.remove(code)
            popup.dismiss()
            self.reload()

        ok.bind(on_release=do_remove)
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup.open()


# --------------------------------------------------------------------------- #
# 详情页
# --------------------------------------------------------------------------- #
class DetailScreen(Screen):
    TABS = (("overview", "概览"), ("daily", "日线"), ("summary", "汇总"), ("news", "消息"))
    COL_W = [1.25, 1.3, 1.3, 1.55, 1.2, 1.85]

    def __init__(self, app, **kwargs):
        super().__init__(name="detail", **kwargs)
        self.app = app
        self.snapshot: StockSnapshot | None = None
        self.window = 20
        self.daily_limit = 30
        self.news_limit = 15
        self.news_only_relevant = False
        self._token = 0
        self._analyses: dict[int, object] = {}
        self._spinner: Spinner | None = None

        root = BoxLayout(orientation="vertical")
        root.add_widget(self._build_header())
        root.add_widget(self._build_tabs())
        self.body = BoxLayout()
        root.add_widget(self.body)
        self.panels = {key: Panel() for key, _ in self.TABS}
        self.body.add_widget(self.panels["overview"])
        self.set_tab("overview")
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def _build_header(self):
        head = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(94),
                         padding=(dp(10), dp(4)), spacing=0)

        row1 = HBox(height=34, spacing=2)
        back = FlatButton("‹", font_size=24, size=(dp(30), dp(30)), bg=[0, 0, 0, 0])
        back.bind(on_release=lambda *_: self.app.go_home())
        row1.add_widget(back)
        self.name_lbl = Txt("--", size=17, bold=True)
        row1.add_widget(self.name_lbl)
        refresh = FlatButton("刷新", font_size=10.5, size=(dp(48), dp(26)), bg=theme.SURFACE_2)
        refresh.bind(on_release=lambda *_: self.reload())
        row1.add_widget(refresh)
        head.add_widget(row1)

        row2 = HBox(height=30, spacing=dp(6))
        self.meta_lbl = Txt("", size=9.5, color=theme.MUTED)
        row2.add_widget(self.meta_lbl)
        self.price_lbl = Txt("--", size=23, bold=True, align="right",
                             size_hint_x=None, width=dp(112))
        row2.add_widget(self.price_lbl)
        self.pct_lbl = Txt("", size=12, align="right", size_hint_x=None, width=dp(74))
        row2.add_widget(self.pct_lbl)
        head.add_widget(row2)

        self.status_lbl = Txt("", size=9, color=theme.MUTED, size_hint_y=None, height=dp(18))
        head.add_widget(self.status_lbl)
        return head

    def _build_tabs(self):
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38),
                        padding=(dp(6), 0), spacing=dp(2))
        self.tab_buttons: dict[str, TabButton] = {}
        for key, label in self.TABS:
            btn = TabButton(label, size_hint_x=1)
            btn.bind(on_release=lambda inst, k=key: self.set_tab(k))
            self.tab_buttons[key] = btn
            bar.add_widget(btn)
        return bar

    # ------------------------------------------------------------------ #
    def set_tab(self, key: str) -> None:
        self.body.clear_widgets()
        self.body.add_widget(self.panels[key])
        for name, btn in self.tab_buttons.items():
            btn.active = name == key
        self.current_tab = key

    def load(self, code: str, name: str = "", secid: str = "", force: bool = False) -> None:
        self._token += 1
        token = self._token
        self.snapshot = None
        self._analyses = {}
        self.window = 20
        self.daily_limit = 30
        self.news_limit = 15
        self.name_lbl.text = name or code
        self.meta_lbl.text = code
        self.price_lbl.text = "--"
        self.price_lbl.color = theme.TEXT
        self.pct_lbl.text = ""
        self.status_lbl.text = "正在获取行情 / 资金 / 新闻 / 公告…"
        for panel in self.panels.values():
            panel.clear()
        self._spinner = Spinner()
        self._spinner.start()
        self.panels["overview"].add(self._spinner)
        self.set_tab("overview")

        self.app.run_async(
            lambda: service.load_snapshot(code, name, force=force),
            lambda snap: self._on_loaded(token, snap),
            lambda err: self._on_error(token, err),
        )

    def reload(self) -> None:
        if self.snapshot is not None:
            self.load(self.snapshot.code, self.snapshot.name, force=True)

    def _on_loaded(self, token: int, snapshot: StockSnapshot) -> None:
        if token != self._token:
            return
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None
        self.snapshot = snapshot
        self._analyses = {}
        self._render_all()

    def _on_error(self, token: int, message: str) -> None:
        if token != self._token:
            return
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None
        text = str(message).replace("NetError: ", "").replace("请求失败: ", "")
        panel = self.panels["overview"]
        panel.clear()
        card = AutoCard(padding=dp(14), spacing=dp(8))
        card.add_widget(Txt("加载失败", size=15, bold=True, color=theme.UP,
                            size_hint_y=None, height=dp(22)))
        card.add_widget(WrapLabel(text, size=11.5, color=theme.TEXT))
        card.add_widget(WrapLabel("请检查网络后重试；离线时会尽量显示上次缓存的数据。",
                                  size=10, color=theme.MUTED))
        retry = FlatButton("重试", font_size=12.5, size_hint_y=None, height=dp(40),
                           size_hint_x=1, bg=theme.SURFACE_2)
        retry.bind(on_release=lambda *_: self.reload())
        card.add_widget(retry)
        panel.add(card)
        self.status_lbl.text = "加载失败 · 可点击重试"

    # ------------------------------------------------------------------ #
    def analysis_for(self, window: int):
        if window not in self._analyses:
            self._analyses[window] = analyzer.analyze(self.snapshot, window)
        return self._analyses[window]

    def _render_all(self) -> None:
        self._render_header()
        self._render_overview()
        self._render_daily()
        self._render_summary()
        self._render_news()

    def _render_header(self) -> None:
        snap = self.snapshot
        if snap is None:
            return
        self.name_lbl.text = snap.name
        industry = snap.industry or "—"
        cap = fmt.fmt_cap(snap.market_cap) if snap.market_cap else "—"
        self.meta_lbl.text = f"{snap.code} · {industry} · 市值 {cap}"
        self.price_lbl.text = f"{snap.price:.2f}"
        self.pct_lbl.text = fmt.fmt_pct(snap.pct)
        color = pct_color(snap.pct)
        self.price_lbl.color = color
        self.pct_lbl.color = color
        note = snap.notes[0] if snap.notes else ""
        self.status_lbl.text = (
            f"{note}　更新 {snap.updated}" if note else f"更新 {snap.updated} · 数据来源：东方财富"
        )

    # ---------------------------- 概览 ---------------------------- #
    def _render_overview(self) -> None:
        snap = self.snapshot
        if snap is None:
            return
        panel = self.panels["overview"]
        panel.clear()

        grid = auto_grid(2, 8)
        for summary in analyzer.summarize_all(snap.rows):
            card = TapAutoCard(padding=dp(10), spacing=dp(2))
            line1 = HBox(height=15, spacing=dp(4))
            line1.add_widget(Txt(summary.label, size=10, color=theme.MUTED,
                                 size_hint_x=None, width=dp(30)))
            line1.add_widget(Txt(summary.tag, size=9, color=theme.ACCENT))
            card.add_widget(line1)

            line2 = HBox(height=26, spacing=dp(4))
            line2.add_widget(Txt(fmt.fmt_pct(summary.pct), size=18, bold=True,
                                 color=pct_color(summary.pct)))
            line2.add_widget(Txt(fmt.fmt_money(summary.main_net, True), size=11,
                                 color=pct_color(summary.main_net), align="right"))
            card.add_widget(line2)

            line3 = Txt(f"成交 {fmt.fmt_money(summary.total_amount)} · 换手 "
                        f"{fmt.fmt_pct(summary.avg_turnover, False)}",
                        size=9, color=theme.MUTED, size_hint_y=None, height=dp(14))
            card.add_widget(line3)
            card.bind(on_release=lambda inst, w=summary.days: self._switch_window(w, jump=True))
            grid.add_widget(card)
        panel.add(grid)

        chart_card = AutoCard(padding=dp(10), spacing=dp(4))
        chart_card.add_widget(Txt("近 60 个交易日：收盘价 / 成交量", size=10,
                                  color=theme.MUTED, size_hint_y=None, height=dp(16)))
        chart_card.add_widget(PriceVolumeChart(rows=snap.rows[-60:], height=dp(150)))
        panel.add(chart_card)

        analysis = self.analysis_for(self.window)
        anom_card = AutoCard(padding=dp(11), spacing=dp(6))
        anom_card.add_widget(Txt(f"{self.window} 日内的异动", size=11.5, bold=True,
                                 size_hint_y=None, height=dp(18)))
        if analysis.anomalies:
            for anomaly in analysis.anomalies[:4]:
                block = VBox(2)
                head = HBox(height=18, spacing=dp(4))
                head.add_widget(Chip(anomaly.date[5:], size=9))
                head.add_widget(Txt(f"{anomaly.pct:+.2f}%", size=11.5,
                                    color=pct_color(anomaly.pct),
                                    size_hint_x=None, width=dp(58)))
                head.add_widget(Txt(f"量比 {anomaly.volume_ratio:.1f}", size=9,
                                    color=theme.MUTED))
                block.add_widget(head)
                block.add_widget(WrapLabel("；".join(anomaly.reasons), size=9.5,
                                           color=theme.MUTED))
                anom_card.add_widget(block)
        else:
            anom_card.add_widget(WrapLabel("区间内未检测到明显异动（涨跌幅 ≥3%、放量 ≥1.8 倍、"
                                           "换手率异常或主力资金大幅进出）。",
                                           size=9.5, color=theme.MUTED))
        panel.add(anom_card)

        link_card = AutoCard(padding=dp(11), spacing=dp(4))
        link_card.add_widget(Txt(f"{self.window} 日 消息关联小结", size=11.5, bold=True,
                                 size_hint_y=None, height=dp(18)))
        link_card.add_widget(WrapLabel(analysis.overview, size=11))
        link_card.add_widget(WrapLabel(
            "关联度由「事件类型 + 个股关键词 + 与异动日间隔 + 措辞方向」综合打分，"
            "用于快速定位线索，不代表因果关系。", size=9, color=theme.MUTED))
        panel.add(link_card)

        if snap.notes:
            note_card = AutoCard(padding=dp(11), spacing=dp(2))
            for note in snap.notes:
                note_card.add_widget(WrapLabel(f"· {note}", size=9, color=theme.MUTED))
            panel.add(note_card)

    # ---------------------------- 日线 ---------------------------- #
    def _render_daily(self) -> None:
        snap = self.snapshot
        if snap is None:
            return
        panel = self.panels["daily"]
        panel.clear()

        rows = list(reversed(snap.rows))[: self.daily_limit]
        card = AutoCard(padding=dp(8), spacing=0)
        header = TableRow(
            ["日期", "收盘", "涨跌", "成交量", "换手", "主力净流入"],
            self.COL_W,
            colors=[theme.MUTED] * 6, size=9, height=dp(24),
        )
        card.add_widget(header)
        card.add_widget(Divider())
        for row in rows:
            values = [
                row.date[5:],
                f"{row.close:.2f}",
                fmt.fmt_pct(row.pct),
                fmt.fmt_volume(row.volume),
                fmt.fmt_pct(row.turnover, False),
                fmt.fmt_money(row.main_net or 0.0, True),
            ]
            colors = [
                theme.TEXT, theme.TEXT, pct_color(row.pct),
                theme.TEXT, theme.TEXT, pct_color(row.main_net or 0.0),
            ]
            block = VBox(1)
            block.add_widget(TableRow(values, self.COL_W, colors=colors,
                                      size=9.5, height=dp(26)))
            block.add_widget(Txt(
                f"开 {row.open:.2f}   高 {row.high:.2f}   低 {row.low:.2f}"
                f"   振幅 {fmt.fmt_pct(row.amplitude, False)}",
                size=8.5, color=theme.MUTED, size_hint_y=None, height=dp(15),
            ))
            card.add_widget(block)
        panel.add(card)

        hint = Txt("上排：收盘 / 涨跌 / 成交量 / 换手率 / 主力净流入　下排：开盘 / 最高 / 最低 / 振幅",
                   size=8.5, color=theme.MUTED, size_hint_y=None, height=dp(16))
        panel.add(hint)

        if len(snap.rows) > len(rows):
            more = FlatButton(f"加载更多（已有 {len(rows)} / {len(snap.rows)} 天）",
                              font_size=11, size_hint_y=None, height=dp(36),
                              size_hint_x=1, bg=theme.SURFACE_2)
            more.bind(on_release=lambda *_: self._more_daily())
            panel.add(more)

    def _more_daily(self) -> None:
        self.daily_limit += 40
        self._render_daily()

    # ---------------------------- 汇总 ---------------------------- #
    def _render_summary(self) -> None:
        snap = self.snapshot
        if snap is None:
            return
        panel = self.panels["summary"]
        panel.clear()
        summaries = analyzer.summarize_all(snap.rows)

        table = AutoCard(padding=dp(9), spacing=dp(2))
        table.add_widget(Txt("5 / 10 / 20 / 60 日汇总对比", size=11.5, bold=True,
                             size_hint_y=None, height=dp(20)))
        table.add_widget(TableRow(
            ["周期", "涨跌", "成交额", "主力净流入", "均换手"],
            [0.8, 1.2, 1.35, 1.65, 1.1],
            colors=[theme.MUTED] * 5, size=9, height=dp(24),
        ))
        table.add_widget(Divider())
        for summary in summaries:
            table.add_widget(TableRow(
                [summary.label, fmt.fmt_pct(summary.pct), fmt.fmt_money(summary.total_amount),
                 fmt.fmt_money(summary.main_net, True),
                 fmt.fmt_pct(summary.avg_turnover, False)],
                [0.8, 1.2, 1.35, 1.65, 1.1],
                colors=[theme.TEXT, pct_color(summary.pct), theme.TEXT,
                        pct_color(summary.main_net), theme.TEXT],
                size=10, height=dp(28),
            ))
        panel.add(table)

        for summary in summaries:
            panel.add(self._summary_card(summary))

        panel.add(Txt("注：区间涨跌以区间前一交易日收盘价为基准；量能为日均成交量相对上一个"
                      "同长度区间；资金流数据来自东方财富。", size=8.5, color=theme.MUTED,
                      size_hint_y=None, height=dp(28)))

    def _summary_card(self, summary) -> AutoCard:
        card = AutoCard(padding=dp(11), spacing=dp(4))
        head = HBox(height=22, spacing=dp(6))
        head.add_widget(Txt(summary.label, size=14, bold=True, size_hint_x=None,
                            width=dp(44)))
        head.add_widget(Txt(f"{summary.start[5:]} ~ {summary.end[5:]}", size=9,
                            color=theme.MUTED))
        head.add_widget(Chip(summary.tag, size=8.5, color=theme.ACCENT,
                             bg=[0.34, 0.27, 0.08, 0.85]))
        card.add_widget(head)

        grid = GridLayout(cols=3, spacing=dp(2), size_hint_y=None)
        grid.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
        stats = [
            ("区间涨跌", fmt.fmt_pct(summary.pct), pct_color(summary.pct)),
            ("累计成交额", fmt.fmt_money(summary.total_amount), theme.TEXT),
            ("累计成交量", fmt.fmt_volume(summary.total_volume), theme.TEXT),
            ("主力净流入", fmt.fmt_money(summary.main_net, True), pct_color(summary.main_net)),
            ("净流入天数", f"{summary.inflow_days}/{summary.days}", theme.TEXT),
            ("均换手率", fmt.fmt_pct(summary.avg_turnover, False), theme.TEXT),
            ("量能较上期", f"{summary.volume_change:+.0f}%", theme.TEXT),
            ("最高 / 最低", f"{summary.high:.2f} / {summary.low:.2f}", theme.TEXT),
            ("振幅", fmt.fmt_pct(summary.amplitude, False), theme.TEXT),
        ]
        for title, value, color in stats:
            grid.add_widget(StatBox(title, value, color, size=11.5, height=dp(38)))
        card.add_widget(grid)

        card.add_widget(Txt(
            f"上涨 {summary.up_days} 天 · 下跌 {summary.down_days} 天 · "
            f"主力占成交额 {summary.main_net_ratio:+.1f}%",
            size=9, color=theme.MUTED, size_hint_y=None, height=dp(18),
        ))
        return card

    # ---------------------------- 消息 ---------------------------- #
    def _render_news(self) -> None:
        snap = self.snapshot
        if snap is None:
            return
        panel = self.panels["news"]
        panel.clear()
        analysis = self.analysis_for(self.window)

        intro = AutoCard(padding=dp(11), spacing=dp(4))
        intro.add_widget(Txt(f"{self.window} 日区间 · 新闻 / 公告关联", size=11.5, bold=True,
                             size_hint_y=None, height=dp(18)))
        intro.add_widget(WrapLabel(analysis.overview, size=11))
        intro.add_widget(WrapLabel(
            "评分 = 事件类型 + 个股关键词 + 与异动日间隔 + 措辞方向；仅作复盘线索。",
            size=9, color=theme.MUTED))
        panel.add(intro)

        window_row = HBox(height=30, spacing=dp(6))
        for days in (5, 10, 20, 60):
            active = days == self.window
            btn = FlatButton(
                f"{days}日", font_size=11, size_hint_x=1, size_hint_y=None, height=dp(28),
                bg=theme.ACCENT if active else theme.SURFACE_2,
                color=[0.05, 0.06, 0.08, 1] if active else theme.TEXT,
            )
            btn.bind(on_release=lambda inst, d=days: self._switch_window(d))
            window_row.add_widget(btn)
        panel.add(window_row)

        filter_row = HBox(height=26, spacing=dp(6))
        for label, value in (("全部", False), ("仅高/中相关", True)):
            active = value == self.news_only_relevant
            btn = FlatButton(
                label, font_size=10, size_hint_x=1, size_hint_y=None, height=dp(24),
                bg=theme.SURFACE_2 if not active else theme.LINE,
                color=theme.TEXT if active else theme.MUTED,
            )
            btn.bind(on_release=lambda inst, v=value: self._set_filter(v))
            filter_row.add_widget(btn)
        panel.add(filter_row)

        hits = analysis.hits
        if self.news_only_relevant:
            hits = [hit for hit in hits if hit.level in ("高", "中")]
        if not hits:
            panel.add(Txt("该区间没有匹配的新闻 / 公告。", size=11, color=theme.MUTED,
                          size_hint_y=None, height=dp(40)))
            return
        for hit in hits[: self.news_limit]:
            panel.add(self._news_card(hit))
        if len(hits) > self.news_limit:
            more = FlatButton(f"显示更多（还有 {len(hits) - self.news_limit} 条）",
                              font_size=11, size_hint_y=None, height=dp(36),
                              size_hint_x=1, bg=theme.SURFACE_2)
            more.bind(on_release=lambda *_: self._more_news())
            panel.add(more)

    def _news_card(self, hit: NewsHit) -> TapAutoCard:
        color, bg = LEVEL_STYLE.get(hit.level, LEVEL_STYLE["低"])
        card = TapAutoCard(padding=dp(10), spacing=dp(3))
        card.bind(on_release=lambda *_: open_url(hit.item.url))

        top = HBox(height=19, spacing=dp(3))
        top.add_widget(Chip(f"{hit.level}相关", size=8.5, color=color, bg=bg))
        top.add_widget(Chip(hit.item.kind_label, size=8.5))
        top.add_widget(Txt(hit.item.time[5:16], size=8.5, color=theme.MUTED))
        direct_color = {"利好": theme.UP, "利空": theme.DOWN}.get(hit.direction, theme.MUTED)
        top.add_widget(Txt(hit.direction, size=8.5, color=direct_color, align="right"))
        card.add_widget(top)

        card.add_widget(WrapLabel(hit.item.title, size=12, bold=True))
        if hit.item.summary:
            summary = hit.item.summary
            card.add_widget(WrapLabel(summary[:90] + ("…" if len(summary) > 90 else ""),
                                      size=9.5, color=theme.MUTED))
        card.add_widget(WrapLabel(" · ".join(hit.reasons[:3]), size=9, color=theme.BLUE))
        card.add_widget(Txt(f"{hit.item.source} · 关联度 {hit.score}",
                            size=8.5, color=theme.MUTED, size_hint_y=None, height=dp(14)))
        return card

    def _switch_window(self, days: int, jump: bool = False) -> None:
        self.window = days
        self.news_limit = 15
        if jump:
            self.set_tab("news")
            self._render_news()
            return
        self._render_news()
        if self.current_tab == "overview":
            self._render_overview()

    def _set_filter(self, only_relevant: bool) -> None:
        self.news_only_relevant = only_relevant
        self.news_limit = 15
        self._render_news()

    def _more_news(self) -> None:
        self.news_limit += 20
        self._render_news()
