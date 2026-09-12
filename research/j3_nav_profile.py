"""자비스3 — 관심종목 ↔ 시장분석 화면 넘김이 왜 늦은지 **재 본다**.

2026-09-10 상하님 — "관심종목에서 시장분석으로 2초, 시장분석에서 관심종목으로
4초. 너무 늦다."

이 스크립트는 **진짜 화면 코드를 그대로 돌린다.** 바꾸는 것은 딱 두 군데,
바깥으로 나가는 길목뿐이다.

  * `yfinance.download`  → 가짜 시세를 만들고 `--latency` 초만큼 잔다.
  * `urllib.request.urlopen` → 바로 실패시킨다(뉴스·공포탐욕은 원래 실패해도
    화면이 도는 구조다).

이렇게 하면 **몇 번 나가는지**와 **파이썬이 순수하게 얼마를 쓰는지**가 갈라져
보인다. 실제 폰에서 걸리는 시간 = 파이썬 시간 + (나간 횟수 × 실제 왕복).

돌리는 법:
    python3 research/j3_nav_profile.py                # 왕복 0.30초로 가정
    python3 research/j3_nav_profile.py --latency 0.6  # 폰이 느릴 때
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import threading
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

PAGE = ROOT / "pages" / "2_자비스3.py"

FETCHES: list[dict] = []
LATENCY = 0.30


# ── 바깥으로 나가는 길목 두 개만 가짜로 바꾼다 ──────────────────────────────
def _fake_frame(rows: int, freq: str, start: float) -> pd.DataFrame:
    index = (pd.bdate_range("2026-03-02", periods=rows) if freq == "1d"
             else pd.date_range("2026-09-08 09:30", periods=rows, freq="5min"))
    walk = start * (1 + np.linspace(0, 0.12, rows) + np.sin(np.arange(rows) / 7) * 0.01)
    return pd.DataFrame(
        {"Open": walk, "High": walk * 1.01, "Low": walk * 0.99,
         "Close": walk, "Volume": np.full(rows, 1_000_000.0)},
        index=index,
    )


def _fake_download(tickers, **kwargs):
    """yfinance.download 대신. 잔 시간과 티커 수를 적어 둔다."""
    names = [str(t).strip().upper() for t in (tickers if isinstance(tickers, (list, tuple)) else [tickers])]
    interval = str(kwargs.get("interval", "1d"))
    rows = 126 if interval == "1d" else 156
    time.sleep(LATENCY)
    FETCHES.append({
        "tickers": len(names), "period": str(kwargs.get("period", "")),
        "interval": interval, "at": time.perf_counter(),
        "thread": threading.current_thread().name,
    })
    frames = {name: _fake_frame(rows, "1d" if interval == "1d" else "5m", 100 + i)
              for i, name in enumerate(names)}
    joined = pd.concat(frames, axis=1)
    joined.columns = pd.MultiIndex.from_tuples(list(joined.columns))
    return joined


def _install_stubs() -> None:
    fake_yf = types.ModuleType("yfinance")
    fake_yf.download = _fake_download
    fake_yf.set_tz_cache_location = lambda *a, **k: None

    class _Sector:                      # 섹터 비중은 안 쓴다
        def __init__(self, *a, **k):
            self.overview = {}
    fake_yf.Sector = _Sector
    sys.modules["yfinance"] = fake_yf

    # 선물 칸(나스닥100·S&P500)도 바깥으로 나간다 — requests 를 쓰므로 위
    # urlopen 갈아치우기에 안 걸린다. 여기서 같이 막지 않으면 이 컨테이너에서는
    # 세 번 다시 받으며 1.8초를 자 버려, 실제와 전혀 다른 숫자가 나온다.
    import jarvis4_data

    def _fake_futures(symbol, label, interval="1m"):
        time.sleep(LATENCY)
        FETCHES.append({"tickers": 1, "period": "2d", "interval": str(interval),
                        "at": time.perf_counter(),
                        "thread": threading.current_thread().name})
        stamps = pd.date_range("2026-09-09 09:30", periods=60, freq="5min")
        closes = [20000 + i * 3.0 for i in range(60)]
        return {"ok": True, "label": label, "symbol": symbol,
                "current": closes[-1], "prev_close": closes[0],
                "change_pct": 1.2, "source_time": stamps[-1].isoformat(),
                "chart": pd.DataFrame({"Close": closes}, index=stamps)}
    jarvis4_data._fetch_yahoo_1m_chart = _fake_futures

    import urllib.request

    def _no_net(*a, **k):
        raise OSError("프로파일 중에는 바깥으로 안 나간다")
    urllib.request.urlopen = _no_net

    # 시세 파일 공책과 DB는 임시 폴더로 돌린다 — 진짜 자료를 안 건드린다.
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="j3prof-"))
    import jarvis3_data
    jarvis3_data._DISK_DIR = tmp / "prices"
    import database
    database.DB_PATH = tmp / "jarvis.sqlite3"
    import jarvis3_briefing_store as store
    store.DB_PATH = tmp / "jarvis.sqlite3"
    return tmp


# ── 어느 함수가 얼마를 먹는지 ────────────────────────────────────────────────
SPANS: list[tuple[str, float]] = []


def _time_calls(module, names, label_prefix=""):
    for name in names:
        original = getattr(module, name, None)
        if not callable(original):
            continue

        def make(original=original, name=name):
            def wrapped(*a, **k):
                begin = time.perf_counter()
                try:
                    return original(*a, **k)
                finally:
                    SPANS.append((label_prefix + name, time.perf_counter() - begin))
            return wrapped
        setattr(module, name, make())


def _run(app, label):
    SPANS.clear()
    marks = len(FETCHES)
    begin = time.perf_counter()
    quiet = io.StringIO()
    with redirect_stdout(quiet), redirect_stderr(quiet):
        app.run()
    spent = time.perf_counter() - begin
    calls = FETCHES[marks:]
    slept = sum(LATENCY for _ in calls)
    rows = {}
    for name, took in SPANS:
        entry = rows.setdefault(name, [0, 0.0])
        entry[0] += 1
        entry[1] += took
    print(f"\n■ {label}")
    print(f"   전체            {spent:6.2f}초")
    detail = ", ".join(f'{c["tickers"]}개 {c["period"]}/{c["interval"]}' for c in calls)
    print(f"   바깥에 나간 것  {len(calls):2d}번 · 합계 {slept:5.2f}초"
          + (f"  ({detail})" if calls else ""))
    print(f"   파이썬만        {spent - slept:6.2f}초")
    for name, (count, took) in sorted(rows.items(), key=lambda kv: -kv[1][1])[:12]:
        if took < 0.01:
            continue
        print(f"      {name:<34} {count:3d}회 {took:6.2f}초")
    return spent, len(calls), spent - slept


def main() -> None:
    global LATENCY
    parser = argparse.ArgumentParser()
    parser.add_argument("--latency", type=float, default=0.30,
                        help="시세 한 번 받는 데 걸린다고 볼 시간(초)")
    args = parser.parse_args()
    LATENCY = args.latency

    tmp = _install_stubs()
    from streamlit.testing.v1 import AppTest

    import jarvis3_data
    import jarvis3_briefing_news as news
    import market_signal_ui
    _time_calls(jarvis3_data, [
        "get_briefing_cards", "get_market_overview", "get_theme_ranking",
        "get_theme_leaders", "find_pullback_stocks", "find_breakout_pullbacks",
        "find_crash_rebound_stocks", "get_top7_snapshot",
    ], "j3data.")
    _time_calls(news, ["headline", "prefetch", "refresh_async"], "news.")
    _time_calls(market_signal_ui, ["render_us_market_signal_card"], "ui.")

    app = AppTest.from_file(str(PAGE), default_timeout=180)
    app.secrets["APP_PASSWORD"] = "test"
    app.session_state["authenticated"] = True
    app.session_state["jarvis_access_role"] = "guest"

    print(f"가정 — 시세 한 번 받는 데 {LATENCY:.2f}초 (임시 폴더 {tmp})")
    _run(app, "① 처음 열기 (관심종목) — 공책이 비어 있다")
    _run(app, "② 그대로 다시 그리기 (관심종목) — 공책이 차 있다")

    def click(key):
        for button in app.button:
            if button.key == key:
                button.click()
                return True
        return False

    if click("j3b_swipe_market"):
        _run(app, "③ 관심종목 → 시장분석 (밀어서)")
    else:
        print("!! j3b_swipe_market 단추를 못 찾았다")
    if click("j3b_swipe_watch"):
        _run(app, "④ 시장분석 → 관심종목 (밀어서)")
    else:
        print("!! j3b_swipe_watch 단추를 못 찾았다")
    if click("j3b_swipe_market"):
        _run(app, "⑤ 관심종목 → 시장분석 (두 번째)")
    if click("j3b_swipe_watch"):
        _run(app, "⑥ 시장분석 → 관심종목 (두 번째)")


if __name__ == "__main__":
    main()
