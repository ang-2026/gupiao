# -*- coding: utf-8 -*-
"""Kivy 应用入口。"""
from __future__ import annotations

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.utils import platform as kivy_platform

from ..store import Watchlist
from . import theme
from .screens import DetailScreen, HomeScreen


class Toast(Label):
    """底部提示条。"""

    def __init__(self, **kwargs):
        super().__init__(
            text="",
            font_name=theme.CJK_FONT if theme._FONT_READY else "Roboto",
            font_size=sp(11.5),
            color=theme.TEXT,
            opacity=0,
            size_hint=(None, None),
            halign="center",
            valign="middle",
            **kwargs,
        )
        with self.canvas.before:
            self._bg_color = Color(rgba=[0.12, 0.15, 0.2, 0.96])
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._sync, size=self._sync)
        self._event = None

    def _sync(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def show(self, message: str) -> None:
        self.text = message
        self.texture_update()
        self.size = (min(Window.width - dp(32), self.texture_size[0] + dp(28)),
                     self.texture_size[1] + dp(14))
        self.pos = (Window.width / 2 - self.width / 2, dp(56))
        self.text_size = self.size
        self.opacity = 1
        if self._event:
            self._event.cancel()
        self._event = Clock.schedule_once(lambda *_: setattr(self, "opacity", 0), 1.8)


class StockLensApp(App):
    title = "A股雷达"

    def build(self):
        theme.apply_env()
        theme.register_fonts()
        Window.clearcolor = theme.BG
        # 桌面端固定成手机比例便于预览；手机上保持全屏自适应
        if kivy_platform not in ("android", "ios"):
            try:
                Window.size = (400, 780)
            except Exception:
                pass
        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass

        self.watchlist = Watchlist()
        self.sm = ScreenManager(transition=SlideTransition(duration=0.16))
        self.home = HomeScreen(self)
        self.detail = DetailScreen(self)
        self.sm.add_widget(self.home)
        self.sm.add_widget(self.detail)

        root = FloatLayout()
        root.add_widget(self.sm)
        self.toast_widget = Toast()
        root.add_widget(self.toast_widget)

        Window.bind(on_keyboard=self._on_key)
        return root

    # ------------------------------------------------------------------ #
    def run_async(self, fn, on_done, on_error=None) -> None:
        """后台线程执行 fn，结果回到主线程。"""

        def worker():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                if on_error is not None:
                    message = str(exc) or exc.__class__.__name__
                    Clock.schedule_once(lambda dt: on_error(message), 0)
                return
            Clock.schedule_once(lambda dt: on_done(result), 0)

        threading.Thread(target=worker, daemon=True).start()

    def toast(self, message: str) -> None:
        try:
            self.toast_widget.show(message)
        except Exception:
            pass

    def open_stock(self, code: str, name: str = "", secid: str = "",
                   force: bool = False) -> None:
        self.detail.load(code, name, secid, force=force)
        self.sm.current = "detail"

    def go_home(self) -> None:
        self.sm.current = "home"
        self.home.refresh_quotes()

    def _on_key(self, window, key, *args):
        if key == 27:  # 安卓返回键
            if self.sm.current == "detail":
                self.go_home()
                return True
        return False

    def on_pause(self):
        return True


def run() -> None:
    StockLensApp().run()


if __name__ == "__main__":
    run()
