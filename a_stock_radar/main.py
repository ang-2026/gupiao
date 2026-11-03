# -*- coding: utf-8 -*-
"""A股雷达 —— 启动入口。

电脑上预览：  python main.py
安卓打包：    buildozer -v android debug   （入口同样是本文件）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stocklens.ui.app import run  # noqa: E402

if __name__ == "__main__":
    run()
