# -*- coding: utf-8 -*-
"""解析与格式化的单元测试（不联网）。"""
from __future__ import annotations

import datetime as dt
import unittest

from stocklens import eastmoney, format as fmt


class ParseTest(unittest.TestCase):
    def test_secid(self):
        self.assertEqual(eastmoney.secid_for("600519"), "1.600519")
        self.assertEqual(eastmoney.secid_for("688981"), "1.688981")
        self.assertEqual(eastmoney.secid_for("000001"), "0.000001")
        self.assertEqual(eastmoney.secid_for("300750"), "0.300750")
        self.assertEqual(eastmoney.secid_for("830799"), "0.830799")
        self.assertEqual(eastmoney.secid_for("1.600519"), "1.600519")
        self.assertEqual(eastmoney.secid_for(""), "")

    def test_parse_daily(self):
        raw = {
            "data": {
                "code": "600519",
                "name": "贵州茅台",
                "klines": [
                    "2026-10-23,1311.84,1335.00,1343.88,1310.00,57686,7677216283.00,2.57,1.25,16.51,0.46",
                    "2026-10-22,1303.21,1318.49,1322.00,1296.00,42491,5576216948.00,1.99,0.67,8.80,0.34",
                ],
            }
        }
        rows, name, code = eastmoney.parse_daily(raw)
        self.assertEqual(name, "贵州茅台")
        self.assertEqual(code, "600519")
        self.assertEqual(len(rows), 2)
        # 按日期升序
        self.assertEqual(rows[0].date, "2026-10-22")
        self.assertAlmostEqual(rows[1].close, 1335.00)
        self.assertAlmostEqual(rows[1].volume, 57686.0)
        self.assertAlmostEqual(rows[1].amount, 7677216283.00)
        self.assertAlmostEqual(rows[1].turnover, 0.46)
        self.assertAlmostEqual(rows[1].pct, 1.25)

    def test_parse_flow(self):
        raw = {"data": {"klines": [
            "2026-10-23,283000000.0,-100.0,-200.0,1000.0,282999000.0,3.7,-0.0,-0.0,0.0,3.7,1335.0,1.25",
        ]}}
        flows = eastmoney.parse_flow(raw)
        self.assertIn("2026-10-23", flows)
        self.assertAlmostEqual(flows["2026-10-23"]["main"], 283000000.0)
        self.assertAlmostEqual(flows["2026-10-23"]["super"], 282999000.0)

    def test_parse_news_strips_tags_and_filters_old(self):
        today = dt.date.today()
        recent = today.strftime("%Y-%m-%d")
        old = (today - dt.timedelta(days=400)).strftime("%Y-%m-%d")
        raw = {"result": {"cmsArticleWebOld": [
            {"date": f"{recent} 09:30:00", "title": "<em>贵州茅台</em>发布公告",
             "content": "公司 &amp; 控股股东", "mediaName": "证券时报", "url": "http://a"},
            {"date": f"{old} 09:30:00", "title": "旧闻", "content": "", "mediaName": "x", "url": "http://b"},
        ]}}
        items = eastmoney.parse_news(raw, days=30)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "贵州茅台发布公告")
        self.assertEqual(items[0].summary, "公司 & 控股股东")
        self.assertEqual(items[0].kind, "news")

    def test_parse_notices(self):
        today = dt.date.today().strftime("%Y-%m-%d")
        raw = {"data": {"list": [{
            "art_code": "AN123",
            "notice_date": f"{today} 00:00:00",
            "title_ch": "贵州茅台:关于回购股份的公告",
            "columns": [{"column_name": "回购"}],
        }]}}
        items = eastmoney.parse_notices(raw, "600519", "贵州茅台", days=30)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "关于回购股份的公告")
        self.assertEqual(items[0].category, "回购")
        self.assertEqual(items[0].kind, "notice")
        self.assertIn("AN123", items[0].url)

    def test_parse_quote_scaling(self):
        raw = {"data": {"f43": 133421, "f58": "贵州茅台", "f60": 133500,
                        "f116": 1.67e12, "f117": 1.67e12, "f127": "白酒Ⅱ",
                        "f162": 1875, "f167": 665, "f170": 5}}
        meta = eastmoney.parse_quote(raw)
        self.assertAlmostEqual(meta["price"], 1334.21)
        self.assertAlmostEqual(meta["pe"], 18.75)
        self.assertAlmostEqual(meta["pb"], 6.65)
        self.assertEqual(meta["industry"], "白酒Ⅱ")


class FormatTest(unittest.TestCase):
    def test_money(self):
        self.assertEqual(fmt.fmt_money(3.56e8), "3.56亿")
        self.assertEqual(fmt.fmt_money(-1.2e8, signed=True), "-1.20亿")
        self.assertEqual(fmt.fmt_money(6.085e7, signed=True), "+6085.0万")
        self.assertEqual(fmt.fmt_money(0), "0元")

    def test_volume(self):
        self.assertEqual(fmt.fmt_volume(57686), "5.8万手")
        self.assertEqual(fmt.fmt_volume(900), "900手")

    def test_pct(self):
        self.assertEqual(fmt.fmt_pct(1.5), "+1.50%")
        self.assertEqual(fmt.fmt_pct(0.46, signed=False), "0.46%")

    def test_cap(self):
        self.assertEqual(fmt.fmt_cap(1.67e12), "1.67万亿")
        self.assertEqual(fmt.fmt_cap(2.3e11), "2300亿")


if __name__ == "__main__":
    unittest.main()
