# -*- coding: utf-8 -*-
"""汇总统计、异动识别与「消息—股价」关联评分。

说明：关联判断是**启发式**的——用事件类型权重、个股关键词命中、消息方向词、
以及与异动交易日的间隔综合打分，用来给人工复盘提供线索，不是因果结论。
"""
from __future__ import annotations

import bisect
from statistics import mean

from . import config
from .models import (
    Anomaly,
    DayRow,
    NewsHit,
    NewsItem,
    PeriodSummary,
    StockSnapshot,
    WindowAnalysis,
)

# --------------------------------------------------------------------------- #
# 关键词
# --------------------------------------------------------------------------- #
POSITIVE_WORDS = (
    "增长", "预增", "扭亏", "盈利", "中标", "签约", "订单", "回购", "增持", "分红",
    "派息", "提价", "涨价", "突破", "新高", "利好", "翻倍", "超预期", "获批",
    "投产", "扩产", "合作", "战略", "创新高", "上调", "中标", "净利增",
)
NEGATIVE_WORDS = (
    "下降", "预亏", "亏损", "减持", "处罚", "立案", "问询", "关注函", "退市",
    "诉讼", "仲裁", "违约", "质押", "下滑", "不及预期", "停产", "召回",
    "风险提示", "警示", "下调", "监管", "调查", "冻结",
)

# (关键词集合, 权重, 归类)
EVENT_RULES: tuple[tuple[tuple[str, ...], int, str], ...] = (
    (("重组", "并购", "收购", "资产注入", "借壳"), 18, "资本运作"),
    (("业绩预告", "业绩快报", "年报", "半年报", "季报", "预增", "预亏", "业绩"), 16, "业绩"),
    (("重大合同", "中标", "订单", "签约", "框架协议"), 16, "订单合同"),
    (("问询", "关注函", "立案", "处罚", "警示", "监管", "调查"), 15, "监管"),
    (("回购",), 14, "回购"),
    (("停牌", "复牌"), 14, "停复牌"),
    (("增持",), 13, "股东增减持"),
    (("减持",), 13, "股东增减持"),
    (("澄清", "传闻", "辟谣"), 12, "澄清"),
    (("诉讼", "仲裁", "冻结"), 11, "诉讼"),
    (("分红", "派息", "利润分配", "送转"), 10, "分红送转"),
    (("股权激励", "员工持股", "增发", "定增", "可转债"), 10, "融资激励"),
    (("投产", "扩产", "产能", "涨价", "提价"), 9, "经营"),
)

# 新闻时间与异动日的间隔（交易日） -> 时间分
_TIME_POINTS = {0: 28, 1: 22, 2: 12, 3: 6, 4: 3, 5: 3}


# --------------------------------------------------------------------------- #
# 数据合并
# --------------------------------------------------------------------------- #
def merge_flow(rows: list[DayRow], flows: dict[str, dict]) -> list[DayRow]:
    """把资金流数据合并进日线行（没有对应日期则保持 None）。"""
    for row in rows:
        flow = flows.get(row.date)
        if not flow:
            continue
        row.main_net = flow.get("main")
        row.super_net = flow.get("super")
        row.large_net = flow.get("large")
        row.medium_net = flow.get("medium")
        row.small_net = flow.get("small")
        row.main_ratio = flow.get("main_ratio")
    return rows


# --------------------------------------------------------------------------- #
# 区间汇总
# --------------------------------------------------------------------------- #
def _safe_pct(new: float, old: float) -> float:
    if not old:
        return 0.0
    return (new / old - 1.0) * 100.0


