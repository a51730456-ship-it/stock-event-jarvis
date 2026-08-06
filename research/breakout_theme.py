"""상승장(신고가 눌림)도 테마·다른 조건으로 갈라 잰다 (2026-08-06 사용자 지시).

급락 갈래는 테마를 넣으니 그림이 달라졌다. 상승장도 같은 자로 재서 별점 기준을
낙폭·날짜로 할지 테마로 할지 정한다.

    python research/breakout_theme.py
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
        df = d[t].dropna(how="all")[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        continue
    if len(df) >= 400:
        data[t] = df
Q = data.pop("QQQ")
QHI = Q["High"].rolling(252, min_periods=252).max()
QDD = (Q["Close"] / QHI - 1.0) * 100
QMA = Q["Close"].rolling(200, min_periods=200).mean()
UP = set(Q.index[((Q["Close"] > QMA) & (QDD > -10.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HOLD = 120

PRE = {}
for t, df in data.items():
    close, high = df["Close"], df["High"]
    hi = high.rolling(252, min_periods=252).max()
    val = close * df["Volume"]
    above = (val > val.rolling(50).mean()).values
    streak, run = np.zeros(len(above), dtype=int), 0
    for i, f in enumerate(above):
        run = run + 1 if f else 0
        streak[i] = run
    # 52주 신고가가 며칠 전인가
    days = high.rolling(252, min_periods=252).apply(
        lambda w: len(w) - 1 - int(np.argmax(w)), raw=True).values
    PRE[t] = {"idx": df.index,
              "dd": ((close / hi - 1.0) * 100).values,
              "days": days,
              "ret": (close.shift(-(1 + HOLD)) / df["Open"].shift(-1) - 1.0).values * 100,
              "streak": streak,
              "gain11": ((close / close.shift(11) - 1.0) * 100).values,
              "ret60": ((close / close.shift(60) - 1.0) * 100).values,
              "pos": {x: i for i, x in enumerate(df.index)}}

# 그물 — 신고가 1~5일 전 · 고점에서 4~15% 눌림
rows = []
for day in sorted(UP):
    picks = []
    for t, p in PRE.items():
        i = p["pos"].get(day)
        if i is None or not np.isfinite(p["dd"][i]) or not np.isfinite(p["days"][i]):
            continue
        if 1 <= p["days"][i] <= 5 and -15.0 <= p["dd"][i] <= -4.0:
            picks.append((t, i))
    if not picks:
        continue
    cnt = {}
    for t, _i in picks:
        for nm in MEMBER.get(t, []):
            cnt[nm] = cnt.get(nm, 0) + 1
    for t, i in picks:
        p = PRE[t]
        r = p["ret"][i]
        if not np.isfinite(r):
            continue
        rows.append({
            "ret": r, "date": p["idx"][i], "dd": p["dd"][i], "days": int(p["days"][i]),
            "together": max(max([cnt.get(nm, 0) - 1 for nm in MEMBER.get(t, [])],
                                default=0), 0),
            "streak": int(p["streak"][i]),
            "gain11": p["gain11"][i], "ret60": p["ret60"][i],
        })

base = []
for t, p in PRE.items():
    for i in range(252, len(p["idx"])):
        if p["idx"][i] in UP and np.isfinite(p["dd"][i]) and np.isfinite(p["ret"][i]):
            base.append((p["ret"][i], p["idx"][i]))
bv = np.array([r for r, _d in base])
ba = np.array([r for r, dt in base if dt < SPLIT])
bb = np.array([r for r, dt in base if dt >= SPLIT])
print(f"테마 명부 {len(PRE)}종목 · 정상 상승장 {len(UP)}일 · 6개월 보유")
print(f"기준선 — 아무 날 아무 종목  {len(bv):,}번 · 가운데 {np.median(bv):+.1f}%"
      f" · 승률 {(bv > 0).mean()*100:.1f}%"
      f"  (앞 5년 {(ba > 0).mean()*100:.1f}% · 뒤 5년 {(bb > 0).mean()*100:.1f}%)")
print(f"그물에 걸린 자리 {len(rows):,}개")
print("=" * 92)
print(f"  {'조건':<24}{'잰 횟수':>9}{'가운데':>10}{'승률':>9}{'앞 5년':>10}{'뒤 5년':>10}")


def show(label, keep):
    sel = [x for x in rows if keep(x)]
    if len(sel) < 100:
        print(f"  {label:<25}{len(sel):>8,}   표본 부족")
        return
    v = np.array([x["ret"] for x in sel])
    a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
    b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
    aw = f"{(a > 0).mean()*100:9.1f}%" if len(a) >= 50 else f"{'—':>10}"
    bw = f"{(b > 0).mean()*100:9.1f}%" if len(b) >= 50 else f"{'—':>10}"
    print(f"  {label:<25}{len(v):>8,}{np.median(v):+9.1f}%{(v > 0).mean()*100:8.1f}%{aw}{bw}")


show("그물 전체", lambda x: True)
print()
show("눌림 10~15%", lambda x: x["dd"] <= -10)
show("눌림 4~10%", lambda x: x["dd"] > -10)
show("신고가 1~3일 전", lambda x: x["days"] <= 3)
show("신고가 4~5일 전", lambda x: x["days"] >= 4)
print()
show("테마 동반 0개", lambda x: x["together"] == 0)
show("테마 동반 1~2개", lambda x: 1 <= x["together"] <= 2)
show("테마 동반 3개 이상", lambda x: x["together"] >= 3)
print()
show("거래대금 연속 11일↑", lambda x: x["streak"] >= 11)
show("최근 11일 -5%↓", lambda x: np.isfinite(x["gain11"]) and x["gain11"] < -5)
show("60일 상승폭 40%↑", lambda x: np.isfinite(x["ret60"]) and x["ret60"] >= 40)
print()
show("테마3개↑ + 눌림10~15%", lambda x: x["together"] >= 3 and x["dd"] <= -10)
show("테마3개↑ + 60일40%↑",
     lambda x: x["together"] >= 3 and np.isfinite(x["ret60"]) and x["ret60"] >= 40)
