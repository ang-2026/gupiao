# -*- coding: utf-8 -*-
"""汇总 / 异动 / 关联评分的单元测试（不联网）。"""
from __future__ import annotations

import unittest

from stocklens import analyzer
from stocklens.models import DayRow, NewsItem


def make_rows(n: int = 80) -> list[DayRow]:
    """构造一段可控的日线：1..n 日，收盘价从 10 元每天 +0.1，成交量恒定 1000 手。"""
    rows: list[DayRow] = []
    for i in range(n):
        day = f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        close = 10.0 + i * 0.1
        rows.append(
            DayRow(
                date=day,
                open=close - 0.05,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=1000.0,
                amount=1_000_000.0,
                pct=1.0,
                change=0.1,
                amplitude=4.0,
                turnover=2.0,
                main_net=1_000_000.0,
                super_net=600_000.0,
                large_net=400_000.0,
                medium_net=-500_000.0,
                small_net=-500_000.0,
                main_ratio=10.0,
            )
        )
    return rows


class SummarizeTest(unittest.TestCase):
    def test_basic_5day(self):
        rows = make_rows(80)
        summary = analyzer.summarize(rows, 5)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.days, 5)
        self.assertEqual(summary.start, rows[-5].date)
        self.assertEqual(summary.end, rows[-1].date)
        # 收盘价 10+0.1*i，第 80 天收盘 17.9；5 日区间基准为第 75 天收盘 17.4
        self.assertAlmostEqual(summary.pct, (17.9 / 17.4 - 1) * 100, places=4)
        self.assertAlmostEqual(summary.total_volume, 5000.0)
        self.assertAlmostEqual(summary.total_amount, 5_000_000.0)
        self.assertAlmostEqual(summary.main_net, 5_000_000.0)
        self.assertAlmostEqual(summary.avg_turnover, 2.0)
        self.assertAlmostEqual(summary.high, 18.1, places=2)
        self.assertAlmostEqual(summary.low, 17.3, places=2)
        self.assertEqual(summary.up_days, 5)
        self.assertEqual(summary.inflow_days, 5)
        self.assertTrue(summary.has_flow)

    def test_volume_change_vs_previous_window(self):
        rows = make_rows(80)
        for row in rows[-5:]:
            row.volume = 2000.0
        summary = analyzer.summarize(rows, 5)
        self.assertAlmostEqual(summary.volume_change, 100.0, places=4)
        self.assertIn("放量", summary.tag)

    def test_missing_flow(self):
        rows = make_rows(10)
        for row in rows:
            row.main_net = None
            row.super_net = None
            row.large_net = None
        summary = analyzer.summarize(rows, 5)
        self.assertFalse(summary.has_flow)
        self.assertEqual(summary.main_net, 0.0)

    def test_short_history(self):
        rows = make_rows(3)
        summary = analyzer.summarize(rows, 20)
        self.assertEqual(summary.days, 3)
        self.assertEqual(summary.requested, 20)

    def test_all_windows(self):
        rows = make_rows(200)
        summaries = analyzer.summarize_all(rows)
        self.assertEqual([s.days for s in summaries], [5, 10, 20, 60])


class AnomalyTest(unittest.TestCase):
    def test_detects_price_and_volume_spike(self):
        rows = make_rows(60)
        rows[-2].pct = 6.5
        rows[-2].volume = 4000.0
        rows[-2].turnover = 9.0
        found = analyzer.detect_anomalies(rows, 20)
        self.assertTrue(found)
        hit = [a for a in found if a.date == rows[-2].date]
        self.assertEqual(len(hit), 1)
        text = " ".join(hit[0].reasons)
        self.assertIn("6.50%", text)
        self.assertIn("倍", text)

    def test_quiet_window_has_no_anomaly(self):
        rows = make_rows(60)
        self.assertEqual(analyzer.detect_anomalies(rows, 20), [])


class ScoreTest(unittest.TestCase):
    def test_same_day_positive_headline_scores_high(self):
        rows = make_rows(60)
        rows[-1].pct = 5.0
        rows[-1].volume = 3000.0
        anomalies = analyzer.detect_anomalies(rows, 10)
        self.assertTrue(anomalies)
        item = NewsItem(
            date=rows[-1].date, time=f"{rows[-1].date} 09:30",
            title="测试股份发布业绩预告：净利润预增120%", summary="公司预计全年净利润大幅增长。",
            source="测试", url="http://x", kind="news",
        )
        hits = analyzer.score_media(rows, [item], anomalies, name="测试股份")
        self.assertEqual(len(hits), 1)
        self.assertGreaterEqual(hits[0].score, 60)
        self.assertEqual(hits[0].level, "高")
        self.assertEqual(hits[0].direction, "利好")

    def test_unrelated_old_item_scores_low(self):
        rows = make_rows(60)
        rows[-1].pct = 5.0
        anomalies = analyzer.detect_anomalies(rows, 5)
        item = NewsItem(
            date=rows[-40].date, time=f"{rows[-40].date} 10:00",
            title="某公司发布日常经营公告", summary="其他内容。",
            source="测试", url="http://y", kind="news",
        )
        hits = analyzer.score_media(rows, [item], anomalies, name="测试股份")
        self.assertLess(hits[0].score, 40)
        self.assertEqual(hits[0].level, "低")

    def test_analyze_filters_by_window(self):
        rows = make_rows(80)
        inside = NewsItem(date=rows[-1].date, time=f"{rows[-1].date} 10:00",
                          title="区间内新闻", summary="", source="s", url="u1", kind="news")
        outside = NewsItem(date=rows[-40].date, time=f"{rows[-40].date} 10:00",
                           title="区间外新闻", summary="", source="s", url="u2", kind="news")
        snapshot = type("Snap", (), {})()
        snapshot.rows = rows
        snapshot.news = [inside, outside]
        snapshot.notices = []
        snapshot.name = "测试股份"
        snapshot.all_media = inside_media = [inside, outside]
        analysis = analyzer.analyze(snapshot, 5)
        self.assertEqual(analysis.matched_media, 1)
        self.assertEqual(analysis.hits[0].item.url, "u1")
        self.assertIn("5 个交易日", analysis.overview)


if __name__ == "__main__":
    unittest.main()
