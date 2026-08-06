"""신고가 뒤 1~5일 · 10~15% 눌림을 잰다 (2026-08-06 사용자 지시).

사용자 결정 — **눌린 폭 10~15%가 첫 기준**이고, 기다린 날(1~5일)은 화면에 보여만
주고 사람이 판단한다. 그래서 1~3일과 3~5일을 하나로 합친 값이 필요하다.

    python research/breakout_1to5.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

NDX = """AAPL MSFT NVDA AMZN AVGO META TSLA GOOGL GOOG COST NFLX TMUS PLTR CSCO AMD LIN PEP
INTU ISRG TXN QCOM BKNG ADBE AMGN HON AMAT GILD PANW ADP VRTX MU LRCX ADI SBUX MELI KLAC INTC
CRWD CEG MDLZ CTAS PYPL CDNS SNPS MAR ORLY ABNB REGN FTNT ASML CSX WDAY TTD PDD ROP MNST AEP
NXPI DASH CHTR PCAR ADSK ROST FANG PAYX AZN KDP MRVL ODFL FAST EA CPRT VRSK IDXX EXC BKR CTSH
XEL CCEP KHC TEAM LULU ZS DXCM TTWO MCHP ON CDW GEHC WBD BIIB ILMN MDB ARM APP AXON""".split()

d = yf.download(NDX + ["QQQ"], period="10y", interval="1d", auto_adjust=True,
                group_by="ticker", threads=8, progress=False)
data = {}
for t in NDX + ["QQQ"]:
    try:
        df = d[t].dropna(how="all")[["Open", "High", "Low", "Close"]].dropna()
    except Exception:
        continue
    if len(df) >= 400:
        data[t] = df
Q = data.pop("QQQ")
QDD = Q["Close"] / Q["High"].rolling(252, min_periods=252).max() - 1.0
QMA = Q["Close"].rolling(200, min_periods=200).mean()
UP = set(Q.index[((Q["Close"] > QMA) & (QDD > -0.10)).fillna(False).values])
YEARS = (Q.index[-1] - Q.index[0]).days / 365.25
SPLIT = pd.Timestamp("2021-08-01")
HOLDS = [(60, "3개월"), (120, "6개월"), (250, "1년")]

PRE = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    PRE[t] = {"idx": df.index, "high": df["High"].values, "close": df["Close"].values,
              "hi": hi.values, "nh": (df["High"] >= hi).values,
              "ret": {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0).values * 100
                      for h, lab in HOLDS}}


def signals(p, w0, w1, d0, d1):
    """신고가마다 한 번. 기다리는 중 새 신고가가 나오면 그 자리는 무효."""
    out, n = [], len(p["idx"])
    nh, cl, hg, h2 = p["nh"], p["close"], p["high"], p["hi"]
    i = 251
    while i < n:
        if not (np.isfinite(h2[i]) and nh[i]):
            i += 1
            continue
        peak, fired, j = hg[i], False, i
        for k in range(1, w1 + 1):
            j = i + k
            if j >= n or nh[j]:
                break
            peak = max(peak, hg[j])
            if k >= w0 and d0 <= cl[j] / peak - 1.0 <= d1:
                out.append(j)
                fired = True
                break
        i = (j if fired else i + 1)
    return out


def collect(w, db, lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for j in signals(p, w[0], w[1], db[0], db[1]):
            dt = p["idx"][j]
            if dt not in UP:
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            if np.isfinite(r[j]):
                out.append(r[j])
    return np.array(out)


def base(lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for i in range(251, len(p["idx"])):
            dt = p["idx"][i]
            if dt not in UP or not np.isfinite(p["hi"][i]) or not np.isfinite(r[i]):
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            out.append(r[i])
    return np.array(out)


BAND = (-0.15, -0.10)
print(f"나스닥100 {len(PRE)}종목 · 정상 상승장 {len(UP)}일 · 눌린 폭 10~15%")
print("=" * 84)
print(f"  {'기다린 날':<10}{'1년에':>7}" + "".join(f"{lab:>22}" for _h, lab in HOLDS))
for w, name in (((1, 3), "1~3일"), ((3, 5), "3~5일"), ((1, 5), "1~5일 (합)")):
    line = f"  {name:<11}"
    n = len(collect(w, BAND, "6개월"))
    line += f"{round(n / YEARS):5d}번"
    for _h, lab in HOLDS:
        v = collect(w, BAND, lab)
        line += f"{np.median(v):+11.1f}% {(v > 0).mean()*100:8.1f}%"
    print(line)
line = f"  {'아무 종목이나':<9}{'—':>7}"
for _h, lab in HOLDS:
    b = base(lab)
    line += f"{np.median(b):+11.1f}% {(b > 0).mean()*100:8.1f}%"
print(line)

print("\n교차 검증 — 앞 5년 / 뒤 5년 (6개월 승률, 그 시기 기준선 대비)")
ba, bb = base("6개월", "a"), base("6개월", "b")
for w, name in (((1, 3), "1~3일"), ((3, 5), "3~5일"), ((1, 5), "1~5일 (합)")):
    a, b = collect(w, BAND, "6개월", "a"), collect(w, BAND, "6개월", "b")
    da = (a > 0).mean() * 100 - (ba > 0).mean() * 100
    db_ = (b > 0).mean() * 100 - (bb > 0).mean() * 100
    verdict = "양쪽 다 이김" if da > 0 and db_ > 0 else "한쪽만"
    print(f"  {name:<11}앞 {da:+6.1f}%p   뒤 {db_:+6.1f}%p   {verdict}")
