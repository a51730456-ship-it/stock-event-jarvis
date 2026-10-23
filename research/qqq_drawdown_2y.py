"""QQQ 는 고점에서 몇 % 빠졌을 때 사면 2년 뒤 성적이 나은가 (2026-10-23 상하님 「여기서 이야기하는 12% 는 QQQ 여야 되지 않냐」).

맨 위 낙폭 막대 밑 글(「IXIC 가 1년 최고 종가에서 12% 넘게 빠졌을 때 사서 2년 뒤 팔면 100번 중 86번」 · jarvis3_data 6230줄)을
QQQ 로 다시 잰다. 그 55년치 측정 프로그램은 저장소에 없어 같은 모양으로 새로 짰다 — IXIC 도 같이 재서 옛 숫자
(아무 날 +27.5% · 81번 · 12% +44.7% · 86번)가 비슷하게 나오는지로 재는 틀을 확인한다.

  · 낙폭 — IXIC: 그날 종가 ÷ 1년(252장) 최고 종가 − 1 (막대 글과 같음)
            QQQ : 그날 종가 ÷ 1년 최고가(고가) − 1 (상하님 엑셀 · 화면 「QQQ 낙폭」과 같음)
  · 산 날 — 한 하락에 한 번, 처음 −X% 아래로 닿은 날 종가. 종가가 1년 최고 종가를 되찾으면 다음 하락을 센다.
  · 판 날 — 504 거래일(2년) 뒤 종가. 가운데 값과 100번 중 이익 난 횟수.
야후가 막힌 클라우드에서는 못 돈다 — 깃허브(.github/workflows/j12_band_remeasure.yml)에서 돌린다.
"""
from __future__ import annotations

import numpy as np
import yfinance as yf

HOLD = 504
LEVELS = (5, 6, 8, 10, 12, 15, 20, 25)


def series(symbol: str, start: str):
    frame = yf.download(symbol, start=start, interval="1d", auto_adjust=True, progress=False)
    return frame["Close"].squeeze().dropna(), frame["High"].squeeze().dropna()


def report(name: str, close, peak) -> None:
    drop = (close / peak - 1.0).dropna()
    # 다음 하락을 세는 때 — 종가가 1년 최고 종가를 되찾은 날(앱의 급락 끝과 같음). 고가 기준 낙폭은 0 에 거의 안 닿아
    # 「낙폭 0」으로 다시 켜면 첫 하락 하나만 세진다(가짜 자료 시험에서 발견).
    back = (close >= close.rolling(252, min_periods=252).max() - 1e-9).reindex(drop.index).fillna(False)
    forward = (close.shift(-HOLD) / close - 1.0) * 100.0
    base = forward.reindex(drop.index).dropna()
    print(f"\n{name} · {close.index[0].date()} ~ {close.index[-1].date()}")
    print(f"  아무 날이나 샀으면  2년 뒤 가운데 {np.median(base):+.1f}% · 100번 중 {np.mean(base > 0) * 100:.0f}번 ({len(base)}날)")
    for level in LEVELS:
        days, armed = [], True
        for day, value in drop.items():
            if back.loc[day]:
                armed = True
            elif armed and value <= -level / 100.0:
                days.append(day)
                armed = False
        got = forward.reindex(days).dropna()
        if len(got):
            print(f"  {level:>2}% 빠졌을 때   2년 뒤 가운데 {np.median(got):+.1f}% · 100번 중 {np.mean(got > 0) * 100:.0f}번 "
                  f"({len(days)}번 · 2년 지난 것 {len(got)}번)")
        else:
            print(f"  {level:>2}% 빠졌을 때   2년 지난 것 없음 ({len(days)}번)")


ixic_close, _ixic_high = series("^IXIC", "1970-01-01")
report("나스닥 종합(IXIC) — 1년 최고 종가 기준(막대 글 확인용)", ixic_close,
       ixic_close.rolling(252, min_periods=252).max())
qqq_close, qqq_high = series("QQQ", "1999-01-01")
report("QQQ — 1년 최고가(고가) 기준(엑셀 · 화면 「QQQ 낙폭」과 같음)", qqq_close,
       qqq_high.rolling(252, min_periods=252).max())
