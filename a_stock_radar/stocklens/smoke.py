# -*- coding: utf-8 -*-
"""核心层联调脚本：真实接口 → 汇总 → 关联，打印结果。

用法：
    set STOCKLENS_HOME=...        （可选，指定缓存/自选目录）
    python -m stocklens.smoke 600519
"""
from __future__ import annotations

import sys

from . import analyzer, eastmoney, format as fmt, service


def main(argv: list[str]) -> int:
    code = argv[1] if len(argv) > 1 else "600519"
    print(f"== 搜索 {code} ==")
    found = eastmoney.search_stocks(code)
    print(found[:3])

    snap = service.load_snapshot(code, name=(found[0]["name"] if found else ""))
    print(f"\n== {snap.name} {snap.code} ==")
    print(f"最新 {snap.price:.2f}  {fmt.fmt_pct(snap.pct)}  行业 {snap.industry}  "
          f"总市值 {fmt.fmt_cap(snap.market_cap)}  PE {snap.pe:.1f}  PB {snap.pb:.2f}")
    print(f"日线 {len(snap.rows)} 条，{snap.rows[0].date} ~ {snap.rows[-1].date}")
    print(f"新闻 {len(snap.news)} 条，公告 {len(snap.notices)} 条，更新 {snap.updated}")
    for note in snap.notes:
        print("  !", note)

    print("\n== 最近 6 个交易日 ==")
    print(f"{'日期':<12}{'开盘':>8}{'收盘':>8}{'最高':>8}{'最低':>8}{'成交量':>10}"
          f"{'换手':>8}{'主力净流入':>12}")
    for row in snap.rows[-6:]:
        print(f"{row.date:<12}{row.open:>8.2f}{row.close:>8.2f}{row.high:>8.2f}{row.low:>8.2f}"
              f"{fmt.fmt_volume(row.volume):>10}{fmt.fmt_pct(row.turnover, False):>8}"
              f"{fmt.fmt_money(row.main_net or 0, True):>12}")

    print("\n== 5/10/20/60 日汇总 ==")
    for summary in analyzer.summarize_all(snap.rows):
        print(
            f"{summary.label:>4} | 区间 {summary.start}~{summary.end} | 涨跌 {summary.pct:+.2f}% "
            f"| 成交 {fmt.fmt_money(summary.total_amount)} / {fmt.fmt_volume(summary.total_volume)} "
            f"| 主力 {fmt.fmt_money(summary.main_net, True)}({summary.main_net_ratio:+.1f}%) "
            f"| 均换手 {summary.avg_turnover:.2f}% | 高 {summary.high:.2f} 低 {summary.low:.2f} "
            f"| 量比前期 {summary.volume_change:+.0f}% | {summary.tag}"
        )

    for window in (5, 20):
        analysis = analyzer.analyze(snap, window)
        print(f"\n== {window} 日关联分析 ==")
        print(analysis.overview)
        for anomaly in analysis.anomalies:
            print(f"  异动 {anomaly.date} {anomaly.pct:+.2f}%  量比{anomaly.volume_ratio:.1f}  "
                  f"{'；'.join(anomaly.reasons)}")
        for hit in analysis.hits[:6]:
            print(f"  [{hit.level}相关 {hit.score:>3}] {hit.item.time} {hit.item.kind_label} "
                  f"{hit.item.title[:40]}  <- {'；'.join(hit.reasons[:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