def summarize(rows: list[DayRow], n: int) -> PeriodSummary | None:
    """计算最近 n 个交易日的汇总。"""
    if not rows:
        return None
    n = max(1, int(n))
    window = rows[-n:]
    prev = rows[-2 * n:-n]
    days = len(window)
    total_volume = sum(r.volume for r in window)
    total_amount = sum(r.amount for r in window)
    flow_rows = [r for r in window if r.main_net is not None]
    has_flow = bool(flow_rows)
    main_net = sum(r.main_net or 0.0 for r in flow_rows)
    super_net = sum(r.super_net or 0.0 for r in flow_rows)
    large_net = sum(r.large_net or 0.0 for r in flow_rows)

    base_close = window[0].open if window[0].open else window[0].close
    if len(rows) > days:
        base_close = rows[-days - 1].close or base_close
    last_close = window[-1].close
    pct = _safe_pct(last_close, base_close)

    highs = [r.high for r in window if r.high > 0]
    lows = [r.low for r in window if r.low > 0]
    high = max(highs) if highs else 0.0
    low = min(lows) if lows else 0.0
    amplitude = _safe_pct(high, low) if low else 0.0

    up_days = sum(1 for r in window if r.pct > 0.05)
    down_days = sum(1 for r in window if r.pct < -0.05)
    flat_days = days - up_days - down_days
    inflow_days = sum(1 for r in flow_rows if (r.main_net or 0) > 0)

    avg_volume = total_volume / days
    avg_turnover = mean([r.turnover for r in window]) if window else 0.0

    prev_avg_volume = (sum(r.volume for r in prev) / len(prev)) if prev else 0.0
    prev_avg_turnover = mean([r.turnover for r in prev]) if prev else 0.0
    volume_change = _safe_pct(avg_volume, prev_avg_volume) if prev_avg_volume else 0.0
    turnover_change = _safe_pct(avg_turnover, prev_avg_turnover) if prev_avg_turnover else 0.0

    main_ratio = (main_net / total_amount * 100.0) if total_amount else 0.0

    if not prev_avg_volume:
        volume_tag = ""
    elif volume_change >= 20:
        volume_tag = "放量"
    elif volume_change <= -20:
        volume_tag = "缩量"
    else:
        volume_tag = "量能平稳"

    if pct >= 2:
        price_tag = "上涨"
    elif pct <= -2:
        price_tag = "下跌"
    else:
        price_tag = "震荡"

    return PeriodSummary(
        days=days,
        requested=n,
        start=window[0].date,
        end=window[-1].date,
        pct=pct,
        total_volume=total_volume,
        total_amount=total_amount,
        main_net=main_net,
        super_net=super_net,
        large_net=large_net,
        main_net_ratio=main_ratio,
        avg_turnover=avg_turnover,
        avg_volume=avg_volume,
        high=high,
        low=low,
        amplitude=amplitude,
        up_days=up_days,
        down_days=down_days,
        flat_days=flat_days,
        inflow_days=inflow_days,
        volume_change=volume_change,
        turnover_change=turnover_change,
        tag=f"{volume_tag}{price_tag}",
        has_flow=has_flow,
    )


def summarize_all(rows: list[DayRow], windows: tuple[int, ...] = config.WINDOWS) -> list[PeriodSummary]:
    out = []
    for n in windows:
        item = summarize(rows, n)
        if item is not None:
            out.append(item)
    return out


# --------------------------------------------------------------------------- #
# 异动识别
# --------------------------------------------------------------------------- #
def _avg(values: list[float]) -> float:
    values = [v for v in values if v is not None]
    return mean(values) if values else 0.0


