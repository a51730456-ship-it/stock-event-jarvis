"""나눠 사기(33%씩 세 번) 검증.

계획 — 나스닥이 -12%에 닿으면 1/3 매수, 더 빠져 -18%에 닿으면 1/3 더,
        -24%에 닿으면 나머지 1/3. 종목은 고점에서 20~50% 빠진 것.

물음 셋
  ① 2·3차 매수가 실제로 몇 번이나 왔나 (안 오면 돈이 놀게 된다)
  ② 나눠 산 성적이 한 번에 산 것보다 나은가
  ③ -6~-12%에서 한 번에 사는 것과 견주면?
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
QDD = (Q["Close"] / Q["High"].rolling(252, min_periods=252).max() - 1.0).dropna()
HOLDS = [(60, "3개월"), (120, "6개월"), (250, "1년")]

STK = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    STK[t] = {"idx": df.index, "dd": (df["Close"] / hi - 1.0).values,
              "ret": {lab: (df["Close"].shift(-(1 + h)) / df["Open"].shift(-1) - 1.0).values * 100
                      for h, lab in HOLDS},
              "pos": {x: i for i, x in enumerate(df.index)}}

# ── 국면 나누기 — -12% 아래로 내려간 사건 ──────────────────────────
EP, armed, cur = [], True, None
for dt, v in QDD.items():
    if armed and v <= -0.12:
        cur = {"start": dt, "t1": dt, "t2": None, "t3": None, "min": v}
        armed = False
    elif cur is not None:
        cur["min"] = min(cur["min"], v)
        if cur["t2"] is None and v <= -0.18:
            cur["t2"] = dt
        if cur["t3"] is None and v <= -0.24:
            cur["t3"] = dt
        if v > -0.03:
            EP.append(cur)
            cur, armed = None, True
if cur is not None:
    EP.append(cur)

print("=" * 96)
print("① -12%에 닿은 사건과, 그 뒤 더 빠졌는지")
print("=" * 96)
print(f"  {'1차 -12%':<14}{'2차 -18%':<14}{'3차 -24%':<14}{'가장 깊었던 곳':>14}")
for e in EP:
    print(f"  {str(e['t1'].date()):<14}"
          f"{str(e['t2'].date()) if e['t2'] else '안 옴':<14}"
          f"{str(e['t3'].date()) if e['t3'] else '안 옴':<14}"
          f"{e['min']*100:>13.1f}%")
n2 = sum(1 for e in EP if e["t2"])
n3 = sum(1 for e in EP if e["t3"])
print(f"\n  -12% 사건 {len(EP)}번 중 → 2차 매수 {n2}번({n2/len(EP)*100:.0f}%) · "
      f"3차 매수 {n3}번({n3/len(EP)*100:.0f}%)")


def buy(day, lab):
    """그날 고점에서 20~50% 빠진 종목을 골고루 산 성적."""
    out = []
    for t, p in STK.items():
        i = p["pos"].get(day)
        if i is None or not np.isfinite(p["dd"][i]):
            continue
        if not (-0.50 <= p["dd"][i] < -0.20):
            continue
        r = p["ret"][lab][i]
        if np.isfinite(r):
            out.append(r)
    return np.array(out)


print("\n" + "=" * 96)
print("② 나눠 사기 vs 한 번에 사기 (각 차수를 산 날부터 재는 성적)")
print("=" * 96)
for _h, lab in HOLDS:
    rows = []
    for e in EP:
        parts, w = [], []
        for key, frac in (("t1", 1 / 3), ("t2", 1 / 3), ("t3", 1 / 3)):
            day = e[key]
            if day is None:
                continue
            v = buy(day, lab)
            if len(v):
                parts.append(np.mean(v))
                w.append(frac)
        if not parts:
            continue
        # 실제로 산 만큼만으로 평균 (안 온 차수는 현금)
        blended = float(np.average(parts, weights=w))
        allin = np.mean(buy(e["t1"], lab)) if len(buy(e["t1"], lab)) else np.nan
        rows.append((e["t1"].date(), len(parts), blended, allin))
    if not rows:
        continue
    b = np.array([r[2] for r in rows])
    a = np.array([r[3] for r in rows if np.isfinite(r[3])])
    print(f"\n▶ {lab} 보유")
    print(f"  {'1차 매수일':<13}{'몇 번 샀나':>10}{'나눠 사기':>12}{'한 번에':>12}")
    for dt, k, bl, al in rows:
        print(f"  {str(dt):<13}{k:>8}번{bl:>11.1f}%{al:>11.1f}%")
    print(f"  {'평균':<13}{'':>10}{b.mean():>11.1f}%{a.mean():>11.1f}%")

print("\n" + "=" * 96)
print("③ -6~-12%에서 한 번에 사는 것과 견주면 (같은 종목 조건)")
print("=" * 96)
# -6~-12% 첫 진입일
E6, armed = [], True
for dt, v in QDD.items():
    if armed and -0.12 < v <= -0.06:
        E6.append(dt)
        armed = False
    elif not armed and v > -0.03:
        armed = True
print(f"  -6~-12%에 처음 닿은 사건 {len(E6)}번")
for _h, lab in HOLDS:
    v6 = np.array([np.mean(buy(dt, lab)) for dt in E6 if len(buy(dt, lab))])
    v12 = np.array([np.mean(buy(e["t1"], lab)) for e in EP if len(buy(e["t1"], lab))])
    print(f"  {lab:<6} -6~-12%에서 사면 {v6.mean():+6.1f}% ({len(v6)}번)   "
          f"-12%에서 사면 {v12.mean():+6.1f}% ({len(v12)}번)")
