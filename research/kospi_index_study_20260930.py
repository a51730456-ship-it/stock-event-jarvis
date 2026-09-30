"""코스피 지수 자체를 사서 들면 어땠나 · 언제 샀어야 했나 (1996-12 ~ 2026-09, 야후 ^KS11, 배당 빠진 지수).
1회성 측정. 앱 안 건드림. 2026-09-30 자비스10 논의 — "종목 말고 코스피를 사는 게 낫지 않나"(상하님).
자료: research/_data/kospi_yahoo_19961211_20260930.csv (야후 ^KS11 · 네이버와 겹친 2,996일 최대 차 0.58%).
"""
import pathlib

import numpy as np
import pandas as pd

DATA = pathlib.Path(__file__).resolve().parent / "_data" / "kospi_yahoo_19961211_20260930.csv"
y = pd.read_csv(DATA, header=[0, 1], index_col=0, parse_dates=True)
y.columns = [c[0] for c in y.columns]
c = y["Close"].dropna()
c = c[c > 0]
print(f"자료 {c.index[0].date()} ~ {c.index[-1].date()} · {len(c)}일 · {c.iloc[0]:.0f} → {c.iloc[-1]:.0f}")
yrs = (c.index[-1] - c.index[0]).days / 365.25
print(f"통째 해마다 {((c.iloc[-1]/c.iloc[0])**(1/yrs)-1)*100:.1f}% (배당 빼고)")

# A. 고점을 다시 넘기까지 걸린 시간 (물린 기간)
print("\n[A] 이전 고점을 다시 넘기까지 (1년 넘게 걸린 것)")
peak_val, peak_day = c.iloc[0], c.index[0]
bottom = None
for d, v in c.items():
    if v > peak_val:
        if (d - peak_day).days > 365:
            print(f"  {peak_day.date()} 고점 {peak_val:,.0f} → {d.date()} 다시 넘음 · {(d-peak_day).days/365.25:.1f}년 · 그사이 최저 {bottom[1]:,.0f}({(bottom[1]/peak_val-1)*100:+.0f}%)")
        peak_val, peak_day, bottom = v, d, None
    else:
        if bottom is None or v < bottom[1]:
            bottom = (d, v)
if bottom is not None:
    print(f"  {peak_day.date()} 고점 {peak_val:,.0f} → 아직 못 넘음")

# B. 아무 날 사서 N년 들면
print("\n[B] 아무 날 사서 들고 있으면 (배당 빼고)")
for yrs_h in (1, 3, 5, 10):
    h = 250 * yrs_h
    f = (c.shift(-h) / c - 1).dropna() * 100
    print(f"  {yrs_h:>2}년: 오른 확률 100번 중 {(f>0).mean()*100:3.0f}번 · 가운데 {f.median():+6.1f}% · 가장 나쁨 {f.min():+6.1f}% · ({len(f)}일)")

# 끝 날짜에 따라 얼마나 달라지나
for a, b in (("2007-10-31", "2024-12-30"), ("2011-04-29", "2024-12-30"), ("2014-05-19", "2024-12-30"), ("2014-05-19", "2026-08-07")):
    va, vb = c.asof(pd.Timestamp(a)), c.asof(pd.Timestamp(b))
    print(f"  {a} → {b}: {va:,.0f} → {vb:,.0f} ({(vb/va-1)*100:+.0f}%)")

# C. 다달이 같은 돈 넣기 (10년·5년)
print("\n[C] 다달이 같은 돈을 넣었다면 (매달 마지막 날 사고 기간 끝에 평가)")
m = c.resample("ME").last()
for n in (60, 120):
    res = []
    for i in range(0, len(m) - n):
        px = m.iloc[i:i + n]
        units = (1 / px).sum()
        res.append((units * m.iloc[i + n] / n - 1) * 100)
    res = np.array(res)
    print(f"  {n//12}년 넣기: 번 확률 100번 중 {(res>0).mean()*100:3.0f}번 · 가운데 {np.median(res):+6.1f}% · 가장 나쁨 {res.min():+6.1f}% · ({len(res)}가지 시작 달)")

# D. 200일선 — 다달이 한 번 본다 (달 마지막 날 위면 다음 달 들고, 아래면 현금·이자 0)
print("\n[D] 코스피 200일선 위일 때만 들기 (달 마지막 날 보고 다음 달 결정 · 현금 이자 0 · 한 번 바꿀 때 0.1%)")
sma = c.rolling(200).mean()
me = c.resample("ME").last()
above = (c > sma).resample("ME").last()
ret = me.pct_change().shift(-1)  # 다음 달 수익
df = pd.DataFrame({"ret": ret, "on": above}).dropna()
df = df[sma.resample("ME").last().reindex(df.index).notna()]
switch = df["on"].astype(int).diff().abs().fillna(0)
df["rule"] = np.where(df["on"], df["ret"], 0.0) - switch * 0.001


def stats(s):
    eq = (1 + s).cumprod()
    yrs_ = len(s) / 12
    dd = (eq / eq.cummax() - 1).min() * 100
    return (eq.iloc[-1] ** (1 / yrs_) - 1) * 100, dd, (eq.iloc[-1] - 1) * 100


for label, a, b in (("통째", None, None), ("1997~2006", "1997", "2006"), ("2007~2016", "2007", "2016"), ("2017~2026", "2017", "2026")):
    d = df.loc[a:b] if a else df
    h, hdd, htot = stats(d["ret"])
    r, rdd, rtot = stats(d["rule"])
    print(f"  {label:<10} 그냥 들기 해마다 {h:+5.1f}% (가장 크게 빠짐 {hdd:5.0f}%) · 선 위일 때만 {r:+5.1f}% ({rdd:5.0f}%) · 들고 있던 달 {d['on'].mean()*100:3.0f}% · 바꾼 횟수 {int(switch.loc[d.index].sum())}")

# 좋은 달·나쁜 달을 선이 얼마나 잡았나
top = df["ret"].nlargest(15)
bot = df["ret"].nsmallest(15)
print(f"  가장 좋은 15달 중 선 위였던 달 {int(df.loc[top.index,'on'].sum())} · 가장 나쁜 15달 중 선 위였던 달 {int(df.loc[bot.index,'on'].sum())}")

# E. 고점에서 얼마나 빠졌을 때 샀나
print("\n[E] 코스피가 그때까지 고점에서 얼마나 빠져 있던 날 샀나 → 1년·3년 뒤")
dd = (c / c.cummax() - 1) * 100
for lo, hi in ((0, -5), (-5, -10), (-10, -15), (-15, -20), (-20, -30), (-30, -100)):
    sel = (dd <= lo) & (dd > hi)
    out = [f"  {lo:>4}~{hi:>4}%  ({sel.sum():>4}일)"]
    for h in (250, 750):
        f = ((c.shift(-h) / c - 1) * 100)[sel].dropna()
        if len(f):
            out.append(f"{h//250}년 뒤 오름 {(f>0).mean()*100:3.0f}번 · 가운데 {f.median():+6.1f}%")
    print(" · ".join(out))
