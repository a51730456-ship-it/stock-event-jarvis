"""표를 채우고, 각 줄이 얼마나 검증된 것인지도 같이 낸다.

검증은 셋으로 본다.
  ① 잰 횟수      — 표본이 몇 개인가
  ② 서로 다른 사건 수 — 사실은 몇 번의 사건인가 (이게 진짜 한계다)
  ③ 앞뒤 5년 갈라 — 시기를 갈라도 같은 방향인가
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
print(f"나스닥100 {len(data)}종목 · {Q.index[0].date()} ~ {Q.index[-1].date()}")

GR = [(-0.06, 0.00, "-0~-6%"), (-0.12, -0.06, "-6~-12%"), (-0.18, -0.12, "-12~-18%"),
      (-0.24, -0.18, "-18~-24%"), (-0.30, -0.24, "-24~-30%"), (-2.00, -0.30, "-30% 아래")]
SB = [(-0.30, -0.20, "20~30%"), (-0.50, -0.30, "30~50%")]
HOLDS = [(20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년")]
SPLIT = pd.Timestamp("2021-08-01")

F = {}
for t, df in data.items():
    dd = df["Close"] / df["High"].rolling(252, min_periods=252).max() - 1.0
    r = {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0) * 100
         for h, lab in HOLDS}
    F[t] = (dd, r, QDD.reindex(df.index))


def grab(g, b, lab, half=None):
    out = []
    for t, (dd, r, q) in F.items():
        m = dd.notna() & q.notna() & (q > g[0]) & (q <= g[1]) & (dd >= b[0]) & (dd < b[1])
        if half == "a":
            m &= dd.index < SPLIT
        elif half == "b":
            m &= dd.index >= SPLIT
        v = r[lab][m].dropna()
        if len(v):
            out.append(v.values)
    return np.concatenate(out) if out else np.array([])


def episodes(lo, hi):
    """그 등급에 들어간 서로 다른 사건 수. -3% 안으로 회복해야 다시 센다."""
    n, armed = 0, True
    for v in QDD.dropna().values:
        if armed and lo < v <= hi:
            n += 1
            armed = False
        elif not armed and v > -0.03:
            armed = True
    return n


print("\n" + "=" * 112)
print("표 — 나스닥100 96종목 · 배당 포함 · 가운데 값")
print("=" * 112)
hdr = f"  {'고점 대비':<11}{'자주 오나':<13}" + "".join(f"{l:>9}" for _h, l in HOLDS) * 2
print(hdr)
FREQ = {"-0~-6%": "날의 67%", "-6~-12%": "7개월에 한 번", "-12~-18%": "2.2년에 한 번",
        "-18~-24%": "2.2년에 한 번", "-24~-30%": "4.5년에 한 번", "-30% 아래": "9년에 한 번"}
rows = {}
for lo, hi, nm in GR:
    line = f"  {nm:<12}{FREQ[nm]:<14}"
    rows[nm] = {}
    for blo, bhi, bnm in SB:
        for _h, lab in HOLDS:
            a = grab((lo, hi), (blo, bhi), lab)
            rows[nm][(bnm, lab)] = a
            line += f"{np.median(a):+8.1f}%" if len(a) >= 30 else f"{'—':>9}"
    print(line)

print("\n" + "=" * 112)
print("얼마나 검증된 것인가")
print("=" * 112)
print(f"  {'고점 대비':<12}{'사건 수':>8}{'잰 횟수(20~30/30~50)':>24}"
      f"{'앞 5년 → 뒤 5년 (30~50%·6개월)':>34}{'판정':>12}")
for lo, hi, nm in GR:
    ep = episodes(lo, hi)
    n1 = len(rows[nm][("20~30%", "6개월")])
    n2 = len(rows[nm][("30~50%", "6개월")])
    a = grab((lo, hi), (-0.50, -0.30), "6개월", "a")
    b = grab((lo, hi), (-0.50, -0.30), "6개월", "b")
    ma = np.median(a) if len(a) >= 30 else None
    mb = np.median(b) if len(b) >= 30 else None
    if ma is None or mb is None:
        judge, cell = "한쪽 자료 없음", f"{'—':>34}"
    else:
        same = (ma > 0) == (mb > 0) and min(ma, mb) > 0
        judge = "양쪽 다 이익" if same else "한쪽이 무너짐"
        cell = f"{ma:+14.1f}% →{mb:+9.1f}%".rjust(34)
    print(f"  {nm:<13}{ep:>7}번{f'{n1:,} / {n2:,}':>24}{cell}{judge:>14}")

print("\n  ※ '사건 수'가 진짜 한계다. 잰 횟수가 2천 번이어도 사건이 두 번이면 두 번을 잰 것이다.")
