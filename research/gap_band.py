"""구멍 난 구간을 잰다 (2026-08-06 사용자 지적).

상승장은 -4~-15%, 급락은 -20~-50%만 본다. 그 사이 **-15~-20%**와 **-50% 아래**가
어디에도 안 잡힌다. 그 구간이 값을 하는지 재서, 넣을지 말지 정한다.

    python research/gap_band.py
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
QDD = (Q["Close"] / Q["High"].rolling(252, min_periods=252).max() - 1.0) * 100
SPLIT = pd.Timestamp("2021-08-01")
HOLDS = [(60, "3개월"), (120, "6개월"), (250, "1년")]

PRE = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    PRE[t] = {"idx": df.index, "dd": ((df["Close"] / hi - 1.0) * 100).values,
              "ret": {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0).values * 100
                      for h, lab in HOLDS}}

# 나스닥이 -6~-12%였던 날에만 본다 (급락 갈래가 쓰는 자리)
MARKET = set(QDD.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
BANDS = [(-15.0, -10.0, "10~15%"), (-20.0, -15.0, "15~20% ← 구멍"),
         (-30.0, -20.0, "20~30%"), (-50.0, -30.0, "30~50%"),
         (-200.0, -50.0, "50% 아래 ← 구멍")]


def collect(lo, hi, lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for i in range(len(p["idx"])):
            dt = p["idx"][i]
            if dt not in MARKET or not np.isfinite(p["dd"][i]):
                continue
            if not (lo <= p["dd"][i] < hi):
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            if np.isfinite(r[i]):
                out.append(r[i])
    return np.array(out)


def base(lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for i in range(252, len(p["idx"])):
            dt = p["idx"][i]
            if dt not in MARKET or not np.isfinite(p["dd"][i]) or not np.isfinite(r[i]):
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            out.append(r[i])
    return np.array(out)


print(f"나스닥이 -6~-12%였던 날 {len(MARKET)}일 · 나스닥100 {len(PRE)}종목")
print("=" * 84)
print(f"  {'종목 낙폭':<18}{'잰 횟수':>9}" + "".join(f"{lab:>20}" for _h, lab in HOLDS))
b = {lab: base(lab) for _h, lab in HOLDS}
line = f"  {'그날 아무 종목이나':<15}{len(b['6개월']):>9,}"
for _h, lab in HOLDS:
    line += f"{np.median(b[lab]):+11.1f}% {(b[lab] > 0).mean()*100:6.1f}%"
print(line)
print("  " + "-" * 80)
for lo, hi, name in BANDS:
    v6 = collect(lo, hi, "6개월")
    line = f"  {name:<18}{len(v6):>9,}"
    for _h, lab in HOLDS:
        v = collect(lo, hi, lab)
        line += (f"{np.median(v):+11.1f}% {(v > 0).mean()*100:6.1f}%"
                 if len(v) >= 100 else f"{'표본 부족':>20}")
    print(line)

print("\n교차 검증 — 앞 5년 / 뒤 5년 (6개월 승률, 그 시기 기준선 대비)")
ba, bb = base("6개월", "a"), base("6개월", "b")
for lo, hi, name in BANDS:
    a, bx = collect(lo, hi, "6개월", "a"), collect(lo, hi, "6개월", "b")
    if len(a) < 50 or len(bx) < 50:
        print(f"  {name:<18} 표본 부족")
        continue
    da = (a > 0).mean() * 100 - (ba > 0).mean() * 100
    db = (bx > 0).mean() * 100 - (bb > 0).mean() * 100
    verdict = "양쪽 다 이김" if da > 0 and db > 0 else ("양쪽 다 짐" if da <= 0 and db <= 0 else "한쪽만")
    print(f"  {name:<18} 앞 {da:+6.1f}%p   뒤 {db:+6.1f}%p   {verdict}")
