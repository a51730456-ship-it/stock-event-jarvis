"""테마 동반 40점이 **테마 크기** 때문에 나온 결과인가 (2026-08-06 사용자 지적).

지금 배점은 '그날 같은 그물에 걸린 같은 테마 종목 수(개수)'로 준다. 그런데 빅테크10은
10종목이라 4개가 걸리기 쉽고, 5종목짜리 테마에서 4개 걸리는 것과 무게가 다르다.

세 가지를 잰다.
  ① 개수(지금 방식)  — 3개 이상
  ② 비율(새 방식)    — 같이 걸린 수 ÷ 그 테마 종목 수
  ③ 테마 크기만      — 큰 테마 종목이라서 좋은 것인가

    python research/theme_size_bias.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis3_data import US_LARGE_CAP_UNIVERSE, US_THEMES

MEMBER, SIZE = {}, {}
for theme in US_THEMES:
    SIZE[theme["name"]] = len(theme["stocks"])
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
QHI = Q["High"].rolling(252, min_periods=252).max()
QDD = (Q["Close"] / QHI - 1.0) * 100
QMA = Q["Close"].rolling(200, min_periods=200).mean()
UP = set(Q.index[((Q["Close"] > QMA) & (QDD > -10.0)).fillna(False).values])
CRASH = set(Q.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HOLD = 120

PRE = {}
for t, df in data.items():
    close, high = df["Close"], df["High"]
    hi = high.rolling(252, min_periods=252).max()
    days = high.rolling(252, min_periods=252).apply(
        lambda w: len(w) - 1 - int(np.argmax(w)), raw=True).values
    PRE[t] = {"idx": df.index, "dd": ((close / hi - 1.0) * 100).values, "days": days,
              "ret": (close.shift(-(1 + HOLD)) / df["Open"].shift(-1) - 1.0).values * 100,
              "pos": {x: i for i, x in enumerate(df.index)},
              # 이 종목이 든 테마 중 가장 큰 것 — '큰 테마 종목인가'를 보는 값
              "big": max((SIZE[n] for n in MEMBER.get(t, [])), default=0)}


def gather(days_set, match):
    out = []
    for day in sorted(days_set):
        picks = [(t, i) for t, p in PRE.items()
                 if (i := p["pos"].get(day)) is not None
                 and np.isfinite(p["dd"][i]) and match(p, i)]
        cnt = {}
        for t, _i in picks:
            for nm in MEMBER.get(t, []):
                cnt[nm] = cnt.get(nm, 0) + 1
        for t, i in picks:
            p = PRE[t]
            r = p["ret"][i]
            if not np.isfinite(r):
                continue
            names = MEMBER.get(t, [])
            # 개수 = 나 말고 같이 걸린 수 · 비율 = 그 테마에서 걸린 비율
            count = max((cnt.get(nm, 0) - 1 for nm in names), default=0)
            ratio = max((cnt.get(nm, 0) / SIZE[nm] for nm in names), default=0.0)
            out.append({"ret": r, "date": p["idx"][i], "count": max(count, 0),
                        "ratio": ratio, "big": p["big"]})
    return out


def base_of(days_set):
    return [(p["ret"][i], p["idx"][i]) for p in PRE.values()
            for i in range(252, len(p["idx"]))
            if p["idx"][i] in days_set and np.isfinite(p["dd"][i])
            and np.isfinite(p["ret"][i])]


def report(title, rows, base):
    ba = np.array([r for r, dt in base if dt < SPLIT])
    bb = np.array([r for r, dt in base if dt >= SPLIT])
    fa, fb = (ba > 0).mean() * 100, (bb > 0).mean() * 100
    print("\n" + "=" * 78)
    print(f"{title} — 걸린 자리 {len(rows):,}개 · 기준선 앞 {fa:.1f}% / 뒤 {fb:.1f}%")
    print(f"  {'조건':<26}{'잰 횟수':>8}{'승률':>8}{'앞':>8}{'뒤':>8}  판정")

    def show(label, keep):
        sel = [x for x in rows if keep(x)]
        a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
        b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
        if len(a) < 50 or len(b) < 50:
            print(f"  {label:<27}{len(sel):>7,}   표본 부족")
            return
        v = np.array([x["ret"] for x in sel])
        da = (a > 0).mean() * 100 - fa
        db = (b > 0).mean() * 100 - fb
        mark = "양쪽 다 이김" if da > 0 and db > 0 else ("양쪽 다 짐" if da <= 0 and db <= 0
                                                        else "한쪽만")
        print(f"  {label:<27}{len(v):>7,}{(v > 0).mean()*100:7.1f}%"
              f"{da:+8.1f}{db:+8.1f}  {mark}")

    show("① 개수 3개 이상(지금)", lambda x: x["count"] >= 3)
    show("① 개수 1~2개", lambda x: 1 <= x["count"] <= 2)
    print()
    show("② 비율 30% 이상", lambda x: x["ratio"] >= 0.30)
    show("② 비율 50% 이상", lambda x: x["ratio"] >= 0.50)
    show("② 비율 30% 미만", lambda x: x["ratio"] < 0.30)
    print()
    show("③ 큰 테마(8종목↑) 종목", lambda x: x["big"] >= 8)
    show("③ 작은 테마(7종목↓) 종목", lambda x: x["big"] < 8)
    print()
    show("큰 테마 안에서 개수 3개↑", lambda x: x["big"] >= 8 and x["count"] >= 3)
    show("작은 테마 안에서 개수 3개↑", lambda x: x["big"] < 8 and x["count"] >= 3)
    show("큰 테마 안에서 비율 30%↑", lambda x: x["big"] >= 8 and x["ratio"] >= 0.30)
    show("작은 테마 안에서 비율 30%↑", lambda x: x["big"] < 8 and x["ratio"] >= 0.30)


print(f"테마 명부 {len(PRE)}종목 · 테마 크기 {min(SIZE.values())}~{max(SIZE.values())}종목")
report("급락 후 반등장 (나스닥 -6~-12% · 종목 -20~-50%)",
       gather(CRASH, lambda p, i: -50.0 <= p["dd"][i] < -20.0), base_of(CRASH))
report("정상 상승장 (신고가 1~5일 전 · 눌림 4~15%)",
       gather(UP, lambda p, i: (np.isfinite(p["days"][i]) and 1 <= p["days"][i] <= 5
                                and -15.0 <= p["dd"][i] <= -4.0)), base_of(UP))
