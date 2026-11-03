# -*- coding: utf-8 -*-
"""生成应用图标与启动图（仅开发时运行一次，生成的 PNG 会提交到 assets/）。

用法：python tools/make_icon.py
依赖：Pillow
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

BG = (11, 15, 20, 255)
CARD = (21, 27, 36, 255)
GOLD = (242, 181, 68, 255)
UP = (255, 90, 95, 255)
DOWN = (34, 197, 139, 255)
MUTED = (139, 152, 168, 255)


def font(size: int):
    for path in (
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        str(ROOT / "assets" / "fonts" / "NotoSansSC-Regular.otf"),
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_icon(size: int = 512, padding: int = 0) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    left, right = int(size * 0.16), int(size * 0.84)
    top, bottom = int(size * 0.22), int(size * 0.66)
    # 网格
    for i in range(1, 4):
        y = top + (bottom - top) * i / 4
        draw.line([left, y, right, y], fill=(255, 255, 255, 18), width=max(1, size // 256))

    # K 线
    candles = [
        (0.00, 0.62, 0.42, 0.30),
        (0.18, 0.55, 0.30, 0.18),
        (0.36, 0.42, 0.55, 0.34),
        (0.54, 0.30, 0.45, 0.14),
        (0.72, 0.22, 0.20, 0.06),
    ]
    body_w = int((right - left) / 5 * 0.42)
    for idx, (x, open_, close, low) in enumerate(candles):
        cx = left + (right - left) * (0.1 + x * 0.9)
        up = close < open_
        color = UP if up else DOWN
        y_open = top + (bottom - top) * open_
        y_close = top + (bottom - top) * close
        y_low = top + (bottom - top) * min(0.95, low)
        y_high = top + (bottom - top) * max(0.02, min(open_, close) - 0.12)
        draw.line([cx, y_high, cx, y_low], fill=color, width=max(2, size // 128))
        draw.rounded_rectangle(
            [cx - body_w / 2, min(y_open, y_close), cx + body_w / 2, max(y_open, y_close)],
            radius=max(2, size // 128),
            fill=color,
        )

    # 金色收盘价折线
    points = [
        (left, top + (bottom - top) * 0.72),
        (left + (right - left) * 0.22, top + (bottom - top) * 0.58),
        (left + (right - left) * 0.44, top + (bottom - top) * 0.62),
        (left + (right - left) * 0.66, top + (bottom - top) * 0.34),
        (right, top + (bottom - top) * 0.20),
    ]
    draw.line(points, fill=GOLD, width=max(3, size // 96), joint="curve")

    # 文字
    label_font = font(int(size * 0.17))
    text = "A股雷达"
    bbox = draw.textbbox((0, 0), text, font=label_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], size * 0.74 - th / 2 - bbox[1]),
        text,
        font=label_font,
        fill=(233, 238, 245, 255),
    )
    return img


def make_splash(width: int = 1080, height: int = 1920) -> Image.Image:
    img = Image.new("RGBA", (width, height), BG)
    icon = make_icon(int(width * 0.46))
    img.alpha_composite(icon, (int(width * 0.27), int(height * 0.32)))
    draw = ImageDraw.Draw(img)
    f = font(int(width * 0.05))
    text = "量价 · 资金 · 消息关联"
    bbox = draw.textbbox((0, 0), text, font=f)
    draw.text(((width - (bbox[2] - bbox[0])) / 2, height * 0.60), text, font=f, fill=MUTED)
    return img


if __name__ == "__main__":
    icon = make_icon(512)
    icon.save(ASSETS / "icon.png")
    print("saved", ASSETS / "icon.png")
    make_splash().convert("RGB").save(ASSETS / "presplash.png")
    print("saved", ASSETS / "presplash.png")
