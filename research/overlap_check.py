"""배점 항목끼리 같은 것을 재고 있지 않나 (2026-08-06 사용자 지적).

낙폭 갈래(구덩이 깊이)와 최근 11일(방금 빠졌나)이 겹치면 한 가지를 두 번 세는 것이다.
테마 동반까지 셋을 서로 견준다.

  ① 항목끼리 얼마나 같이 움직이나(상관)
  ② 낙폭 칸을 고정해 놓고도 11일이 성적을 가르나 — 가르면 별개다
  ③ 11일을 고정해 놓고도 낙폭이 성적을 가르나

    python research/overlap_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis3_data import US_LARGE_CAP_UNIVERSE, US_THEMES

MEMBER = {}
for theme in US_THEMES:
    for s in theme["stocks"]:
        MEMBER.setdefault(s, []).append(theme["name"])

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
QDD = (Q["Close"] / Q["High"].rolling(252, min_periods=252).max() - 1.0) * 100
CRASH = set(QDD.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HOLD = 120

PRE = {}
for t, df in data.items():
    close = df["Close"]
    hi = df["High"].rolling(252, min_periods=252).max()
    PRE[t] = {"idx": df.index, "dd": ((close / hi - 1.0) * 100).values,
              "ret": (close.shift(-(1 + HOLD)) / df["Open"].shift(-1) - 1.0).values * 100,
              "gain11": ((close / close.shift(11) - 1.0) * 100).values,
              "pos": {x: i for i, x in enumerate(df.index)}}

rows = []
for day in sorted(CRASH):
    picks = [(t, i) for t, p in PRE.items()
             if (i := p["pos"].get(day)) is not None
             and np.isfinite(p["dd"][i]) and -50.0 <= p["dd"][i] < -20.0]
    cnt = {}
    for t, _i in picks:
        for nm in MEMBER.get(t, []):
            cnt[nm] = cnt.get(nm, 0) + 1
    for t, i in picks:
        p = PRE[t]
        if not (np.isfinite(p["ret"][i]) and np.isfinite(p["gain11"][i])):
            continue
        rows.append({"ret": p["ret"][i], "date": p["idx"][i], "dd": p["dd"][i],
                     "gain11": p["gain11"][i],
                     "count": max(max((cnt.get(nm, 0) - 1
                                       for nm in MEMBER.get(t, [])), default=0), 0)})

base = []
for t, p in PRE.items():
    for i in range(252, len(p["idx"])):
        if p["idx"][i] in CRASH and np.isfinite(p["dd"][i]) and np.isfinite(p["ret"][i]):
            base.append((p["ret"][i], p["idx"][i]))
ba = np.array([r for r, dt in base if dt < SPLIT])
bb = np.array([r for r, dt in base if dt >= SPLIT])
fa, fb = (ba > 0).mean() * 100, (bb > 0).mean() * 100

dd = np.array([x["dd"] for x in rows])
g11 = np.array([x["gain11"] for x in rows])
cnt = np.array([float(x["count"]) for x in rows])
print(f"급락 그물 {len(rows):,}개 · 기준선 앞 {fa:.1f}% / 뒤 {fb:.1f}%")
print("\n① 항목끼리 얼마나 같이 움직이나 (1에 가까울수록 같은 것을 잰다)")
print(f"  낙폭 vs 최근 11일   {np.corrcoef(dd, g11)[0, 1]:+.3f}")
print(f"  낙폭 vs 테마 동반   {np.corrcoef(dd, cnt)[0, 1]:+.3f}")
print(f"  최근 11일 vs 테마   {np.corrcoef(g11, cnt)[0, 1]:+.3f}")


def show(label, keep):
    sel = [x for x in rows if keep(x)]
    a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
    b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
    if len(a) < 50 or len(b) < 50:
        print(f"  {label:<30}{len(sel):>7,}   표본 부족")
        return
    da = (a > 0).mean() * 100 - fa
    db = (b > 0).mean() * 100 - fb
    mark = "양쪽 다 이김" if da > 0 and db > 0 else ("양쪽 다 짐" if da <= 0 and db <= 0
                                                    else "한쪽만")
    print(f"  {label:<31}{len(a)+len(b):>7,}{da:+8.1f}{db:+8.1f}  {mark}")


print("\n② 낙폭 칸을 고정하고 11일로 갈라 본다 (가르면 별개다)")
print(f"  {'조건':<30}{'잰 횟수':>8}{'앞':>8}{'뒤':>8}  판정")
for lo, hi, name in ((-30.0, -20.0, "20~30%"), (-50.0, -30.0, "30~50%")):
    band = lambda x, lo=lo, hi=hi: lo <= x["dd"] < hi
    show(f"{name} 전체", band)
    show(f"{name} + 11일 -5%↓", lambda x, b=band: b(x) and x["gain11"] < -5)
    show(f"{name} + 11일 +5%↑", lambda x, b=band: b(x) and x["gain11"] > 5)

print("\n③ 11일을 고정하고 낙폭으로 갈라 본다")
print(f"  {'조건':<30}{'잰 횟수':>8}{'앞':>8}{'뒤':>8}  판정")
deep = lambda x: -50.0 <= x["dd"] < -30.0
show("11일 -5%↓ + 낙폭 20~30%", lambda x: x["gain11"] < -5 and not deep(x))
show("11일 -5%↓ + 낙폭 30~50%", lambda x: x["gain11"] < -5 and deep(x))
