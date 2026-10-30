"""자비스13 전용 — 코스피·코스닥 「이번 하락」 한 줄에 쓰는 값 (2026-10-30 · 자비스12 의 「📉 이번 하락(QQQ)」 을 한국에 맞춰 옮김).

자는 자비스4 급락 화면(jarvis4_data.kr_crash_market_state)과 **같다** — 1년(252거래일) 최고 **종가** → 그날 종가.
그래야 막대의 큰 숫자 · 이 한 줄 · 급락 후 반등장 설명이 같은 숫자다(자비스12 에서 나스닥 종합(IXIC)과 QQQ 숫자가 달라
헷갈리셨던 일 · 2026-10-27 상하님 「둘 다 정확한 답을 맞춰라」).

얼린 jarvis4_data 는 **읽기만** 한다 — 지수 받기(_index_frame) · 10분 보관과 실패하면 마지막 값(_cached)을 그대로 쓴다.
못 받으면 ok=False 를 돌려주고, 화면은 이 한 줄만 안 그린다(막대는 그대로 — CLAUDE.md 0-0).
"""
from __future__ import annotations

import time

import pandas as pd

import jarvis4_data as j4data

# 값이나 돌려주는 칸을 바꾸면 올리고 자비스13 의 _REQUIRED_J13_MARKET_REVISION 도 같이 올린다(규칙 11).
# 2026103003 — episode 에 분산일(dist)을 더함.
MODULE_REVISION = 2026103003

# 분산일(오닐 · IBD 방식 · 2026-10-30 상하님 「다 넣어라」 — 자비스에 넣을 기능 ⑤) — 지수가 0.2% 넘게 내리면서 거래량이
# 전날보다 많은 날(큰손이 판 흔적). 25거래일이 지나거나 그날 종가보다 5% 넘게 오르면 센 데서 뺀다. 보여 주기만 한다.
DIST_WINDOW = 25
DIST_DROP_PCT = -0.2
DIST_RALLY_PCT = 5.0

_SYMBOLS = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}
# 못 받은 지수는 2분 동안 다시 받으러 가지 않는다 — 네이버가 느릴 때 1분마다 도는 시장판단 판이 그만큼 붙잡히지 않게
# (CLAUDE.md 0-0 ①). 받아 둔 값이 있으면 _cached 가 그 값을 먼저 준다.
_RETRY_AFTER = 120.0
_FAILED_AT: dict = {}


def md(day: str | None) -> str:
    """「2026-06-22」 → 「6월 22일」(자비스12 와 같은 꼴 · 「6/22」 는 점수로 읽힌 적이 있다 — 2026-10-21)."""
    try:
        stamp = pd.Timestamp(day)
    except Exception:
        return str(day or "")
    return f"{stamp.month}월 {stamp.day}일"


def index_frame(name: str = "KOSPI", *, ttl_seconds: float = 600):
    """지수 일봉(Open·High·Low·Close · 약 400일) — 10분 보관 · 못 받으면 None. 성적표의 「같은 날 코스피」가 쓴다."""
    key = str(name).upper()
    symbol = _SYMBOLS[key]
    failed = _FAILED_AT.get(("frame", key))
    if failed is not None and time.time() - failed < _RETRY_AFTER:
        return None

    def _produce():
        frame = j4data._index_frame(symbol)
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            raise RuntimeError(f"{name} 일봉 없음")
        return frame

    try:
        value, _stale = j4data._cached(("j13_index_frame", key), ttl_seconds, _produce)
    except Exception:
        _FAILED_AT[("frame", key)] = time.time()
        return None
    _FAILED_AT.pop(("frame", key), None)
    return value.copy()


