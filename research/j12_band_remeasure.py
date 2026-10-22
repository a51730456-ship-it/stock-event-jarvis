"""자비스12 급락 후 반등장 — 칸별 과거 성적을 지금 규칙으로 다시 잰다 (2026-10-22 상하님 「깃허브로 해라」).

설명 창 카드 숫자(jarvis12_crash.J12_RULES)는 10/21 규칙(종목 낙폭 = 고점일 **종가** → 기준일 종가)으로 잰 것으로
기록돼 있다. 10/22 엑셀대로 고점일 **고가** → 기준일 종가로 바꿔, 두 방법을 나란히 잰다.
옛 방법 줄이 카드 숫자와 같게 나오면 재는 틀이 같다는 뜻이고, 새 방법 줄이 바꿀 숫자다.

재는 틀은 상하님 엑셀(research/ndx_win.py)과 같다 — 나스닥100 96종목 · 10년 · auto_adjust · 기준일 다음 날 시가에 사서
산 날부터 60·120·250 거래일 뒤 종가. 급락·기준일·고점일은 앱 함수(jarvis12_crash.episodes)를 그대로 부른다.
야후가 막힌 클라우드에서는 못 돈다 — 깃허브(.github/workflows/j12_band_remeasure.yml)에서 돌린다.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jarvis3_data as j3  # noqa: E402
import jarvis12_crash as c12  # noqa: E402

NDX = """AAPL MSFT NVDA AMZN AVGO META TSLA GOOGL GOOG COST NFLX TMUS PLTR CSCO AMD LIN PEP
INTU ISRG TXN QCOM BKNG ADBE AMGN HON AMAT GILD PANW ADP VRTX MU LRCX ADI SBUX MELI KLAC INTC
CRWD CEG MDLZ CTAS PYPL CDNS SNPS MAR ORLY ABNB REGN FTNT ASML CSX WDAY TTD PDD ROP MNST AEP
NXPI DASH CHTR PCAR ADSK ROST FANG PAYX AZN KDP MRVL ODFL FAST EA CPRT VRSK IDXX EXC BKR CTSH
XEL CCEP KHC TEAM LULU ZS DXCM TTWO MCHP ON CDW GEHC WBD BIIB ILMN MDB ARM APP AXON""".split()
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))

raw = yf.download(NDX + ["QQQ"], period="10y", interval="1d", auto_adjust=True,
                  group_by="ticker", threads=8, progress=False)
data = {}
for ticker in NDX + ["QQQ"]:
    try:
        frame = raw[ticker].dropna(how="all")[["Open", "High", "Low", "Close"]].dropna()
    except Exception:
        continue
    if len(frame) >= 400:
        data[ticker] = frame
qqq = data.pop("QQQ")
print(f"받은 종목 {len(data)}개 (명부 {len(NDX)}개) · QQQ {qqq.index[0].date()} ~ {qqq.index[-1].date()}")

# 앱의 급락 찾기를 그대로 — 받는 곳만 이 10년치로 바꿔 끼운다.
j3._download_cached = lambda tickers, **kw: ({"QQQ": qqq}, {})
found = c12.episodes()["episodes"]
print(f"\n급락 {len(found)}번 (QQQ 낙폭 = 그날 종가 ÷ 1년 최고가 − 1 ≤ −5% · 기준일 = 가장 깊은 날)")
for item in found:
    print(f"  고점일 {item['peak_date']} · 기준일 {item['reference']} QQQ {item['reference_drop']:.1f}% · "
          f"회복 {item['recovered_on'] or '아직'}")


def measure(peak_field: str) -> dict:
    """peak_field = 'High'(지금 규칙) 또는 'Close'(10/21 규칙) — 고점일의 그 종목 값."""
    out = {rule["key"]: {label: [] for _days, label in HOLDS} for rule in c12.J12_RULES}
    seats = {rule["key"]: 0 for rule in c12.J12_RULES}
    for item in found:
        peak_day = pd.Timestamp(item["peak_date"])
        ref_day = pd.Timestamp(item["reference"])
        for frame in data.values():
            before_peak = frame.loc[:peak_day]
            upto_ref = frame.loc[:ref_day]
            after = frame.loc[frame.index > ref_day]
            if before_peak.empty or upto_ref.empty or after.empty:
                continue
            base = float(before_peak[peak_field].iloc[-1])
            drop = (float(upto_ref["Close"].iloc[-1]) / base - 1.0) * 100.0
            rule = next((r for r in c12.J12_RULES if r["band"][0] <= drop < r["band"][1]), None)
            if rule is None:
                continue
            seats[rule["key"]] += 1
            buy = float(after["Open"].iloc[0])
            for days, label in HOLDS:
                if len(after) > days:
                    out[rule["key"]][label].append((float(after["Close"].iloc[days]) / buy - 1.0) * 100.0)
    return {"returns": out, "seats": seats}


def show(title: str, result: dict) -> None:
    print(f"\n{title}")
    for rule in c12.J12_RULES:
        parts = []
        for _days, label in HOLDS:
            values = np.array(result["returns"][rule["key"]][label])
            if len(values):
                parts.append(f"{label} {np.median(values):+.1f}%(100번 중 {np.mean(values > 0) * 100:.0f}번 · {len(values)}자리)")
            else:
                parts.append(f"{label} 없음")
        print(f"  {rule['label']:<16} 자리 {result['seats'][rule['key']]:>4} · " + " · ".join(parts))


print("\n지금 카드 숫자(J12_RULES)")
for rule in c12.J12_RULES:
    print(f"  {rule['label']:<16} " + " · ".join(
        f"{item['label']} {item['median_return']:+.1f}%(100번 중 {item['win_rate']:.0f}번)" for item in rule["results"]))
show("옛 방법 — 고점일 종가 → 기준일 종가 (10/21 규칙 · 카드 숫자와 같은지 확인용)", measure("Close"))
show("새 방법 — 고점일 고가 → 기준일 종가 (지금 규칙 · 바꿀 숫자)", measure("High"))
