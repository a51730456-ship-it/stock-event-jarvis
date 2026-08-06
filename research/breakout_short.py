"""보유기간을 짧게도 재본다 — 1주부터 1년까지.

물음: 신고가 눌림의 이점이 짧게 들어도 나오나, 아니면 오래 들어야만 나오나?
오래 들어야만 나온다면 그건 규칙이 아니라 시장이 오른 덕일 수 있다.
"""
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
SPLIT = pd.Timestamp("2021-08-01")

HOLDS = [(5, "1주"), (10, "2주"), (20, "1개월"), (40, "2개월"),
         (60, "3개월"), (120, "6개월"), (250, "1년")]
CASES = [((1, 3), (-0.06, -0.04), "1~3일 · 4~6%"),
         ((3, 5), (-0.06, -0.04), "3~5일 · 4~6%  ← 지금 설명서"),
         ((1, 3), (-0.15, -0.10), "1~3일 · 10~15%"),
         ((3, 5), (-0.15, -0.10), "3~5일 · 10~15%")]

PRE = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    PRE[t] = {"idx": df.index, "high": df["High"].values, "close": df["Close"].values,
              "hi": hi.values, "nh": (df["High"] >= hi).values,
              "ret": {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0).values * 100
                      for h, lab in HOLDS}}


def signals(p, w0, w1, d0, d1):
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


SIG = {c[2]: {t: signals(p, c[0][0], c[0][1], c[1][0], c[1][1]) for t, p in PRE.items()}
       for c in CASES}


def collect(name, lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for j in SIG[name][t]:
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


print("=" * 104)
print("보유기간별 — 가운데 값 / 승률 / 기준선보다 몇 %p")
print("=" * 104)
BASE = {lab: base(lab) for _h, lab in HOLDS}
print(f"  {'기준선(아무 종목)':<24}" + "".join(f"{l:>11}" for _h, l in HOLDS))
print(f"  {'  가운데 값':<25}" + "".join(f"{np.median(BASE[l]):+10.1f}%" for _h, l in HOLDS))
print(f"  {'  승률':<27}" + "".join(f"{(BASE[l]>0).mean()*100:10.1f}%" for _h, l in HOLDS))
print()
for w, db, name in CASES:
    print(f"  {name}")
    line_m = f"    {'가운데 값':<21}"
    line_w = f"    {'승률':<23}"
    line_d = f"    {'기준선보다':<21}"
    for _h, lab in HOLDS:
        v = collect(name, lab)
        if len(v) < 100:
            line_m += f"{'—':>11}"
            line_w += f"{'—':>11}"
            line_d += f"{'—':>11}"
            continue
        line_m += f"{np.median(v):+10.1f}%"
        line_w += f"{(v > 0).mean()*100:10.1f}%"
        line_d += f"{(v > 0).mean()*100 - (BASE[lab] > 0).mean()*100:+9.1f}%p"
    print(line_m)
    print(line_w)
    print(line_d)
    print()

print("=" * 104)
print("교차 검증 — 앞 5년 / 뒤 5년 각각 기준선보다 몇 %p (승률)")
print("=" * 104)
BA = {lab: base(lab, "a") for _h, lab in HOLDS}
BB = {lab: base(lab, "b") for _h, lab in HOLDS}
print(f"  {'':<26}" + "".join(f"{l:>11}" for _h, l in HOLDS))
for w, db, name in CASES:
    la = f"  {name[:16]:<18}앞 5년 "
    lb = f"  {'':<18}뒤 5년 "
    for _h, lab in HOLDS:
        a, b = collect(name, lab, "a"), collect(name, lab, "b")
        la += (f"{(a > 0).mean()*100 - (BA[lab] > 0).mean()*100:+9.1f}%p"
               if len(a) >= 50 else f"{'—':>11}")
        lb += (f"{(b > 0).mean()*100 - (BB[lab] > 0).mean()*100:+9.1f}%p"
               if len(b) >= 50 else f"{'—':>11}")
    print(la)
    print(lb)
    print()
