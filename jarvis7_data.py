"""JARVIS 7's nonblocking read layer. JARVIS 3 remains the calculation authority.

Workers never use Streamlit/session state. A single bounded job per key is shared
between reruns; a failed refresh retains the last successful result and its age.
"""
from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class Snapshot:
    value: object = None
    pending: bool = False
    stale: bool = False
    failed: bool = False
    updated: float = 0
    seconds: float = 0


class ReadCache:
    def __init__(self, workers=3, capacity=96):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jarvis7")
        self.lock = threading.RLock()
        self.entries = {}
        self.capacity = capacity

    def request(self, key, loader, ttl=120):
        now = time.monotonic()
        with self.lock:
            if key not in self.entries and len(self.entries) >= self.capacity:
                evict = next((k for k,e in self.entries.items()
                              if e["future"] is None or e["future"].done()),None)
                if evict is None:
                    return Snapshot(failed=True)
                del self.entries[evict]
            entry = self.entries.setdefault(key, {
                "value": None, "at": 0, "retry": 0, "future": None,
                "failed": False, "updated": 0, "seconds": 0, "generation": 0, "submitted": 0,
            })
            future = entry["future"]
            if future is not None and future.done():
                try:
                    value, seconds = future.result()
                    if entry["generation"] != entry["submitted"]:
                        entry["future"] = None
                        return self.request(key,loader,ttl)
                    if value is None or (isinstance(value, dict) and value.get("ok") is False):
                        raise ValueError("source unavailable")
                    if key[0] == "cards" and isinstance(value, dict):
                        previous = entry.get("value") or {}
                        for ticker, old in previous.items():
                            if (value.get(ticker) or {}).get("price") is None and old.get("price") is not None:
                                value[ticker] = {**old, "stale": True}
                        if value and all(v.get("price") is None for v in value.values()):
                            raise ValueError("quotes unavailable")
                    entry.update(value=value, at=now, updated=time.time(),
                                 failed=False, seconds=seconds)
                except Exception:
                    # Do not print provider errors: they can contain URLs/credentials.
                    entry.update(failed=True, retry=now + 30)
                entry["future"] = None
            expired = not entry["at"] or now - entry["at"] >= ttl
            if expired and entry["future"] is None and now >= entry["retry"]:
                entry["submitted"] = entry["generation"]
                entry["future"] = self.pool.submit(self._load, loader)
            result = Snapshot(copy.deepcopy(entry["value"]), entry["future"] is not None,
                              bool(expired and entry["value"] is not None),
                              entry["failed"], entry["updated"], entry["seconds"])
            # Bound memory without evicting work in flight.
            for old in list(self.entries):
                if len(self.entries) <= self.capacity:
                    break
                if old != key and self.entries[old]["future"] is None:
                    del self.entries[old]
            return result

    @staticmethod
    def _load(loader):
        started = time.perf_counter()
        return loader(), time.perf_counter() - started

    def invalidate(self, prefix):
        with self.lock:
            for key, entry in self.entries.items():
                if key[:len(prefix)] == prefix:
                    entry.update(at=0, retry=0, generation=entry["generation"]+1)


CACHE = ReadCache()


def load(kind, *args):
    """Only invoked by workers: even the large data-module import is off the UI path."""
    if kind == "watch":
        import jarvis7_store
        return jarvis7_store.watchlist()
    if kind == "archive":
        import picklist_store as store
        dates = store.available_dates("US")
        day = args[0] if args and args[0] in dates else (dates[0] if dates else "")
        return {"dates": dates, "day": day, "rows": store.load_rows(day, "US") if day else []}
    if kind == "trades":
        import jarvis7_store
        return jarvis7_store.existing_trades()
    if kind == "news":
        import jarvis3_briefing_news
        return jarvis3_briefing_news.get_or_schedule("stock" if args[0] else "market", args[0] or None)
    import jarvis3_data as j3
    if kind == "market":
        return j3.get_market_overview()
    if kind == "ranking":
        return j3.get_theme_rankings()
    if kind == "cards":
        value = j3.get_briefing_cards([{"ticker": ticker} for ticker in args[0]])
        import us_company_logos
        for ticker in args[0]:
            us_company_logos.get_or_schedule(ticker)
        return value
    if kind == "fear":
        return j3.get_fear_greed()
    if kind == "drawdown":
        return j3.get_nasdaq_drawdown()
    if kind == "sparks":
        return j3.get_index_sparklines()
    if kind == "leaders":
        value = j3.get_theme_leaders(args[0], market_score=args[1], theme_score=args[2],
                                    with_charts=False)
        import us_company_logos
        for row in value.get("rows", []):
            us_company_logos.get_or_schedule(row["ticker"])
        return value
    if kind == "stock":
        return j3.analyze_one_stock(args[0], market_score=args[1])
    if kind == "chart":
        return j3.get_intraday_chart(args[0]) if args[1] == "당일" else j3.get_chart_data(*args)
    if kind == "search":
        return j3.search_stocks(args[0], limit=12)
    if kind == "breakout":
        return j3.breakout_scan(persist=False)
    if kind == "crash":
        return j3.find_crash_rebound_stocks()
    if kind == "top":
        value = j3.collect_top_picks(args[0], market_score=args[1],
                                    breakout=j3.breakout_scan(persist=False))
        # J3 uses ok=bool(picked). An empty successful scan is not a network failure.
        if not value.get("rows") and not value.get("errors"):
            return {**value,"ok":True}
        return value
    raise ValueError("Unknown JARVIS 7 source")


def market_assessment(market):
    """Keep J3's completed-session gauge and distinguish a live fallback."""
    market = market or {}
    closed = market.get("previous_market") or {}
    if closed.get("ok") and closed.get("score") is not None:
        return {**closed, "basis": f"{closed.get('trade_date') or '직전 완료 장'} 마감 기준"}
    if market.get("ok"):
        return {**market, "basis": "조회 시점 참고값 · 직전 완료 장 자료 없음"}
    return {"score": None, "regime": "자료 확인 중", "posture": "시장 자료를 확인하고 있습니다", "basis": "자료 대기"}
