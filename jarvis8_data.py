"""J8 single-flight background I/O. Page never waits for a download or scan."""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


class BundleCache:
    """One bounded job, one last-good bundle. Shared across sessions, read-only data."""
    def __init__(self, ttl=1800, retry=60):
        self.ttl, self.retry = ttl, retry
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis8")
        self.future = None
        self.value = None
        self.updated = 0.
        self.attempt = 0.
        self.error = ""

    def request(self, loader=None, refresh=False):
        loader = loader or load_bundle
        with self.lock:
            now = time.monotonic()
            if self.future is not None and self.future.done():
                try:
                    value = self.future.result()
                    if not value.get("ok"):
                        raise ValueError(value.get("error", "자료 갱신 실패"))
                    self.value, self.updated, self.error = value, now, ""
                except Exception as exc:
                    self.error = str(exc)[:250]
                    self.attempt = now
                self.future = None
            expired = self.value is None or now-self.updated >= self.ttl
            cooldown = now-self.attempt >= self.retry
            if self.future is None and ((refresh and cooldown) or (expired and (not self.error or cooldown))):
                self.attempt = now
                self.future = self.pool.submit(loader)
            return {"value": self.value, "pending": self.future is not None,
                    "error": self.error, "stale": bool(self.value and (expired or self.error)),
                    "age_seconds": round(now-self.updated) if self.value else None}


CACHE = BundleCache()
QUOTE_CACHE = BundleCache(ttl=60, retry=60)


def load_market_quotes():
    """Optional ETF reference quotes; never rewrite EOD signals with minute data."""
    import pandas as pd
    import yfinance as yf
    import us_market_calendar as calendar
    from jarvis8_engine import THEMES
    now = datetime.now(calendar.NEW_YORK)
    phase = calendar.phase(now)
    expected = now.date() if phase["label"] == "정규장 시간" else calendar.previous_session_date(now)
    tickers = sorted({t["etf"] for t in THEMES} | {"QQQ", "SPY"})
    raw = yf.download(tickers, period="5d", interval="5m", group_by="ticker",
                      auto_adjust=True, repair=False, prepost=False, threads=6,
                      progress=False, timeout=12)
    quotes = {}
    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            continue
        f = raw[ticker].dropna(subset=["Close"])
        if f.empty:
            continue
        index = pd.to_datetime(f.index)
        f.index = index.tz_localize("UTC").tz_convert(calendar.NEW_YORK) if index.tz is None else index.tz_convert(calendar.NEW_YORK)
        f = f.loc[f.index <= now]
        f = f.loc[[calendar.is_trading_day(d.date()) and
                   calendar.REGULAR_OPEN <= d.time() < calendar.close_time(d.date()) for d in f.index]]
        if f.empty:
            continue
        sessions = f.Close.groupby(f.index.date).last()
        previous = float(sessions.iloc[-2]) if len(sessions) >= 2 else None
        current = float(sessions.iloc[-1])
        ts = f.index[-1]
        stale = ts.date() != expected or (phase["label"] == "정규장 시간" and (now-ts).total_seconds() > 1200)
        quotes[ticker] = {"price": current, "change": (current/previous-1)*100 if previous else None,
                          "time": ts.isoformat(), "stale": stale}
    if not quotes:
        raise ValueError("ETF 참고 시세를 받지 못했습니다")
    return {"ok": True, "quotes": quotes, "phase": phase["label"],
            "fetched_at": now.isoformat(timespec="seconds")}


