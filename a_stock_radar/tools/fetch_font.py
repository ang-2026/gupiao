# -*- coding: utf-8 -*-
"""准备中文字体到 assets/fonts/。

优先下载 Noto Sans CJK SC；下载失败时复制本机已装的中文字体（Linux 可先
`apt install fonts-noto-cjk`）。安卓包里必须有中文字体，否则界面是方块。

    python tools/fetch_font.py [--force]
"""
from __future__ import annotations

import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = ROOT / "assets" / "fonts"
# 这些文件名都会被 stocklens/ui/theme.py 识别
TARGETS = {
    "otf": TARGET_DIR / "NotoSansSC-Regular.otf",
    "ttc": TARGET_DIR / "NotoSansCJK-Regular.ttc",
}

URLS = [
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
]

SYSTEM_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
]

MAGIC = (b"OTTO", b"\x00\x01\x00\x00", b"true", b"ttcf")


def _is_font(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(4) in MAGIC
    except OSError:
        return False


def download(url: str, target: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r下载中 {done / 1048576:.1f} / {total / 1048576:.1f} MB", end="")
    print()
    if not _is_font(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("下载内容不是字体文件")
    os.replace(tmp, target)


def use_system_font() -> bool:
    for path in SYSTEM_FONTS:
        src = Path(path)
        if src.exists() and src.stat().st_size > 500_000 and _is_font(src):
            suffix = ".ttc" if src.suffix.lower() == ".ttc" else ".otf"
            target = TARGETS["ttc" if suffix == ".ttc" else "otf"]
            shutil.copyfile(src, target)
            print(f"已复制系统字体：{src} -> {target}")
            return True
    return False


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    existing = [p for p in TARGETS.values() if p.exists() and _is_font(p)]
    if existing and "--force" not in sys.argv:
        for path in existing:
            print(f"字体已存在：{path}（{path.stat().st_size / 1048576:.1f} MB）")
        return 0

    for url in URLS:
        try:
            print(f"尝试下载 {url}")
            download(url, TARGETS["otf"])
            print(f"完成：{TARGETS['otf']}（{TARGETS['otf'].stat().st_size / 1048576:.1f} MB）")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"  失败：{exc}")

    print("下载失败，尝试使用本机已安装的中文字体…")
    if use_system_font():
        return 0

    print("找不到可用字体。请手动下载 Noto Sans SC / 思源黑体，")
    print(f"另存为 {TARGETS['otf']} 或 {TARGETS['ttc']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
