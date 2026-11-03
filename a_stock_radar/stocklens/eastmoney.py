# -*- coding: utf-8 -*-
"""东方财富公开数据接口：请求（返回原始 JSON，可缓存）与解析分离。

接口说明（均为公开网页接口，无需 token）：
* 搜索：      searchapi.eastmoney.com/api/suggest/get
* 日线行情：  push2his.eastmoney.com/api/qt/stock/kline/get
* 资金流向：  push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
* 实时快照：  push2.eastmoney.com/api/qt/stock/get
* 公告：      np-anotice-stock.eastmoney.com/api/security/ann
* 新闻搜索：  search-api-web.eastmoney.com/search/jsonp
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.parse

from . import config, net
from .models import DayRow, NewsItem

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def secid_for(code: str) -> str:
    """根据 6 位代码推断东方财富 secid（1=沪市，0=深市/北交所）。"""
    code = (code or "").strip()
    if not code:
        return ""
    if "." in code:  # 已带市场前缀
        return code
    if code[0] in "69":  # 沪市 A/B 股、科创板
        return f"1.{code}"
    return f"0.{code}"


def _f(value, default: float | None = None) -> float | None:
    """安全转 float，处理 '-' / '' / None。"""
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if text in ("", "-", "--", "None"):
            return default
        return float(text)
    except Exception:
        return default


def _clean(text: str) -> str:
    text = _TAG_RE.sub("", text or "")
    text = html.unescape(text)
    return _SPACE_RE.sub(" ", text).strip()


def _q(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def _ts() -> str:
    """额外的毫秒时间戳，避开东方财富 CDN 对同一路径的旧缓存。"""
    return str(int(time.time() * 1000))


# --------------------------------------------------------------------------- #
# 搜索
# --------------------------------------------------------------------------- #
def search_stocks(keyword: str, count: int = 10) -> list[dict]:
    """按代码 / 名称 / 拼音搜索 A 股。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    table = {}
    for _ in range(2):
        url = (
            "https://searchapi.eastmoney.com/api/suggest/get?input="
            f"{_q(keyword)}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
            f"&count={count}&_={_ts()}"
        )
        try:
            data = net.get_json(url)
        except Exception:
            continue
        table = (data or {}).get("QuotationCodeTable") or {}
        if table.get("Data"):
            break

    result = []
    for row in table.get("Data") or []:
        if (row.get("Classify") or "") != "AStock":
            continue
        code = row.get("Code") or ""
        quote_id = row.get("QuoteID") or secid_for(code)
        result.append(
            {
                "code": code,
                "name": row.get("Name") or code,
                "secid": quote_id,
                "market": row.get("SecurityTypeName") or "",
            }
        )
    return result


# --------------------------------------------------------------------------- #
# 日线行情
# --------------------------------------------------------------------------- #
def request_daily(secid: str, limit: int = config.HISTORY_LIMIT) -> dict:
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",  # 日线
        "fqt": "1",  # 前复权
        "end": "20500101",
        "lmt": str(limit),
        "_": _ts(),
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    data = net.get_json(url)
    if not ((data or {}).get("data") or {}).get("klines"):
        raise net.NetError("未获取到日线数据，请检查股票代码是否正确")
    return data


def parse_daily(raw: dict) -> tuple[list[DayRow], str, str]:
    """解析日线，返回 (行情列表, 股票名称, 代码)。"""
    payload = (raw or {}).get("data") or {}
    rows: list[DayRow] = []
    for line in payload.get("klines") or []:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        rows.append(
            DayRow(
                date=parts[0],
                open=_f(parts[1], 0.0) or 0.0,
                close=_f(parts[2], 0.0) or 0.0,
                high=_f(parts[3], 0.0) or 0.0,
                low=_f(parts[4], 0.0) or 0.0,
                volume=_f(parts[5], 0.0) or 0.0,
                amount=_f(parts[6], 0.0) or 0.0,
                amplitude=_f(parts[7], 0.0) or 0.0,
                pct=_f(parts[8], 0.0) or 0.0,
                change=_f(parts[9], 0.0) or 0.0,
                turnover=_f(parts[10], 0.0) or 0.0,
            )
        )
    rows.sort(key=lambda r: r.date)
    return rows, payload.get("name") or "", str(payload.get("code") or "")


