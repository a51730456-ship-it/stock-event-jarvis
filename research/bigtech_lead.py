"""시장이 회복될 때 빅테크10이 먼저 움직이나 (2026-08-06 사용자 물음).

빅테크10을 테마로 인정할지 정하려면, 이 10종목이 정말 앞서 도는지 봐야 한다.

재는 방법 — 나스닥이 고점에서 -6~-12%로 내려온 날(급락 그물이 켜지는 자리)을 기준으로
그 뒤 5·20·60거래일 수익률을 **빅테크10 vs 나머지 테마 종목**으로 갈라 견준다.
'먼저'인지 보려고 짧은 구간(5일)부터 본다.

    python research/bigtech_lead.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis3_data import US_LARGE_CAP_UNIVERSE, US_THEMES

BIG = set(next(t["stocks"] for t in US_THEMES if t["name"] == "빅테크10"))
MEMBER = {}
for theme in US_THEMES:
    for s in theme["stocks"]:
        MEMBER.setdefault(s, []).append(theme["name"])
OTHER = [s for s in US_LARGE_CAP_UNIVERSE if s in MEMBER and s not in BIG]

tick = list(US_LARGE_CAP_UNIVERSE) + ["QQQ"]
d = yf.download(tick, period="10y", interval="1d", auto_adjust=True,
                group_by="ticker", threads=8, progress=False)
data = {}
for t in tick:
    try:
        df = d[t].dropna(how="all")[["Open", "High", "Low", "Close"]].dropna()
    except Exception:
        continue
    if len(df) >= 400:
        data[t] = df
Q = data.pop("QQQ")
QHI = Q["High"].rolling(252, min_periods=252).max()
QDD = (Q["Close"] / QHI - 1.0) * 100
CRASH = set(Q.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HORIZONS = [(5, "5일"), (20, "20일"), (60, "60일")]

PRE = {}
for t, df in data.items():
    close = df["Close"]
    PRE[t] = {"pos": {x: i for i, x in enumerate(df.index)}, "idx": df.index,
              "fwd": {n: (close.shift(-n) / close - 1.0).values * 100
                      for n, _lab in HORIZONS}}


def collect(members, n, half=None):
    out = []
    for t in members:
        p = PRE.get(t)
        if p is None:
            continue
        fwd = p["fwd"][n]
        for day in CRASH:
            i = p["pos"].get(day)
            if i is None or not np.isfinite(fwd[i]):
                continue
            if half == "a" and day >= SPLIT:
                continue
            if half == "b" and day < SPLIT:
                continue
            out.append(fwd[i])
    return np.array(out)


print(f"나스닥이 -6~-12%였던 날 {len(CRASH)}일 · "
      f"빅테크10 {len([s for s in BIG if s in PRE])}종목 · "
      f"나머지 테마 {len([s for s in OTHER if s in PRE])}종목")
print("=" * 74)
print(f"  {'구간':<8}{'빅테크10 가운데':>16}{'오른 비율':>10}"
      f"{'나머지 가운데':>16}{'오른 비율':>10}")
for n, lab in HORIZONS:
    b, o = collect(BIG, n), collect(OTHER, n)
    print(f"  {lab:<9}{np.median(b):+13.2f}%{(b > 0).mean()*100:9.1f}%"
          f"{np.median(o):+15.2f}%{(o > 0).mean()*100:9.1f}%")

print("\n앞 5년 / 뒤 5년으로 갈라 (가운데 값)")
print(f"  {'구간':<8}{'빅테크10 앞':>13}{'뒤':>10}{'나머지 앞':>13}{'뒤':>10}")
for n, lab in HORIZONS:
    ba, bb = collect(BIG, n, "a"), collect(BIG, n, "b")
    oa, ob = collect(OTHER, n, "a"), collect(OTHER, n, "b")
    print(f"  {lab:<9}{np.median(ba):+12.2f}%{np.median(bb):+9.2f}%"
          f"{np.median(oa):+12.2f}%{np.median(ob):+9.2f}%")

# '먼저 움직이나' — 5일에서 앞서고 60일에는 따라잡히는지 본다
b5, o5 = collect(BIG, 5), collect(OTHER, 5)
b60, o60 = collect(BIG, 60), collect(OTHER, 60)
print(f"\n5일 차이  {np.median(b5) - np.median(o5):+.2f}%p"
      f"   60일 차이 {np.median(b60) - np.median(o60):+.2f}%p")
