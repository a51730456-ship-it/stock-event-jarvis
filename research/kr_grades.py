"""한국도 미국과 같은 표를 만든다 — 코스피 낙폭 등급별 빈도와 성적."""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd

S = str(Path(__file__).parent / "_data")
KR = pickle.load(open(S + r"\kr_daily.pkl", "rb"))


def prep(df):
    c, h = df["Close"], df["High"]
    hi = h.rolling(252, min_periods=252).max()
    return pd.DataFrame({"open": df["Open"], "close": c, "high": h, "hi252": hi,
                         "dd": c / hi - 1.0}, index=df.index)


KS = prep(KR["kospi"])
STK = {c: prep(v["df"]) for c, v in KR["stocks"].items()}

GRADES = [(-0.06, 0.00, "-0~-6%"), (-0.12, -0.06, "-6~-12%"), (-0.18, -0.12, "-12~-18%"),
          (-0.24, -0.18, "-18~-24%"), (-0.30, -0.24, "-24~-30%"), (-2.00, -0.30, "-30% 아래")]
LEVELS = [-0.05, -0.08, -0.10, -0.12, -0.15, -0.18, -0.20, -0.24, -0.30]


def fwd(m, i, hold):
    b, e = i + 1, i + 1 + hold
    if e >= len(m):
        return None
    buy, sell = m["open"].iat[b], m["close"].iat[e]
    if not np.isfinite(buy) or not np.isfinite(sell) or buy <= 0:
        return None
    return sell / buy - 1.0


def stat(rs):
    if not rs:
        return None
    a = np.array(rs)
    return {"n": len(a), "med": float(np.median(a)) * 100, "win": float((a > 0).mean()) * 100}


dd = KS["dd"].dropna()
yrs = (dd.index[-1] - dd.index[0]).days / 365.25
print("=" * 92)
print(f"코스피 — 고점 대비 얼마나 자주 빠지나 ({len(dd):,}거래일 · {yrs:.1f}년)")
print("=" * 92)
for lo, hi, nm in GRADES:
    sel = dd[(dd > lo) & (dd <= hi)]
    print(f"  {nm:<12} {len(sel):5,}일  ({len(sel)/len(dd)*100:5.1f}%)")

print(f"\n  '적어도 이만큼 빠진' 일이 몇 번 왔나 (-3% 회복해야 다시 셈)")
for lv in LEVELS:
    ep, armed = 0, True
    for v in dd.values:
        if armed and v <= lv:
            ep += 1
            armed = False
        elif not armed and v > -0.03:
            armed = True
    every = yrs / ep if ep else float("inf")
    print(f"    {lv*100:+5.0f}% 아래로  {ep:2d}번   ≈ {every:4.1f}년에 한 번")

print("\n" + "=" * 92)
print("코스피가 그만큼 빠졌을 때 — 코스피 지수 자체를 산 경우")
print("=" * 92)
for hold in (20, 60, 120):
    lab = {20: "1달", 60: "3달", 120: "6달"}[hold]
    allr = [r for i in range(251, len(KS) - hold - 1)
            if np.isfinite(KS["dd"].iat[i]) and (r := fwd(KS, i, hold)) is not None]
    base = stat(allr)
    print(f"\n▶ {hold}거래일({lab})   아무 날이나 {base['n']:,}번 · 100번 중 {base['win']:.1f}번")
    for lo, hi, nm in GRADES:
        rs = [r for i in range(251, len(KS) - hold - 1)
              if np.isfinite(KS["dd"].iat[i]) and lo < KS["dd"].iat[i] <= hi
              and (r := fwd(KS, i, hold)) is not None]
        s = stat(rs)
        if s and s["n"] >= 20:
            print(f"  {nm:<12} {s['n']:5,}번  100번 중 {s['win']:5.1f}번  "
                  f"가운데 {s['med']:+6.2f}%  ({s['win']-base['win']:+5.1f}번)")
        else:
            print(f"  {nm:<12}     잰 횟수가 적어 못 씀")

print("\n" + "=" * 92)
print("같은 날 개별 종목을 산 경우 (한국 대형주 194종목)")
print("=" * 92)
KPOS = {d: i for i, d in enumerate(KS.index)}
for hold in (20, 60, 120):
    lab = {20: "1달", 60: "3달", 120: "6달"}[hold]
    buckets = {g[2]: [] for g in GRADES}
    allr = []
    for c, m in STK.items():
        for i in range(251, len(m) - hold - 1, 2):
            ki = KPOS.get(m.index[i])
            if ki is None or not np.isfinite(KS["dd"].iat[ki]) or not np.isfinite(m["hi252"].iat[i]):
                continue
            r = fwd(m, i, hold)
            if r is None:
                continue
            allr.append(r)
            v = KS["dd"].iat[ki]
            for lo, hi, nm in GRADES:
                if lo < v <= hi:
                    buckets[nm].append(r)
                    break
    base = stat(allr)
    print(f"\n▶ {hold}거래일({lab})   아무 날이나 {base['n']:,}번 · 100번 중 {base['win']:.1f}번")
    for _lo, _hi, nm in GRADES:
        s = stat(buckets[nm])
        if s and s["n"] >= 20:
            print(f"  {nm:<12} {s['n']:7,}번  100번 중 {s['win']:5.1f}번  "
                  f"가운데 {s['med']:+6.2f}%  ({s['win']-base['win']:+5.1f}번)")
        else:
            print(f"  {nm:<12}     잰 횟수가 적어 못 씀")

# 시기 반 가르기 (교차 검증)
print("\n" + "=" * 92)
print("교차 검증 — 시기를 반으로 갈라도 같은가 (코스피 지수 · 6달)")
print("=" * 92)
SPLIT = pd.Timestamp("2020-06-01")
for half, keep in (("앞쪽 2015~2020", lambda d: d < SPLIT), ("뒤쪽 2020~2026", lambda d: d >= SPLIT)):
    allr = [r for i in range(251, len(KS) - 121)
            if keep(KS.index[i]) and np.isfinite(KS["dd"].iat[i]) and (r := fwd(KS, i, 120)) is not None]
    base = stat(allr)
    cells = []
    for lo, hi, nm in GRADES:
        rs = [r for i in range(251, len(KS) - 121)
              if keep(KS.index[i]) and np.isfinite(KS["dd"].iat[i]) and lo < KS["dd"].iat[i] <= hi
              and (r := fwd(KS, i, 120)) is not None]
        s = stat(rs)
        cells.append(f"{nm} {s['win']:5.1f}번" if s and s["n"] >= 20 else f"{nm}   —  ")
    print(f"  {half}  기준 {base['win']:5.1f}번 | " + " | ".join(cells))
