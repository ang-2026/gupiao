# -*- coding: utf-8 -*-
"""配色、字体与通用小工具。"""
from __future__ import annotations

import os
from pathlib import Path

from kivy.core.text import LabelBase
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex as hexc

# --------------------------------------------------------------------------- #
# 配色（深色，涨红跌绿）
# --------------------------------------------------------------------------- #
BG = hexc("#0B0F14")
SURFACE = hexc("#151B24")
SURFACE_2 = hexc("#1C2531")
LINE = hexc("#26303D")
TEXT = hexc("#E9EEF5")
MUTED = hexc("#8B98A8")
UP = hexc("#FF5A5F")
DOWN = hexc("#22C58B")
FLAT = hexc("#9AA7B6")
ACCENT = hexc("#F2B544")
BLUE = hexc("#5AA9FF")
PURPLE = hexc("#B388FF")

CJK_FONT = "CJK"
_FONT_READY = False


def _candidates() -> list[Path]:
    here = Path(__file__).resolve().parent.parent.parent  # 项目根目录
    paths = [
        here / "assets" / "fonts" / "NotoSansSC-Regular.otf",
        here / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf",
        here / "assets" / "fonts" / "NotoSansCJK-Regular.ttc",
        here / "assets" / "fonts" / "SourceHanSansSC-Regular.otf",
        Path("/system/fonts/NotoSansCJK-Regular.ttc"),
        Path("/system/fonts/NotoSansSC-Regular.otf"),
        Path("/system/fonts/DroidSansFallback.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyh.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ]
    return paths


def register_fonts() -> str | None:
    """注册中文字体；把系统的默认 Roboto 也指向它，避免到处写 font_name。"""
    global _FONT_READY
    if _FONT_READY:
        return CJK_FONT
    chosen = None
    for path in _candidates():
        try:
            if path.exists():
                chosen = str(path)
                break
        except OSError:
            continue
    if not chosen:
        return None
    try:
        LabelBase.register(name=CJK_FONT, fn_regular=chosen, fn_bold=chosen)
        # 覆盖默认字体，确保所有内置控件（含 Popup）都能显示中文
        LabelBase.register(name="Roboto", fn_regular=chosen, fn_bold=chosen)
    except Exception:
        return None
    _FONT_READY = True
    return CJK_FONT


def font_path() -> str | None:
    for path in _candidates():
        try:
            if path.exists():
                return str(path)
        except OSError:
            continue
    return None


def color_updown(value: float):
    if value > 0.001:
        return UP
    if value < -0.001:
        return DOWN
    return FLAT


def fmt_pct(value: float, signed: bool = True) -> str:
    from ..format import fmt_pct as _fmt

    return _fmt(value, signed)


def apply_env() -> None:
    """Kivy 配置：禁用多点触控模拟等。"""
    os.environ.setdefault("KIVY_NO_ARGS", "1")
    os.environ.setdefault("KIVY_LOG_MODE", "PYTHON")
    os.environ.setdefault("KIVY_NO_CONSOLELOG", "0")
