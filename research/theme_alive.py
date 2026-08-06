"""테마가 죽어가는지 되살아나는지 미리 알 수 있나 (2026-08-06 사용자 물음).

지금은 '같은 테마에서 몇 개가 같이 걸렸나'만 본다. 그건 **지금 모습**이지
**살아나는 중인지**는 말해 주지 않는다. 미리 알 수 있는 값이 있는지 재본다.

재는 값 넷 — 테마 대표 ETF로 본다(US_THEMES에 이미 들어 있다).
  ① ETF가 20일선 위인가        (추세가 살아 있나)
  ② ETF 최근 5일 수익률         (막 돌아섰나)
  ③ ETF 최근 20일 수익률        (한 달 흐름)
  ④ 같은 테마 동반 수가 늘고 있나 (5일 전보다 많아졌나)

    python research/theme_alive.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis3_data import US_LARGE_CAP_UNIVERSE, US_THEMES

MEMBER, THEME_ETF = {}, {}
for theme in US_THEMES:
    THEME_ETF[theme["name"]] = theme.get("etf")
    for s in theme["stocks"]:
        MEMBER.setdefault(s, []).append(theme["name"])

etfs = sorted({e for e in THEME_ETF.values() if e})
tick = list(US_LARGE_CAP_UNIVERSE) + etfs + ["QQQ"]
d = yf.download(tick, period="10y", interval="1d", auto_adjust=True,
                group_by="ticker", threads=8, progress=False)
data = {}
for t in tick:
    try:
        df = d[t].dropna(how="all")[["Open", "High", "Low", "Close"]].dropna()
    except Exception:
        continue
    if len(df) >= 300:
        data[t] = df
print(f"종목 {len(US_LARGE_CAP_UNIVERSE)}개 · 테마 ETF {len([e for e in etfs if e in data])}"
      f"/{len(etfs)}개 받음")

Q = data["QQQ"]
QHI = Q["High"].rolling(252, min_periods=252).max()
QDD = (Q["Close"] / QHI - 1.0) * 100
QMA = Q["Close"].rolling(200, min_periods=200).mean()
UP = set(Q.index[((Q["Close"] > QMA) & (QDD > -10.0)).fillna(False).values])
CRASH = set(Q.index[((QDD >= -12.0) & (QDD <= -6.0)).fillna(False).values])
SPLIT = pd.Timestamp("2021-08-01")
HOLD = 120

# 테마 ETF 상태 미리 계산
ETF = {}
for name, sym in THEME_ETF.items():
    df = data.get(sym)
    if df is None:
        continue
    c = df["Close"]
    ETF[name] = {
        "above20": (c > c.rolling(20).mean()).values,
        "ret5": ((c / c.shift(5) - 1.0) * 100).values,
        "ret20": ((c / c.shift(20) - 1.0) * 100).values,
        "pos": {x: i for i, x in enumerate(df.index)},
    }

PRE = {}
for t in US_LARGE_CAP_UNIVERSE:
    df = data.get(t)
    if df is None:
        continue
    c, h = df["Close"], df["High"]
    hi = h.rolling(252, min_periods=252).max()
    days = h.rolling(252, min_periods=252).apply(
        lambda w: len(w) - 1 - int(np.argmax(w)), raw=True).values
    PRE[t] = {"idx": df.index, "dd": ((c / hi - 1.0) * 100).values, "days": days,
              "ret": (c.shift(-(1 + HOLD)) / df["Open"].shift(-1) - 1.0).values * 100,
              "pos": {x: i for i, x in enumerate(df.index)}}


def gather(days_set, match):
    """그물에 걸린 자리를 모으고 테마 상태를 붙인다."""
    out = []
    day_list = sorted(days_set)
    # 날마다 동반 수를 세어 두고, 5일 전 것과 견주려고 기억한다
    history = {}
    for day in day_list:
        picks = [(t, i) for t, p in PRE.items()
                 if (i := p["pos"].get(day)) is not None
                 and np.isfinite(p["dd"][i]) and match(p, i)]
        cnt = {}
        for t, _i in picks:
            for nm in MEMBER.get(t, []):
                cnt[nm] = cnt.get(nm, 0) + 1
        history[day] = cnt
        for t, i in picks:
            p = PRE[t]
            r = p["ret"][i]
            if not np.isfinite(r):
                continue
            names = MEMBER.get(t, [])
            together = max(max([cnt.get(nm, 0) - 1 for nm in names], default=0), 0)
            lead = max(names, key=lambda nm: cnt.get(nm, 0), default=None)
            state = ETF.get(lead) if lead else None
            ei = state["pos"].get(day) if state else None
            out.append({
                "ret": r, "date": day, "together": together,
                "above20": bool(state["above20"][ei]) if ei is not None else None,
                "ret5": float(state["ret5"][ei]) if ei is not None else None,
                "ret20": float(state["ret20"][ei]) if ei is not None else None,
            })
    return out


def report(title, rows, base):
    bv = np.array([r for r, _d in base])
    ba = np.array([r for r, dt in base if dt < SPLIT])
    bb = np.array([r for r, dt in base if dt >= SPLIT])
    print("\n" + "=" * 92)
    print(f"{title} — 걸린 자리 {len(rows):,}개")
    print(f"기준선 승률 {(bv > 0).mean()*100:.1f}%"
          f"  (앞 5년 {(ba > 0).mean()*100:.1f}% · 뒤 5년 {(bb > 0).mean()*100:.1f}%)")
    print("=" * 92)
    print(f"  {'조건':<26}{'잰 횟수':>9}{'가운데':>10}{'승률':>9}{'앞 5년':>10}{'뒤 5년':>10}")

    def show(label, keep):
        sel = [x for x in rows if keep(x)]
        if len(sel) < 100:
            print(f"  {label:<27}{len(sel):>8,}   표본 부족")
            return
        v = np.array([x["ret"] for x in sel])
        a = np.array([x["ret"] for x in sel if x["date"] < SPLIT])
        b = np.array([x["ret"] for x in sel if x["date"] >= SPLIT])
        aw = f"{(a > 0).mean()*100:9.1f}%" if len(a) >= 50 else f"{'—':>10}"
        bw = f"{(b > 0).mean()*100:9.1f}%" if len(b) >= 50 else f"{'—':>10}"
        print(f"  {label:<27}{len(v):>8,}{np.median(v):+9.1f}%"
              f"{(v > 0).mean()*100:8.1f}%{aw}{bw}")

    show("그물 전체", lambda x: True)
    show("테마 동반 3개↑", lambda x: x["together"] >= 3)
    print()
    show("① ETF가 20일선 위", lambda x: x["above20"] is True)
    show("① ETF가 20일선 아래", lambda x: x["above20"] is False)
    print()
    show("② ETF 5일 +3%↑ (돌아섬)", lambda x: x["ret5"] is not None and x["ret5"] >= 3)
    show("② ETF 5일 0~+3%", lambda x: x["ret5"] is not None and 0 <= x["ret5"] < 3)
    show("② ETF 5일 마이너스", lambda x: x["ret5"] is not None and x["ret5"] < 0)
    print()
    show("③ ETF 20일 +5%↑", lambda x: x["ret20"] is not None and x["ret20"] >= 5)
    show("③ ETF 20일 마이너스", lambda x: x["ret20"] is not None and x["ret20"] < 0)
    print()
    show("테마3개↑ + ETF 20일선 위",
         lambda x: x["together"] >= 3 and x["above20"] is True)
    show("테마3개↑ + ETF 5일 +3%↑",
         lambda x: x["together"] >= 3 and x["ret5"] is not None and x["ret5"] >= 3)


def base_of(days_set):
    out = []
    for t, p in PRE.items():
        for i in range(252, len(p["idx"])):
            if p["idx"][i] in days_set and np.isfinite(p["dd"][i]) and np.isfinite(p["ret"][i]):
                out.append((p["ret"][i], p["idx"][i]))
    return out


report("급락 후 반등장 (나스닥 -6~-12% · 종목 -20~-50%)",
       gather(CRASH, lambda p, i: -50.0 <= p["dd"][i] < -20.0),
       base_of(CRASH))
report("정상 상승장 (신고가 1~5일 전 · 눌림 4~15%)",
       gather(UP, lambda p, i: (np.isfinite(p["days"][i]) and 1 <= p["days"][i] <= 5
                                and -15.0 <= p["dd"][i] <= -4.0)),
       base_of(UP))