# --------------------------------------------------------------------------- #
# 资金流向
# --------------------------------------------------------------------------- #
def request_flow(secid: str) -> dict:
    params = {
        "secid": secid,
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
        "klt": "101",
        "lmt": "0",
        "_": _ts(),
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?" + urllib.parse.urlencode(params)
    return net.get_json(url)


def parse_flow(raw: dict) -> dict[str, dict]:
    """每日资金流：主力 / 小单 / 中单 / 大单 / 超大单净流入（元）。"""
    klines = ((raw or {}).get("data") or {}).get("klines") or []
    out: dict[str, dict] = {}
    for line in klines:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        out[parts[0]] = {
            "main": _f(parts[1], 0.0) or 0.0,
            "small": _f(parts[2], 0.0) or 0.0,
            "medium": _f(parts[3], 0.0) or 0.0,
            "large": _f(parts[4], 0.0) or 0.0,
            "super": _f(parts[5], 0.0) or 0.0,
            "main_ratio": _f(parts[6], 0.0) or 0.0,
        }
    return out


# --------------------------------------------------------------------------- #
# 实时快照
# --------------------------------------------------------------------------- #
def request_quote(secid: str) -> dict:
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields": "f43,f57,f58,f60,f116,f117,f127,f162,f167,f170",
        "invt": "2",
        "fltt": "1",
        "_": _ts(),
    }
    url = "https://push2.eastmoney.com/api/qt/stock/get?" + urllib.parse.urlencode(params)
    return net.get_json(url)


def parse_quote(raw: dict) -> dict:
    data = (raw or {}).get("data") or {}

    def scaled(value, factor: float = 1.0) -> float:
        num = _f(value, None)
        return (num or 0.0) / factor

    return {
        "name": data.get("f58") or "",
        "price": scaled(data.get("f43"), 100.0),
        "prev_close": scaled(data.get("f60"), 100.0),
        "pct": scaled(data.get("f170"), 100.0),
        "market_cap": _f(data.get("f116"), 0.0) or 0.0,
        "float_cap": _f(data.get("f117"), 0.0) or 0.0,
        "industry": data.get("f127") or "",
        "pe": scaled(data.get("f162"), 100.0),
        "pb": scaled(data.get("f167"), 100.0),
    }


# --------------------------------------------------------------------------- #
# 新闻
# --------------------------------------------------------------------------- #
def request_news(name: str, page: int = 1, size: int = 50) -> dict:
    param = {
        "uid": "",
        "keyword": name,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "time",
                "pageIndex": page,
                "pageSize": size,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    encoded = _q(json.dumps(param, ensure_ascii=False))
    last_error = ""
    for _ in range(2):
        url = (
            "https://search-api-web.eastmoney.com/search/jsonp?cb=cb&_="
            + _ts()
            + "&param="
            + encoded
        )
        try:
            data = net.get_json(url, jsonp=True)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        result = (data or {}).get("result") or {}
        if "cmsArticleWebOld" in result:
            return data
        last_error = "接口返回了非新闻内容"
    raise net.NetError(f"新闻检索失败：{last_error}")


def parse_news(raw: dict, days: int = config.NEWS_LOOKBACK_DAYS) -> list[NewsItem]:
    rows = (((raw or {}).get("result") or {}).get("cmsArticleWebOld")) or []
    cutoff = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    items: list[NewsItem] = []
    for row in rows:
        date_text = (row.get("date") or "").strip()
        if len(date_text) < 10:
            continue
        day = date_text[:10]
        if day < cutoff:
            continue
        items.append(
            NewsItem(
                date=day,
                time=date_text[:16],
                title=_clean(row.get("title") or ""),
                summary=_clean(row.get("content") or ""),
                source=_clean(row.get("mediaName") or "东方财富"),
                url=row.get("url") or "",
                kind="news",
            )
        )
    return items


# --------------------------------------------------------------------------- #
# 公告
# --------------------------------------------------------------------------- #
def request_notices(code: str, size: int = 100) -> dict:
    params = {
        "sr": "-1",
        "page_size": str(size),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": code,
        "_": _ts(),
    }
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann?" + urllib.parse.urlencode(params)
    return net.get_json(url)


def parse_notices(raw: dict, code: str, name: str = "",
                  days: int = config.NEWS_LOOKBACK_DAYS) -> list[NewsItem]:
    rows = ((raw or {}).get("data") or {}).get("list") or []
    cutoff = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    prefix = f"{name}:" if name else ""
    items: list[NewsItem] = []
    for row in rows:
        notice_date = (row.get("notice_date") or "").strip()
        if len(notice_date) < 10:
            continue
        day = notice_date[:10]
        if day < cutoff:
            continue
        title = _clean(row.get("title_ch") or row.get("title") or "")
        if prefix and title.startswith(prefix):
            title = title[len(prefix):].strip()
        columns = row.get("columns") or []
        category = _clean(columns[0].get("column_name") or "") if columns else ""
        art_code = row.get("art_code") or ""
        items.append(
            NewsItem(
                date=day,
                time=f"{day} {notice_date[11:16]}" if len(notice_date) >= 16 else day,
                title=title,
                summary="",
                source="公司公告",
                url=(
                    f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html"
                    if art_code
                    else ""
                ),
                kind="notice",
                category=category,
            )
        )
    return items
