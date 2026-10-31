"""자비스12 시장분석 「🧮 분산일」 — 나스닥 종합 · S&P 500 (2026-10-31 상하님 「넣어라」).

세는 법은 자비스13(jarvis13_market.distribution_days)과 같고, 12년치 재기(research/j12_distribution_measure.py · 깃허브 실행
41158295531)도 그 셈으로 쟀다. 자비스13 파일을 부르지 않고 셈을 여기 따로 둔다 — 자비스13 을 고쳐도 자비스12 가 따라 바뀌지 않게.
  · 분산일 = 지수가 0.2% 넘게 내리고 거래량이 전날보다 많은 날 · 끝난 장까지 25거래일 · 그 뒤 종가가 5% 넘게 오르면 뺌
  · 미국장이 열려 있는 동안(미국 동부 16:15 전)은 오늘 봉을 뺀다 — 반나절 거래량은 늘 전날보다 적다.
경고로 쓰지 않는다(재 보니 7일 넘은 뒤가 오히려 더 올랐다) · 점수·판정·목록에 안 쓴다. 문턱을 그리지 않는다.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

MODULE_REVISION = 2026103101
DIST_WINDOW = 25
DIST_DROP_PCT = -0.2
DIST_RALLY_PCT = 5.0
NY = ZoneInfo("America/New_York")
# 12년치 재기 숫자(2014-01 ~ 2026-10-30 · 깃허브 실행 41158295531) — 화면 줄에 그대로 적는다.
MEASURED = {"run": 41158295531,
            "ixic": {"hot40": 3.63, "base40": 2.62, "hot_dd10": 18, "base_dd10": 13},
            "spx": {"hot40": 4.08, "base40": 1.98, "hot_dd10": 14, "base_dd10": 8}}


def _day(stamp):
    stamp = pd.Timestamp(stamp)
    return (stamp.tz_convert(NY) if stamp.tzinfo else stamp).date()


def finished(frame, now: datetime | None = None):
    """끝난 장만 — 마지막 봉이 미국 동부 오늘이고 16:15 전이면 뺀다."""
    if frame is None or getattr(frame, "empty", True):
        return frame
    now = (now or datetime.now(timezone.utc)).astimezone(NY)
    if _day(frame.index[-1]) == now.date() and now.time() < time(16, 15):
        return frame.iloc[:-1]
    return frame


def distribution_days(frame, *, now: datetime | None = None, window: int = DIST_WINDOW) -> dict | None:
    """끝난 장까지 최근 window 거래일 안의 분산일 — {"count", "dates", "last_day"}. 거래량이 없으면 None."""
    if frame is None or getattr(frame, "empty", True) or "Close" not in frame or "Volume" not in frame:
        return None
    data = finished(frame, now)[["Close", "Volume"]].dropna()
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
        dates.append(str(_day(stamp)))
    return {"count": len(dates), "dates": dates, "last_day": str(_day(data.index[-1]))}


def line_html(ixic: dict | None, spx: dict | None) -> str:
    """시장분석 막대 밑 한 줄. 둘 다 못 세면 빈 글(줄을 안 그린다)."""
    parts = [f"{name} <b style='white-space:nowrap'>{item['count']}일</b>"
             for name, item in (("나스닥 종합", ixic), ("S&amp;P 500", spx)) if item]
    if not parts:
        return ""
    m = MEASURED
    return ("<div class='j3-ndd-note' style='margin-top:.15rem'>🧮 분산일(끝난 장 · 25거래일): " + " · ".join(parts)
            + f" — 12년치로 재 보니 7일 넘은 뒤 40일 평균은 오히려 더 올랐고(나스닥 +{m['ixic']['hot40']:.1f}% · 아무 날 "
            f"+{m['ixic']['base40']:.1f}%), 40일 안 −10% 넘게 빠진 비율은 높았습니다(나스닥 {m['ixic']['hot_dd10']}% · "
            f"아무 날 {m['ixic']['base_dd10']}% · S&amp;P {m['spx']['hot_dd10']}% · {m['spx']['base_dd10']}%) — "
            "경고로 쓰지 않고 점수·판정에 안 씀</div>")