def archive(bundle, frames, ixic, directory=None):
    """Content-addressed evidence, atomic install; no pickle and no original overwrite.

    Includes consumed price rows and code hashes, not just performance claims.
    Runs only while someone uses J8; this is NOT an unattended daily collector.
    """
    root = Path(directory) if directory else ROOT/"data/jarvis8/observations"
    root.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in bundle.items() if k not in ("charts", "observation", "observation_sha256")}
    identity = {"as_of": bundle["as_of"], "version": bundle["version"],
                "inputs": bundle["input_hashes"], "engines": bundle["engine_hashes"]}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    target = root/f"{bundle['as_of']}_{bundle['version']}_{key[:16]}.json.gz"
    if target.exists():
        raw = gzip.decompress(target.read_bytes())
        return str(target), hashlib.sha256(raw).hexdigest()
    body["first_observed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body["prices"] = {s: {"dates": [str(d.date()) for d in f.index],
                           "columns": list(f.columns), "values": f.where(f.notna(), None).values.tolist()}
                      for s, f in dict(frames, **{"^IXIC_LONG": ixic}).items()}
    # NaN is encoded as null, including missing source bars.
    payload = json.loads(json.dumps(body, default=lambda x: x.item() if hasattr(x, "item") else str(x)))
    def finite(v):
        if isinstance(v, float) and not __import__("math").isfinite(v): return None
        if isinstance(v, list): return [finite(x) for x in v]
        if isinstance(v, dict): return {k: finite(x) for k,x in v.items()}
        return v
    raw = json.dumps(finite(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    digest = hashlib.sha256(raw).hexdigest()
    if not target.exists():
        temporary = root/(uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(gzip.compress(raw, mtime=0))
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return str(target), digest


_INDEX_CACHE = {"frame": None, "day": None}


def completed_benchmark_day(raw, expected):
    """Use the latest shared *complete* SPY/QQQ bar, never a volume-only bar."""
    import numpy as np
    import pandas as pd
    from jarvis8_engine import FIELDS, clean

    common = None
    for ticker in ("SPY", "QQQ"):
        if ticker not in raw.columns.get_level_values(0):
            raise ValueError(f"{ticker}: 시세 없음")
        frame = clean(raw[ticker], expected)
        if not set(FIELDS).issubset(frame.columns):
            raise ValueError(f"{ticker}: 필수 가격 열 없음")
        values = frame[FIELDS].to_numpy(dtype=float)
        complete = frame.index[np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)]
        common = complete if common is None else common.intersection(complete)
    if common is None or len(common) == 0:
        raise ValueError("SPY·QQQ: 완료된 공통 일봉 없음")
    return pd.Timestamp(common[-1]).date()


def load_bundle():
    start = time.perf_counter()
    import pandas as pd
    import yfinance as yf
    import us_market_calendar as calendar
    from jarvis8_engine import build, clean, TICKERS
    expected = calendar.previous_session_date()
    # 21 sector ETFs, minutes, news and single-stock quote calls are not needed for EOD ranking.
    requested = list(TICKERS)+["SPY", "QQQ"]
    raw = yf.download(requested, period="2y", interval="1d", group_by="ticker",
                      auto_adjust=True, repair=False, threads=8, progress=False, timeout=15)
    # Yahoo can publish Volume before adjusted OHLC. That partial bar is not a
    # closing price; show the previous completed session as stale observation.
    day = completed_benchmark_day(raw, expected)
    frames = {s: clean(raw[s], day) for s in requested if s in raw.columns.get_level_values(0)}
    history = _INDEX_CACHE["frame"] if _INDEX_CACHE["day"] == day else None
    if history is None:
        history = yf.download("^IXIC", start="2000-01-01", interval="1d", auto_adjust=True,
                              repair=False, progress=False, threads=False, timeout=15)
        if isinstance(history.columns, pd.MultiIndex):
            history = history.xs("^IXIC", axis=1, level=-1)
        history = clean(history, day)
        if len(history) >= 3000 and history.index[-1].date() == day:
            _INDEX_CACHE.update(frame=history, day=day)
    bundle = build(frames, day, history)
    bundle["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle["source"] = "Yahoo Finance · 조정 일봉 · 정규장 마감 기준"
    bundle["load_seconds"] = round(time.perf_counter()-start, 3)
    try:
        path, digest = archive(bundle, frames, history)
        bundle["observation"] = Path(path).name
        bundle["observation_sha256"] = digest
    except Exception as exc:
        bundle["observation_error"] = f"관측 저장 실패: {type(exc).__name__}"
    return bundle
