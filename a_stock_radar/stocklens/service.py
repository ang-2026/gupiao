# -*- coding: utf-8 -*-
"""数据装配：并行拉取行情 / 资金 / 快照 / 公告 / 新闻，产出 StockSnapshot。"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

from . import config, eastmoney, net
from .analyzer import merge_flow
from .models import NewsItem, StockSnapshot


class DataError(Exception):
    """无法获得必要的行情数据。"""


def _cached(key: str, ttl: float, producer, use_cache: bool, status: dict,
            force: bool = False):
    if not use_cache:
        status[key] = "net"
        return producer()
    data, source = net.cached(key, 0 if force else ttl, producer)
    status[key] = source
    return data


def light_quote(secid: str, force: bool = False) -> dict:
    """轻量行情（自选股列表用），只请求一个接口。"""
    raw, _ = net.cached(
        f"quote_{secid}",
        0 if force else config.TTL_QUOTE,
        lambda: eastmoney.request_quote(secid),
    )
    return eastmoney.parse_quote(raw)


def load_snapshot(code: str, name: str = "", limit: int = config.HISTORY_LIMIT,
                  news_days: int = config.NEWS_LOOKBACK_DAYS,
                  use_cache: bool = True, force: bool = False) -> StockSnapshot:
    """拉取一只股票的全部数据；网络失败时自动回退本地缓存。"""
    code = (code or "").strip()
    if not code:
        raise DataError("股票代码不能为空")
    secid = eastmoney.secid_for(code)
    status: dict[str, str] = {}
    notes: list[str] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_daily = pool.submit(
            _cached, f"kline_{secid}_{limit}", config.TTL_KLINE,
            lambda: eastmoney.request_daily(secid, limit), use_cache, status, force,
        )
        f_flow = pool.submit(
            _cached, f"flow_{secid}", config.TTL_FLOW,
            lambda: eastmoney.request_flow(secid), use_cache, status, force,
        )
        f_quote = pool.submit(
            _cached, f"quote_{secid}", config.TTL_QUOTE,
            lambda: eastmoney.request_quote(secid), use_cache, status, force,
        )
        f_notice = pool.submit(
            _cached, f"notice_{code}", config.TTL_NOTICE,
            lambda: eastmoney.request_notices(code), use_cache, status, force,
        )

        try:
            daily_raw = f_daily.result()
        except Exception as exc:  # noqa: BLE001
            raise DataError(f"行情获取失败：{exc}") from exc

        try:
            flow_raw = f_flow.result()
        except Exception:
            flow_raw = None
            notes.append("资金流向数据暂不可用，主力净流入相关指标为空。")

        try:
            quote_raw = f_quote.result()
        except Exception:
            quote_raw = None

        try:
            notice_raw = f_notice.result()
        except Exception:
            notice_raw = None

    rows, api_name, api_code = eastmoney.parse_daily(daily_raw)
    if not rows:
        raise DataError("行情数据为空，请稍后重试")

    name = name or api_name or code
    code = api_code or code

    flows = eastmoney.parse_flow(flow_raw) if flow_raw else {}
    merge_flow(rows, flows)

    meta = eastmoney.parse_quote(quote_raw) if quote_raw else {}
    if not meta.get("industry"):
        meta["industry"] = ""

    notices: list[NewsItem] = []
    if notice_raw:
        notices = eastmoney.parse_notices(notice_raw, code, name, days=news_days)
    else:
        notes.append("公告接口暂不可用，未加载公告。")

    news: list[NewsItem] = []
    if name and name != code:
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(
                        _cached, f"news_{name}_{page}", config.TTL_NEWS,
                        (lambda p=page: eastmoney.request_news(name, page)),
                        use_cache, status, force,
                    )
                    for page in (1, 2, 3)
                ]
                seen: set[str] = set()
                seen_title: set[str] = set()
                for page, future in enumerate(futures, start=1):
                    try:
                        raw = future.result()
                    except Exception:
                        continue
                    for item in eastmoney.parse_news(raw, news_days):
                        if item.url and item.url in seen:
                            continue
                        # 同一事件常被多家转载：标题前 14 个字相同视为重复
                        key = "".join(ch for ch in item.title if ch.isalnum())[:14]
                        if key and key in seen_title:
                            continue
                        seen.add(item.url)
                        if key:
                            seen_title.add(key)
                        news.append(item)
        except Exception:
            pass
    if not news and not notices:
        notes.append("近期未检索到相关新闻/公告。")

    # 资金流覆盖情况提示
    if flows and rows:
        covered = sum(1 for r in rows[-10:] if r.main_net is not None)
        if covered == 0:
            notes.append("最近 10 个交易日暂无资金流向明细（该股可能未纳入资金流统计）。")

    if any(src == "stale" for src in status.values()):
        notes.append("网络不稳定，部分数据来自本地缓存，可能不是最新。")

    news.sort(key=lambda x: x.time, reverse=True)
    notices.sort(key=lambda x: x.time, reverse=True)

    last = rows[-1]
    prev_close = rows[-2].close if len(rows) > 1 else last.close
    price = last.close
    pct = last.pct

    return StockSnapshot(
        code=code,
        name=name,
        secid=secid,
        industry=meta.get("industry") or "",
        price=price,
        prev_close=prev_close,
        pct=pct,
        market_cap=meta.get("market_cap") or 0.0,
        float_cap=meta.get("float_cap") or 0.0,
        pe=meta.get("pe") or 0.0,
        pb=meta.get("pb") or 0.0,
        rows=rows,
        news=news,
        notices=notices,
        updated=dt.datetime.now().strftime("%m-%d %H:%M"),
        notes=notes,
        stale=any(src == "stale" for src in status.values()),
    )