def detect_anomalies(rows: list[DayRow], n: int, limit: int = 15) -> list[Anomaly]:
    """在最近 n 个交易日里找出放量、大涨大跌、换手异常、主力资金异动的日子。"""
    if not rows:
        return []
    n = max(1, int(n))
    start = max(0, len(rows) - n)
    found: list[tuple[float, Anomaly]] = []

    for i in range(start, len(rows)):
        row = rows[i]
        history5 = rows[max(0, i - 5):i]
        history10 = rows[max(0, i - 10):i]
        history20 = rows[max(0, i - 20):i]

        base_vol = _avg([r.volume for r in history5])
        vol_ratio = (row.volume / base_vol) if base_vol > 0 else 0.0
        base_turnover = _avg([r.turnover for r in history10])
        avg_abs_flow = _avg([abs(r.main_net or 0.0) for r in history20 if r.main_net is not None])

        reasons: list[str] = []
        severity = 0.0

        if abs(row.pct) >= 3.0:
            reasons.append(f"{'涨' if row.pct > 0 else '跌'}幅 {abs(row.pct):.2f}%")
            severity = max(severity, abs(row.pct) / 3.0)

        if vol_ratio >= 1.8:
            reasons.append(f"成交量为前5日均量的 {vol_ratio:.1f} 倍")
            severity = max(severity, vol_ratio / 1.8)

        if row.turnover >= 5.0 and base_turnover > 0 and row.turnover >= 2.0 * base_turnover:
            reasons.append(f"换手率 {row.turnover:.2f}%（前10日均值 {base_turnover:.2f}%）")
            severity = max(severity, row.turnover / (2.0 * base_turnover))

        if row.main_net is not None and row.amount > 0:
            magnitude = abs(row.main_net)
            ratio = magnitude / row.amount
            if (
                magnitude >= 1e7
                and ratio >= 0.08
                and magnitude >= 2.5 * max(avg_abs_flow, 1.0)
            ):
                word = "流入" if row.main_net > 0 else "流出"
                reasons.append(f"主力净{word} {magnitude / 1e8:.2f} 亿元（占成交额 {ratio * 100:.1f}%）")
                severity = max(severity, magnitude / max(avg_abs_flow, 1.0) / 2.5)

        if reasons:
            found.append(
                (
                    severity,
                    Anomaly(
                        date=row.date,
                        pct=row.pct,
                        volume_ratio=vol_ratio,
                        turnover=row.turnover,
                        main_net=row.main_net,
                        reasons=reasons,
                    ),
                )
            )

    found.sort(key=lambda pair: pair[0], reverse=True)
    top = [pair[1] for pair in found[:limit]]
    top.sort(key=lambda a: a.date)
    return top


# --------------------------------------------------------------------------- #
# 新闻 / 公告关联评分
# --------------------------------------------------------------------------- #
def _direction(item: NewsItem) -> tuple[str, int, int]:
    """从标题判断消息方向（正文常夹带其他公司，只看标题更稳）。"""
    text = item.title
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    if pos > neg:
        return "利好", pos, neg
    if neg > pos:
        return "利空", pos, neg
    return "中性", pos, neg


def _event(item: NewsItem) -> tuple[int, str]:
    """事件类型权重：公司公告按全权重，媒体新闻打折并标注“疑似”。"""
    text = f"{item.title} {item.category}" if item.kind == "notice" else item.title
    for keywords, weight, label in EVENT_RULES:
        if any(k in text for k in keywords):
            if item.kind == "notice":
                return weight, label
            return max(2, round(weight * 0.6)), label
    return (5, "公告") if item.kind == "notice" else (2, "资讯")


def _day_index(dates: list[str], day: str) -> int:
    """把任意日期映射到最近的一个交易日索引。"""
    if not dates:
        return -1
    idx = bisect.bisect_right(dates, day) - 1
    return max(0, min(idx, len(dates) - 1))


