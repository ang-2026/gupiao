# -*- coding: utf-8 -*-
"""数据模型（全部为普通 dataclass，方便序列化到 JSON / 界面展示）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DayRow:
    """单个交易日的行情 + 资金流（资金流缺失时为 None）。"""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float  # 成交量，单位：手
    amount: float  # 成交额，单位：元
    pct: float  # 涨跌幅，%
    change: float  # 涨跌额，元
    amplitude: float  # 振幅，%
    turnover: float  # 换手率，%
    main_net: float | None = None  # 主力净流入，元
    super_net: float | None = None  # 超大单净流入，元
    large_net: float | None = None  # 大单净流入，元
    medium_net: float | None = None  # 中单净流入，元
    small_net: float | None = None  # 小单净流入，元
    main_ratio: float | None = None  # 主力净流入占比，%

    @property
    def has_flow(self) -> bool:
        return self.main_net is not None


@dataclass
class PeriodSummary:
    """N 日汇总。金额单位：元；比例单位：%。"""

    days: int
    requested: int
    start: str
    end: str
    pct: float  # 区间涨跌幅
    total_volume: float  # 累计成交量（手）
    total_amount: float  # 累计成交额（元）
    main_net: float  # 主力净流入合计（元）
    super_net: float
    large_net: float
    main_net_ratio: float  # 主力净流入 / 成交额，%
    avg_turnover: float
    avg_volume: float
    high: float
    low: float
    amplitude: float  # (最高-最低)/最低，%
    up_days: int
    down_days: int
    flat_days: int
    inflow_days: int
    volume_change: float  # 日均成交量相对上一个同长度区间变化，%
    turnover_change: float  # 日均换手率相对上一个同长度区间变化，%
    tag: str  # 如“放量上涨”
    has_flow: bool

    @property
    def label(self) -> str:
        return f"{self.days}日"


@dataclass
class Anomaly:
    """一个放量 / 大涨大跌 / 资金异动的交易日。"""

    date: str
    pct: float
    volume_ratio: float
    turnover: float
    main_net: float | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class NewsItem:
    """新闻或公告。"""

    date: str  # YYYY-MM-DD
    time: str  # YYYY-MM-DD HH:MM
    title: str
    summary: str
    source: str
    url: str
    kind: str  # 'news' | 'notice'
    category: str = ""

    @property
    def kind_label(self) -> str:
        return "公告" if self.kind == "notice" else "新闻"


@dataclass
class NewsHit:
    """新闻/公告与股价波动的关联评分结果。"""

    item: NewsItem
    score: int  # 0-100
    level: str  # 高 / 中 / 低
    direction: str  # 利好 / 利空 / 中性
    reasons: list[str] = field(default_factory=list)
    anomaly: Anomaly | None = None


@dataclass
class StockSnapshot:
    """一只股票的完整数据快照。"""

    code: str
    name: str
    secid: str
    industry: str = ""
    price: float = 0.0
    prev_close: float = 0.0
    pct: float = 0.0
    market_cap: float = 0.0  # 总市值，元
    float_cap: float = 0.0  # 流通市值，元
    pe: float = 0.0
    pb: float = 0.0
    rows: list[DayRow] = field(default_factory=list)
    news: list[NewsItem] = field(default_factory=list)
    notices: list[NewsItem] = field(default_factory=list)
    updated: str = ""
    notes: list[str] = field(default_factory=list)  # 数据源提示（离线、缺字段等）
    stale: bool = False

    @property
    def all_media(self) -> list[NewsItem]:
        items = list(self.news) + list(self.notices)
        items.sort(key=lambda x: x.time, reverse=True)
        return items


@dataclass
class WindowAnalysis:
    """某只股票在某个汇总周期下的分析结果。"""

    window: int
    summary: PeriodSummary | None
    anomalies: list[Anomaly]
    hits: list[NewsHit]
    overview: str
    high_count: int
    mid_count: int
    matched_media: int
    media_total: int
    start: str
    end: str
