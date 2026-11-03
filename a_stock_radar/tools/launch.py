# -*- coding: utf-8 -*-
"""桌面启动器：设置 Kivy 目录后运行 App（供 run.bat 调用）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("KIVY_HOME", str(ROOT / ".tools" / "kivyhome"))
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("PYTHONUTF8", "1")

print("=" * 46)
print("  A股雷达 StockLens")
print("  正在启动，请稍候（首次启动会慢一些）…")
print("  关闭窗口即可退出；数据需要联网获取。")
print("=" * 46)

import kivy  # noqa: E402

print(f"  Python {sys.version.split()[0]} / Kivy {kivy.__version__}")
print("=" * 46)

from stocklens.ui.app import run  # noqa: E402

run()
