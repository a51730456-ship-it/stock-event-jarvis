"""테마를 여러 개 가진 종목이 유리한가 (2026-08-06 사용자 지적).

지금 배점은 그 종목이 속한 테마들 중 **가장 많이 걸린 테마 하나**만 본다(최댓값).
메타처럼 테마가 4개면 그중 하나만 3개 이상이어도 40점 만점이다. 나머지 3개가
0이어도 깎이지 않는다. 상하님 지적 — "테마 4개 중 2개만 오르면 깎는 게 정상 아니냐".

세 가지를 견준다.
  ① 최대   — 지금 방식 (가장 많이 걸린 테마 하나)
  ② 평균   — 그 종목의 모든 테마 동반 수의 평균
  ③ 덮은비율 — 그 종목의 테마 중 '3개 이상 걸린 테마'의 비율

    python research/theme_coverage.py
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
              "themes": len(MEMBER.get(t, []))}


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
            if not names:
                continue
            each = [max(cnt.get(nm, 0) - 1, 0) for nm in names]
            out.append({
                "ret": r, "date": p["idx"][i],
                "best": max(each),                       # ① 지금 방식
                "mean": float(np.mean(each)),            # ② 평균
                "cover": float(np.mean([e >= 3 for e in each])),  # ③ 3개↑ 테마 비율
                "themes": len(names),
            })
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
    print("\n" + "=" * 76)
    print(f"{title} — 걸린 자리 {len(rows):,}개 · 기준선 앞 {fa:.1f}% / 뒤 {fb:.1f}%")
    print(f"  {'조건':<30}{'잰 횟수':>8}{'앞':>8}{'뒤':>8}  판정")

    def show(label, keep):
        sel = [x for x in rows if keep(x)]
        a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
        b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
        if len(a) < 50 or len(b) < 50:
            print(f"  {label:<31}{len(sel):>7,}   표본 부족")
            return
        da = (a > 0).mean() * 100 - fa
        db = (b > 0).mean() * 100 - fb
        mark = "양쪽 다 이김" if da > 0 and db > 0 else ("양쪽 다 짐" if da <= 0 and db <= 0
                                                        else "한쪽만")
        print(f"  {label:<31}{len(a)+len(b):>7,}{da:+8.1f}{db:+8.1f}  {mark}")

    show("① 최대 3개↑ (지금 방식)", lambda x: x["best"] >= 3)
    print()
    show("② 평균 3개↑", lambda x: x["mean"] >= 3)
    show("② 평균 2개↑", lambda x: x["mean"] >= 2)
    print()
    show("③ 테마 전부가 3개↑ (100%)", lambda x: x["cover"] >= 0.999)
    show("③ 절반 이상 테마가 3개↑", lambda x: x["cover"] >= 0.5)
    show("③ 한 테마만 3개↑ (나머지 미달)",
         lambda x: x["best"] >= 3 and x["cover"] < 0.5)
    print()
    show("테마 1개짜리 종목 · 최대 3개↑",
         lambda x: x["themes"] == 1 and x["best"] >= 3)
    show("테마 2개↑ 종목 · 최대 3개↑",
         lambda x: x["themes"] >= 2 and x["best"] >= 3)


print(f"테마 명부 {len(PRE)}종목 · 한 종목이 든 테마 수 "
      f"{min(p['themes'] for p in PRE.values())}~{max(p['themes'] for p in PRE.values())}개")
report("급락 후 반등장 (나스닥 -6~-12% · 종목 -20~-50%)",
       gather(CRASH, lambda p, i: -50.0 <= p["dd"][i] < -20.0), base_of(CRASH))
report("정상 상승장 (신고가 1~5일 전 · 눌림 4~15%)",
       gather(UP, lambda p, i: (np.isfinite(p["days"][i]) and 1 <= p["days"][i] <= 5
                                and -15.0 <= p["dd"][i] <= -4.0)), base_of(UP))
