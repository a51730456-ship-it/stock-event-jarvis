"""정상 상승장 — 52주 신고가 돌파 뒤 '며칠 기다려' '얼마나 눌렸을 때' 사나.

날짜와 눌린 폭을 둘 다 갈라 잰다. 나스닥100 96종목 · 10년 · 배당 포함.
교차 검증 — 10년을 2021년 8월에서 반으로 갈라 앞뒤 따로 잰다.
"""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

S = str(Path(__file__).parent / "_data")
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
print(f"나스닥100 {len(data)}종목 · {Q.index[0].date()} ~ {Q.index[-1].date()}")

QHI = Q["High"].rolling(252, min_periods=252).max()
QDD = Q["Close"] / QHI - 1.0
QMA = Q["Close"].rolling(200, min_periods=200).mean()
UP = set(Q.index[((Q["Close"] > QMA) & (QDD > -0.10)).fillna(False).values])
YEARS = (Q.index[-1] - Q.index[0]).days / 365.25
print(f"정상 상승장으로 친 날 {len(UP)}일 ({len(UP)/len(Q)*100:.0f}%)")

HOLDS = [(60, "3개월"), (120, "6개월"), (250, "1년")]
WAITS = [(1, 3, "1~3일"), (3, 5, "3~5일"), (5, 10, "5~10일")]
DROPS = [(-0.04, -0.02, "2~4%"), (-0.06, -0.04, "4~6%"),
         (-0.10, -0.06, "6~10%"), (-0.15, -0.10, "10~15%")]
SPLIT = pd.Timestamp("2021-08-01")

PRE = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    PRE[t] = {
        "idx": df.index, "open": df["Open"].values, "high": df["High"].values,
        "close": df["Close"].values, "hi": hi.values,
        "nh": (df["High"] >= hi).values,
        "ret": {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0).values * 100
                for h, lab in HOLDS},
    }


def signals(p, w0, w1, d0, d1):
    """신고가 뒤 w0~w1거래일 안에 그 고점에서 d0~d1 눌린 첫 날. 신고가당 한 번."""
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
            if k >= w0:
                dr = cl[j] / peak - 1.0
                if d0 <= dr <= d1:
                    out.append(j)
                    fired = True
                    break
        i = (j if fired else i + 1)
    return out


def collect(w, dband, lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for j in signals(p, w[0], w[1], dband[0], dband[1]):
            dt = p["idx"][j]
            if dt not in UP:
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            v = r[j]
            if np.isfinite(v):
                out.append(v)
    return np.array(out)


def base(lab, half=None):
    out = []
    for t, p in PRE.items():
        r = p["ret"][lab]
        for i in range(251, len(p["idx"])):
            dt = p["idx"][i]
            if dt not in UP or not np.isfinite(p["hi"][i]):
                continue
            if half == "a" and dt >= SPLIT:
                continue
            if half == "b" and dt < SPLIT:
                continue
            if np.isfinite(r[i]):
                out.append(r[i])
    return np.array(out)


BASE = {lab: base(lab) for _h, lab in HOLDS}
print("\n기준선 — 정상 상승장 아무 날 아무 종목")
for _h, lab in HOLDS:
    b = BASE[lab]
    print(f"  {lab}: 가운데 {np.median(b):+.1f}% · 승률 {(b>0).mean()*100:.1f}% ({len(b):,}번)")

print("\n" + "=" * 108)
print("날짜 × 눌린 폭 (가운데 값 / 승률 / 1년에 몇 번)")
print("=" * 108)
print(f"  {'기다림':<8}{'눌린 폭':<9}{'1년에':>7}" + "".join(f"{l:>20}" for _h, l in HOLDS))
RESULT = {}
for w in WAITS:
    for db in DROPS:
        cells = []
        n_sig = None
        for _h, lab in HOLDS:
            v = collect(w, db, lab)
            if n_sig is None:
                n_sig = len(v)
            if len(v) >= 100:
                cells.append(f"{np.median(v):+7.1f}% {(v>0).mean()*100:5.1f}%")
                RESULT[(w[2], db[2], lab)] = (np.median(v), (v > 0).mean() * 100, len(v))
            else:
                cells.append(f"{'표본 부족':>20}")
        per_year = n_sig / len(data) / YEARS
        print(f"  {w[2]:<9}{db[2]:<10}{per_year:6.1f}" + "".join(f"{c:>20}" for c in cells))

print("\n" + "=" * 108)
print("교차 검증 — 앞 5년 / 뒤 5년 (6개월 보유 · 승률)")
print("=" * 108)
ba, bb = base("6개월", "a"), base("6개월", "b")
print(f"  기준선  앞 5년 {(ba>0).mean()*100:.1f}%  ·  뒤 5년 {(bb>0).mean()*100:.1f}%\n")
print(f"  {'기다림':<8}{'눌린 폭':<9}{'앞 5년':>16}{'뒤 5년':>16}{'판정':>18}")
for w in WAITS:
    for db in DROPS:
        a, b = collect(w, db, "6개월", "a"), collect(w, db, "6개월", "b")
        if len(a) < 50 or len(b) < 50:
            print(f"  {w[2]:<9}{db[2]:<10}{'표본 부족':>34}")
            continue
        wa = (a > 0).mean() * 100 - (ba > 0).mean() * 100
        wbb = (b > 0).mean() * 100 - (bb > 0).mean() * 100
        judge = "양쪽 다 기준선 위" if wa > 0 and wbb > 0 else (
            "양쪽 다 아래" if wa <= 0 and wbb <= 0 else "한쪽만")
        print(f"  {w[2]:<9}{db[2]:<10}{wa:+11.1f}%p{wbb:+15.1f}%p{judge:>20}")

pickle.dump(RESULT, open(S + r"\breakout_result.pkl", "wb"))
