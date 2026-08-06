"""테마가 붙어 있으면 달라지나 (2026-08-06 사용자 지적).

앞서 낙폭 구간을 잴 때 **테마를 아예 안 봤다**. 같은 테마 종목이 여럿 같이 걸리면
테마가 통째로 반등하며 같이 움직일 수 있다는 지적이다. 재본다.

종목 묶음은 자비스3 테마 명부(US_LARGE_CAP_UNIVERSE)를 쓴다 — 나스닥100으로는
테마에 든 종목이 32개뿐이라 테마를 볼 수 없다.

    python research/gap_band_theme.py
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
MARKET = set(QDD.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HOLD, LAB = 120, "6개월"

PRE = {}
for t, df in data.items():
    hi = df["High"].rolling(252, min_periods=252).max()
    # 화면이 순위에 쓰는 값들을 같이 만든다(테마 동반은 아래에서 날마다 센다).
    close = df["Close"]
    val = close * df.get("Volume", close * 0 + 1)     # 거래대금 근사
    above = (val > val.rolling(50).mean()).values
    streak, run = np.zeros(len(above), dtype=int), 0
    for i, f in enumerate(above):
        run = run + 1 if f else 0
        streak[i] = run
    PRE[t] = {"idx": df.index,
              "dd": ((df["Close"] / hi - 1.0) * 100).values,
              "ret": (df["Close"].shift(-(1 + HOLD)) / df["Open"].shift(-1) - 1.0).values * 100,
              "streak": streak,
              "gain11": ((close / close.shift(11) - 1.0) * 100).values,
              "ret60": ((close / close.shift(60) - 1.0) * 100).values,
              "pos": {x: i for i, x in enumerate(df.index)}}

BANDS = [(-15.0, -10.0, "10~15%"), (-20.0, -15.0, "15~20%"),
         (-30.0, -20.0, "20~30%"), (-50.0, -30.0, "30~50%")]

print(f"테마 명부 {len(PRE)}종목 · 나스닥이 -6~-12%였던 날 {len(MARKET)}일 · 6개월 보유")
print("=" * 92)

# 날마다 그 구간에 든 종목을 모으고, 같은 테마에서 몇 개나 같이 걸렸는지 센다
for lo, hi, name in BANDS:
    rows = []
    for day in sorted(MARKET):
        picks = []
        for t, p in PRE.items():
            i = p["pos"].get(day)
            if i is None or not np.isfinite(p["dd"][i]):
                continue
            if lo <= p["dd"][i] < hi:
                picks.append((t, i))
        if not picks:
            continue
        cnt = {}
        for t, _i in picks:
            for nm in MEMBER.get(t, []):
                cnt[nm] = cnt.get(nm, 0) + 1
        for t, i in picks:
            p = PRE[t]
            together = max([cnt.get(nm, 0) - 1 for nm in MEMBER.get(t, [])], default=0)
            r = p["ret"][i]
            if np.isfinite(r):
                rows.append({
                    "together": max(together, 0), "ret": r, "date": p["idx"][i],
                    "streak": int(p["streak"][i]),
                    "gain11": p["gain11"][i], "ret60": p["ret60"][i],
                })
    if not rows:
        continue
    allr = np.array([x["ret"] for x in rows])
    print(f"\n▶ 고점 대비 {name}  (잰 횟수 {len(rows):,})")
    print(f"    {'조건':<24}{'잰 횟수':>9}{'가운데':>10}{'승률':>9}{'앞 5년':>10}{'뒤 5년':>10}")
    print(f"    {'전체':<25}{len(allr):>8,}{np.median(allr):+9.1f}%"
          f"{(allr > 0).mean()*100:8.1f}%")

    def show(label, keep):
        sel = [x for x in rows if keep(x)]
        if len(sel) < 100:
            print(f"    {label:<25}{len(sel):>8,}   표본 부족")
            return
        v = np.array([x["ret"] for x in sel])
        a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
        b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
        aw = f"{(a > 0).mean()*100:9.1f}%" if len(a) >= 50 else f"{'—':>10}"
        bw = f"{(b > 0).mean()*100:9.1f}%" if len(b) >= 50 else f"{'—':>10}"
        print(f"    {label:<25}{len(v):>8,}{np.median(v):+9.1f}%"
              f"{(v > 0).mean()*100:8.1f}%{aw}{bw}")

    show("테마 동반 0개", lambda x: x["together"] == 0)
    show("테마 동반 1~2개", lambda x: 1 <= x["together"] <= 2)
    show("테마 동반 3개 이상", lambda x: x["together"] >= 3)
    show("거래대금 연속 0일", lambda x: x["streak"] == 0)
    show("거래대금 연속 4~10일", lambda x: 4 <= x["streak"] <= 10)
    show("거래대금 연속 11일↑", lambda x: x["streak"] >= 11)
    show("최근 11일 -5% 넘게 빠짐", lambda x: np.isfinite(x["gain11"]) and x["gain11"] < -5)
    show("최근 11일 +15% 넘게 오름", lambda x: np.isfinite(x["gain11"]) and x["gain11"] > 15)
    show("60일 상승폭 40%↑", lambda x: np.isfinite(x["ret60"]) and x["ret60"] >= 40)
    show("테마3개↑ + 연속11일↑", lambda x: x["together"] >= 3 and x["streak"] >= 11)

# 기준선 — 그날 아무 종목이나
base = []
for t, p in PRE.items():
    for i in range(252, len(p["idx"])):
        if p["idx"][i] in MARKET and np.isfinite(p["dd"][i]) and np.isfinite(p["ret"][i]):
            base.append((p["ret"][i], p["idx"][i]))
bv = np.array([r for r, _d in base])
ba = np.array([r for r, dt in base if dt < SPLIT])
bb = np.array([r for r, dt in base if dt >= SPLIT])
print(f"\n기준선 — 그날 아무 종목이나  {len(bv):,}번 · 가운데 {np.median(bv):+.1f}%"
      f" · 승률 {(bv > 0).mean()*100:.1f}%"
      f"  (앞 5년 {(ba > 0).mean()*100:.1f}% · 뒤 5년 {(bb > 0).mean()*100:.1f}%)")
