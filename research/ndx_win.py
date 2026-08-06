"""표에 승률을 붙인다. 보유기간마다 승률이 얼마나 다른지도 같이 본다."""
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

GR = [(-0.06, 0.00, "-0~-6%"), (-0.12, -0.06, "-6~-12%"), (-0.18, -0.12, "-12~-18%"),
      (-0.24, -0.18, "-18~-24%"), (-0.30, -0.24, "-24~-30%"), (-2.00, -0.30, "-30% 아래")]
SB = [(-0.30, -0.20, "20~30%"), (-0.50, -0.30, "30~50%"), (-0.50, -0.20, "20~50% 합쳐")]
HOLDS = [(20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년")]

F = {}
for t, df in data.items():
    dd = df["Close"] / df["High"].rolling(252, min_periods=252).max() - 1.0
    r = {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0) * 100
         for h, lab in HOLDS}
    F[t] = (dd, r, QDD.reindex(df.index))


def grab(g, b, lab):
    out = []
    for t, (dd, r, q) in F.items():
        m = dd.notna() & q.notna() & (q > g[0]) & (q <= g[1]) & (dd >= b[0]) & (dd < b[1])
        v = r[lab][m].dropna()
        if len(v):
            out.append(v.values)
    return np.concatenate(out) if out else np.array([])


def grab_all(lab):
    out = []
    for t, (dd, r, q) in F.items():
        v = r[lab][dd.notna() & q.notna()].dropna()
        if len(v):
            out.append(v.values)
    return np.concatenate(out)


print("=" * 104)
print("승률 — 보유기간마다 다르다 (나스닥100 96종목 · 100번 중 이익 난 횟수)")
print("=" * 104)
print(f"  {'고점 대비':<12}{'종목 낙폭':<12}" + "".join(f"{l:>10}" for _h, l in HOLDS))
base = {lab: (grab_all(lab) > 0).mean() * 100 for _h, lab in HOLDS}
print(f"  {'아무 날이나':<11}{'20~50%':<12}" + "".join(f"{base[l]:9.1f}번" for _h, l in HOLDS))
print("  " + "-" * 100)
for lo, hi, nm in GR:
    for blo, bhi, bnm in SB:
        a = grab((lo, hi), (blo, bhi), "6개월")
        line = f"  {nm if bnm == SB[0][2] else '':<12}{bnm:<12}"
        for _h, lab in HOLDS:
            v = grab((lo, hi), (blo, bhi), lab)
            line += f"{(v > 0).mean()*100:9.1f}번" if len(v) >= 30 else f"{'—':>10}"
        print(line)
    print()

print("=" * 104)
print("표에 넣을 승률 — '20~50% 빠진 종목을 6개월 들었을 때'로 정한다")
print("=" * 104)
print(f"  {'고점 대비':<13}{'승률':>8}{'잰 횟수':>10}   기준(아무 날 20~50% 종목 6개월): "
      f"{(np.concatenate([grab(g[:2], (-0.50, -0.20), '6개월') for g in GR]) > 0).mean()*100:.1f}번")
for lo, hi, nm in GR:
    v = grab((lo, hi), (-0.50, -0.20), "6개월")
    print(f"  {nm:<14}{(v > 0).mean()*100:6.1f}번{len(v):>10,}")
