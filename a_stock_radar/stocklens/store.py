# -*- coding: utf-8 -*-
"""自选股本地存储（JSON 文件，放在应用私有目录）。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import config


class Watchlist:
    def __init__(self, path: Path | None = None):
        self.path = path or (config.data_dir() / "watchlist.json")
        self._items: list[dict] | None = None

    # ------------------------------------------------------------------ #
    def _read(self) -> list[dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            items = payload.get("items") if isinstance(payload, dict) else payload
            if isinstance(items, list):
                cleaned = []
                for row in items:
                    code = str(row.get("code") or "").strip()
                    if not code:
                        continue
                    cleaned.append(
                        {
                            "code": code,
                            "name": str(row.get("name") or code),
                            "secid": str(row.get("secid") or ""),
                        }
                    )
                return cleaned
        except Exception:
            pass
        return []

    def load(self) -> list[dict]:
        if self._items is None:
            self._items = self._read()
            if not self._items:
                self._items = [dict(row, secid="") for row in config.DEFAULT_WATCHLIST]
                self.save(self._items)
        return self._items

    # ------------------------------------------------------------------ #
    def save(self, items: list[dict]) -> None:
        self._items = items
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"items": items}, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def has(self, code: str) -> bool:
        return any(row["code"] == code for row in self.load())

    def add(self, code: str, name: str, secid: str = "") -> list[dict]:
        code = (code or "").strip()
        if not code:
            return self.load()
        items = [row for row in self.load() if row["code"] != code]
        items.insert(0, {"code": code, "name": name or code, "secid": secid})
        self.save(items)
        return items

    def remove(self, code: str) -> list[dict]:
        items = [row for row in self.load() if row["code"] != code]
        self.save(items)
        return items
