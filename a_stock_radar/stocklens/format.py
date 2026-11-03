# -*- coding: utf-8 -*-
"""展示格式化：金额、成交量、百分比。"""
from __future__ import annotations


def fmt_money(yuan: float, signed: bool = False) -> str:
    """元 → 亿 / 万。"""
    try:
        value = float(yuan or 0.0)
    except Exception:
        return "--"
    sign = "-" if value < 0 else ("+" if signed else "")
    abs_value = abs(value)
    if abs_value >= 1e8:
        return f"{sign}{abs_value / 1e8:.2f}亿"
    if abs_value >= 1e4:
        return f"{sign}{abs_value / 1e4:.1f}万"
    return f"{sign}{abs_value:.0f}元"


def fmt_volume(shou: float) -> str:
    """手 → 万手。"""
    try:
        value = float(shou or 0.0)
    except Exception:
        return "--"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万手"
    return f"{value:.0f}手"


def fmt_pct(value: float, signed: bool = True) -> str:
    try:
        num = float(value or 0.0)
    except Exception:
        return "--"
    return f"{num:+.2f}%" if signed else f"{num:.2f}%"


def fmt_price(value: float) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "--"


def fmt_ratio(value: float) -> str:
    """倍数展示，如 1.9 倍。"""
    try:
        return f"{float(value):.1f}倍"
    except Exception:
        return "--"


def fmt_cap(yuan: float) -> str:
    try:
        value = float(yuan or 0.0)
    except Exception:
        return "--"
    if value >= 1e12:
        return f"{value / 1e12:.2f}万亿"
    if value >= 1e8:
        return f"{value / 1e8:.0f}亿"
    return f"{value / 1e4:.0f}万"
