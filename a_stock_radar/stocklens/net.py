# -*- coding: utf-8 -*-
"""HTTP 请求与磁盘缓存（仅标准库，便于打包到安卓）。

设计要点：
* 统一 UA / Referer，失败自动重试；
* JSONP 自动解包；
* 所有接口结果落盘缓存，断网时回退到上一次成功的数据（stale）。

注意：**不要**给 urlopen 传自定义 SSLContext。部分网络环境下（含企业代理/部分
CDN 节点）显式 SSLContext 会命中错误的缓存内容；把 certifi 的 CA 路径写入
SSL_CERT_FILE、使用默认上下文反而最稳。
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

from . import config


class NetError(Exception):
    """网络或接口错误。"""


def _prepare_ssl() -> None:
    """安卓系统的 CA 路径常常不存在，优先使用 certifi 的证书包。"""
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi  # type: ignore

        os.environ["SSL_CERT_FILE"] = certifi.where()
    except Exception:
        pass


_prepare_ssl()


def get_text(url: str, timeout: float | None = None, retry: int | None = None,
             referer: str = "https://quote.eastmoney.com/") -> str:
    """GET 文本，带重试。"""
    timeout = config.TIMEOUT if timeout is None else timeout
    retry = config.RETRY if retry is None else retry
    headers = {
        "User-Agent": config.UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    last: Exception | None = None
    for attempt in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = "utf-8"
                ctype = resp.headers.get("Content-Type", "")
                if "charset=" in ctype:
                    charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
            return raw.decode(charset, "replace")
        except Exception as exc:  # noqa: BLE001 - 统一转换为 NetError
            last = exc
            if attempt < retry:
                time.sleep(0.6 * (attempt + 1))
    raise NetError(f"请求失败: {type(last).__name__}: {last}")


def _unwrap_jsonp(text: str) -> str:
    body = text.strip()
    if body.startswith("(") and body.endswith(")"):
        return body[1:-1]
    if not body.startswith("{"):
        start, end = body.find("("), body.rfind(")")
        if start != -1 and end > start:
            return body[start + 1:end]
    return body


def get_json(url: str, jsonp: bool = False, timeout: float | None = None) -> dict:
    text = get_text(url, timeout=timeout)
    if jsonp:
        text = _unwrap_jsonp(text)
    try:
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raise NetError(f"返回内容不是合法 JSON: {exc}") from exc


class Cache:
    """极简磁盘缓存：key -> {ts, data}。"""

    def __init__(self, directory=None):
        self.dir = directory or config.cache_dir()
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _path(self, key: str):
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
        if len(safe) > 120:
            safe = safe[:120]
        return self.dir / f"{safe}.json"

    def get(self, key: str):
        path = self._path(key)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            return float(payload["ts"]), payload["data"]
        except Exception:
            return None

    def set(self, key: str, data) -> None:
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"ts": time.time(), "data": data}, fh, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            pass


_CACHE: Cache | None = None


def cache() -> Cache:
    global _CACHE
    if _CACHE is None:
        _CACHE = Cache()
    return _CACHE


def cached(key: str, ttl: float, producer, allow_stale: bool = True):
    """取缓存 / 请求网络。

    返回 (data, source)，source 取值：
        'cache' 命中新鲜缓存
        'net'   本次网络获取
        'stale' 网络失败，回退旧缓存
    """
    store = cache()
    hit = store.get(key)
    now = time.time()
    if hit is not None and now - hit[0] <= ttl:
        return hit[1], "cache"
    try:
        data = producer()
    except Exception:
        if hit is not None and allow_stale:
            return hit[1], "stale"
        raise
    store.set(key, data)
    return data, "net"
