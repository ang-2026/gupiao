# -*- coding: utf-8 -*-
"""全局常量与本地目录。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

APP_NAME = "A股雷达"
APP_VERSION = "1.0.0"
APP_ID = "org.stocklens.radar"

# 汇总周期（交易日）
WINDOWS = (5, 10, 20, 60)

# 拉取的日线根数：需覆盖 60 日汇总 + 上一个 60 日区间 + 图表
HISTORY_LIMIT = 320
# 新闻/公告回看天数（自然日），足够覆盖 60 个交易日
NEWS_LOOKBACK_DAYS = 120
NEWS_MAX_ITEMS = 160

# 接口
TIMEOUT = 12
RETRY = 2
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36"
)

# 缓存有效期（秒）
TTL_KLINE = 10 * 60
TTL_FLOW = 10 * 60
TTL_QUOTE = 5 * 60
TTL_NEWS = 20 * 60
TTL_NOTICE = 60 * 60

# 首次启动的示例自选股（可删除）
DEFAULT_WATCHLIST = [
    {"code": "600519", "name": "贵州茅台"},
    {"code": "000001", "name": "平安银行"},
    {"code": "300750", "name": "宁德时代"},
]

_DATA_DIR: Path | None = None


def _usable(path: Path) -> bool:
    """目录可创建且可写。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def data_dir() -> Path:
    """返回可写的本地数据目录：优先环境变量，其次 Kivy 应用目录，最后用户主目录/临时目录。"""
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR

    candidates: list[Path] = []
    env = os.environ.get("STOCKLENS_HOME")
    if env:
        candidates.append(Path(env).expanduser())

    try:  # Android / Kivy 下使用应用私有目录
        from kivy.app import App  # type: ignore

        app = App.get_running_app()
        if app is not None:
            candidates.append(Path(app.user_data_dir))
    except Exception:
        pass

    candidates.append(Path.home() / ".stocklens")
    candidates.append(Path(tempfile.gettempdir()) / "stocklens")
    candidates.append(Path.cwd() / "stocklens-data")

    for path in candidates:
        if _usable(path):
            _DATA_DIR = path
            return path

    # 全都不可写时也不要崩，返回一个路径即可（写入失败会被上层 try 忽略）
    _DATA_DIR = candidates[-1]
    return _DATA_DIR


def cache_dir() -> Path:
    path = data_dir() / "cache"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path
