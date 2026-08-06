"""테마가 **실제로 같이 움직였나**가 개수보다 나은가 (2026-08-06 사용자 지시).

지금 배점은 '그날 같은 그물에 걸린 같은 테마 종목 수'만 센다. 같이 올랐는지는 안 본다.
그래서 '같이 움직였나'를 두 가지로 재서 개수와 견준다.

  ① 개수                  — 지금 방식
  ② 테마 형제들의 최근 5일 수익률 **가운데 값** (나를 뺀 나머지)
  ③ 테마 형제들이 같은 방향으로 움직인 **비율** (5일 수익률 부호가 같은 비율)

    python research/theme_comove.py
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
              # 최근 5일 움직임 — '같이 움직였나'를 이 값으로 본다
              "ret5": ((close / close.shift(5) - 1.0) * 100).values,
              "pos": {x: i for i, x in enumerate(df.index)}}

# 테마별 종목 목록(자료가 있는 것만)
THEME_STOCKS = {}
for theme in US_THEMES:
    THEME_STOCKS[theme["name"]] = [s for s in theme["stocks"] if s in PRE]


def gather(days_set, match):
    out = []
    for day in sorted(days_set):
        picks = [(t, i) for t, p in PRE.items()
                 if (i := p["pos"].get(day)) is not None
                 and np.isfinite(p["dd"][i]) and match(p, i)]
        if not picks:
            continue
        cnt = {}
        for t, _i in picks:
            for nm in MEMBER.get(t, []):
                cnt[nm] = cnt.get(nm, 0) + 1
        # 테마마다 형제들의 5일 수익률을 미리 모은다(그날 그 테마 전체 종목)
        theme_ret5 = {}
        for name, members in THEME_STOCKS.items():
            vals = {}
            for s in members:
                j = PRE[s]["pos"].get(day)
                if j is not None and np.isfinite(PRE[s]["ret5"][j]):
                    vals[s] = float(PRE[s]["ret5"][j])
            theme_ret5[name] = vals
        for t, i in picks:
            p = PRE[t]
            r = p["ret"][i]
            if not np.isfinite(r):
                continue
            names = MEMBER.get(t, [])
            count = max(max((cnt.get(nm, 0) - 1 for nm in names), default=0), 0)
            # 가장 많이 같이 걸린 테마를 대표로 본다(배점이 쓰는 것과 같은 테마)
            lead = max(names, key=lambda nm: cnt.get(nm, 0), default=None)
            peers = dict(theme_ret5.get(lead, {})) if lead else {}
            mine = peers.pop(t, None)
            if peers:
                vals = np.array(list(peers.values()))
                peer_med = float(np.median(vals))
                same = (float(np.mean(vals > 0)) if mine is not None and mine > 0
                        else float(np.mean(vals < 0)) if mine is not None
                        else float("nan"))
            else:
                peer_med, same = float("nan"), float("nan")
            out.append({"ret": r, "date": p["idx"][i], "count": count,
                        "peer_med": peer_med, "same": same})
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
    print(f"  {'조건':<28}{'잰 횟수':>8}{'앞':>8}{'뒤':>8}  판정")

    def show(label, keep):
        sel = [x for x in rows if keep(x)]
        a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
        b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
        if len(a) < 50 or len(b) < 50:
            print(f"  {label:<29}{len(sel):>7,}   표본 부족")
            return
        da = (a > 0).mean() * 100 - fa
        db = (b > 0).mean() * 100 - fb
        mark = "양쪽 다 이김" if da > 0 and db > 0 else ("양쪽 다 짐" if da <= 0 and db <= 0
                                                        else "한쪽만")
        print(f"  {label:<29}{len(a)+len(b):>7,}{da:+8.1f}{db:+8.1f}  {mark}")

    ok = lambda x: np.isfinite(x["peer_med"])
    show("① 개수 3개 이상(지금)", lambda x: x["count"] >= 3)
    print()
    show("② 형제 5일 +3%↑ (같이 오름)", lambda x: ok(x) and x["peer_med"] >= 3)
    show("② 형제 5일 0~+3%", lambda x: ok(x) and 0 <= x["peer_med"] < 3)
    show("② 형제 5일 마이너스", lambda x: ok(x) and x["peer_med"] < 0)
    show("② 형제 5일 -3%↓ (같이 빠짐)", lambda x: ok(x) and x["peer_med"] <= -3)
    print()
    show("③ 같은 방향 70%↑", lambda x: np.isfinite(x["same"]) and x["same"] >= 0.7)
    show("③ 같은 방향 40% 미만", lambda x: np.isfinite(x["same"]) and x["same"] < 0.4)
    print()
    show("개수3↑ + 형제 같이 빠짐",
         lambda x: x["count"] >= 3 and ok(x) and x["peer_med"] < 0)
    show("개수3↑ + 형제 같이 오름",
         lambda x: x["count"] >= 3 and ok(x) and x["peer_med"] >= 3)


print(f"테마 명부 {len(PRE)}종목")
report("급락 후 반등장 (나스닥 -6~-12% · 종목 -20~-50%)",
       gather(CRASH, lambda p, i: -50.0 <= p["dd"][i] < -20.0), base_of(CRASH))
report("정상 상승장 (신고가 1~5일 전 · 눌림 4~15%)",
       gather(UP, lambda p, i: (np.isfinite(p["days"][i]) and 1 <= p["days"][i] <= 5
                                and -15.0 <= p["dd"][i] <= -4.0)), base_of(UP))