def score_media(rows: list[DayRow], items: list[NewsItem],
                anomalies: list[Anomaly], name: str = "") -> list[NewsHit]:
    """给区间内的每一条新闻/公告打分（0-100）。"""
    if not items:
        return []
    dates = [r.date for r in rows]
    anomaly_index = {a.date: _day_index(dates, a.date) for a in anomalies}
    anomaly_by_index = {anomaly_index[a.date]: a for a in anomalies}
    name = (name or "").strip()

    hits: list[NewsHit] = []
    for item in items:
        score = 0
        reasons: list[str] = []

        # 1) 个股关键词
        text = f"{item.title} {item.summary}"
        if name and name in item.title:
            score += 18
            reasons.append("标题直接含个股名称")
        elif name and name in text:
            score += 4
            reasons.append("正文提及个股")

        # 2) 事件类型
        weight, label = _event(item)
        score += weight
        if item.kind == "notice":
            reasons.append(f"公司公告（{item.category or label}）")
        elif weight >= 8:
            reasons.append(f"疑似事件：{label}")

        # 3) 与最近异动日的时间距离
        idx = _day_index(dates, item.date)
        nearest: tuple[int, Anomaly] | None = None
        if anomaly_by_index:
            for a_idx, anomaly in anomaly_by_index.items():
                dist = abs(a_idx - idx)
                if nearest is None or dist < nearest[0]:
                    nearest = (dist, anomaly)
        if nearest is not None:
            dist, anomaly = nearest
            score += _TIME_POINTS.get(dist, 0)
            if dist == 0:
                reasons.append(f"与 {anomaly.date} 的异动同日（{anomaly.pct:+.2f}%）")
            elif dist <= 2:
                reasons.append(f"距 {anomaly.date} 异动仅 {dist} 个交易日")
            elif dist <= 5:
                reasons.append(f"距 {anomaly.date} 异动 {dist} 个交易日")

        # 4) 措辞方向与走势是否一致
        direction, pos, neg = _direction(item)
        if nearest is not None and direction != "中性":
            anomaly = nearest[1]
            if (direction == "利好" and anomaly.pct > 0) or (direction == "利空" and anomaly.pct < 0):
                score += 8
                reasons.append("措辞方向与当日走势一致")
            elif abs(anomaly.pct) >= 3:
                reasons.append("措辞方向与当日走势相反，需结合其他因素判断")

        # 5) 摘要信息量
        if len(item.summary) >= 40:
            score += 3

        score = max(0, min(100, score))
        level = "高" if score >= 62 else ("中" if score >= 42 else "低")
        hits.append(
            NewsHit(
                item=item,
                score=score,
                level=level,
                direction=direction,
                reasons=reasons or ["与区间内波动无明显关联特征"],
                anomaly=nearest[1] if nearest else None,
            )
        )

    order = {"高": 0, "中": 1, "低": 2}
    hits.sort(key=lambda h: (order.get(h.level, 3), -h.score, h.item.time), reverse=False)
    return hits


# --------------------------------------------------------------------------- #
# 组合分析
# --------------------------------------------------------------------------- #
def analyze(snapshot: StockSnapshot, window: int) -> WindowAnalysis:
    """对某个汇总周期做完整分析：汇总 + 异动 + 区间消息 + 关联结论。"""
    rows = snapshot.rows
    summary = summarize(rows, window)
    if summary is None:
        return WindowAnalysis(
            window=window, summary=None, anomalies=[], hits=[], overview="暂无行情数据",
            high_count=0, mid_count=0, matched_media=0, media_total=0, start="", end="",
        )

    anomalies = detect_anomalies(rows, window)
    start, end = summary.start, summary.end
    media = [m for m in snapshot.all_media if start <= m.date <= end]
    hits = score_media(rows, media, anomalies, name=snapshot.name)

    high_count = sum(1 for h in hits if h.level == "高")
    mid_count = sum(1 for h in hits if h.level == "中")

    if anomalies:
        dates = "、".join(a.date[5:] for a in anomalies[:4])
        more = f" 等 {len(anomalies)} 天" if len(anomalies) > 4 else ""
        overview = (
            f"{window} 个交易日（{start[5:]} ~ {end[5:]}）内有异动：{dates}{more}。"
            f"区间共 {len(media)} 条新闻/公告，其中高相关 {high_count} 条、中相关 {mid_count} 条。"
        )
    else:
        overview = (
            f"{window} 个交易日（{start[5:]} ~ {end[5:]}）走势相对平稳，"
            f"区间涨跌 {summary.pct:+.2f}%，未出现明显放量或异动。"
            f"区间共 {len(media)} 条新闻/公告。"
        )

    return WindowAnalysis(
        window=window,
        summary=summary,
        anomalies=anomalies,
        hits=hits,
        overview=overview,
        high_count=high_count,
        mid_count=mid_count,
        matched_media=len(media),
        media_total=len(snapshot.all_media),
        start=start,
        end=end,
    )