def last_finished_day(frame, now=None):
    """마지막으로 **끝난** 장의 날짜 — 장중(서울 15시 40분 전)이면 오늘 봉은 아직 안 끝났으니 그 앞 장(자비스12 「어제까지」와 같은 뜻)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if frame is None or getattr(frame, "empty", True):
        return None
    days = [pd.Timestamp(stamp).date() for stamp in frame.index]
    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if days and days[-1] == now.date() and (now.hour, now.minute) < (15, 40):
        return days[-2] if len(days) > 1 else None
    return days[-1] if days else None


def distribution_days(frame, *, now=None, window: int = DIST_WINDOW) -> dict | None:
    """**끝난 장까지** 최근 window 거래일 안의 분산일 — {"count", "dates", "last_day"}. 거래량이 없으면 None.

    장중(15시 40분 전)에는 오늘 봉을 빼고 센다 — 반나절 거래량은 늘 전날보다 적어 내린 날도 안 잡힌다.
    """
    if frame is None or getattr(frame, "empty", True) or "Close" not in frame or "Volume" not in frame:
        return None
    last = last_finished_day(frame, now)
    if last is None:
        return None
    data = frame[[pd.Timestamp(stamp).date() <= last for stamp in frame.index]][["Close", "Volume"]].dropna()
    if len(data) < window + 1:
        return None
    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    if not (volume > 0).any():
        return None
    falling = (close.pct_change() * 100.0 <= DIST_DROP_PCT) & (volume > volume.shift(1))
    dates = []
    for stamp in data.index[-window:]:
        if not bool(falling.loc[stamp]):
            continue
        after = close.loc[stamp:].iloc[1:]
        if not after.empty and float(after.max()) >= float(close.loc[stamp]) * (1.0 + DIST_RALLY_PCT / 100.0):
            continue                     # 그 뒤 5% 넘게 올라 지워진 날
        dates.append(str(pd.Timestamp(stamp).date()))
    return {"count": len(dates), "dates": dates, "last_day": str(last)}


def episode(name: str = "KOSPI", *, ttl_seconds: float = 600) -> dict:
    """그 지수의 1년 최고 종가와 그날 · 그 뒤 가장 깊었던 날 · 지금 · 분산일.

    돌려주는 것 — peak · peak_date · low · low_date · low_drop(%) · current · date · drop(%) · dist · stale.
    drop 은 kr_crash_market_state 의 drop_pct 와 같은 셈이다(같은 일봉 · 같은 252거래일 · 같은 종가).
    dist 는 같은 일봉으로 센 분산일(distribution_days · 못 세면 None) — 지수를 한 번만 받는다.
    """
    symbol = _SYMBOLS[str(name).upper()]

    def _produce():
        frame = j4data._index_frame(symbol)
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            raise RuntimeError(f"{name} 일봉 없음")
        closes = frame["Close"].dropna()
        if len(closes) < 60:
            raise RuntimeError(f"{name} 일봉이 너무 짧다")
        window = closes.tail(252)
        peak = float(window.max())
        peak_day = pd.Timestamp(window.idxmax())
        after = closes.loc[peak_day:]
        low = float(after.min())
        low_day = pd.Timestamp(after.idxmin())
        current = float(closes.iloc[-1])
        if peak <= 0:
            raise RuntimeError(f"{name} 고점 값이 이상하다")
        try:
            dist = distribution_days(frame)
        except Exception:
            dist = None                  # 분산일을 못 세도 「이번 하락」 줄은 그대로 그린다(CLAUDE.md 0-0)
        return {
            "name": str(name).upper(), "peak": peak, "peak_date": str(peak_day.date()),
            "low": low, "low_date": str(low_day.date()), "low_drop": (low / peak - 1.0) * 100.0,
            "current": current, "date": str(pd.Timestamp(closes.index[-1]).date()),
            "drop": (current / peak - 1.0) * 100.0,
            "dist": dist,
        }

    key = str(name).upper()
    failed = _FAILED_AT.get(key)
    if failed is not None and time.time() - failed < _RETRY_AFTER:
        return {"ok": False, "error": "조금 전에 못 받았다 — 2분 뒤 다시 받는다"}
    try:
        value, stale = j4data._cached(("j13_index_episode", key), ttl_seconds, _produce)
    except Exception as exc:
        _FAILED_AT[key] = time.time()
        return {"ok": False, "error": str(exc)}
    _FAILED_AT.pop(key, None)
    return {"ok": True, "stale": bool(stale), **value}
