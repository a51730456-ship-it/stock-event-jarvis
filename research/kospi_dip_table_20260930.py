"""코스피판 「하락률대비 상승수익률」 표 + '기다렸다 사기'가 '다달이 사기'보다 나은가 (2026-09-30, 1회성).

표 모양은 미국테마 설명서의 엑셀 사진(assets/us_method_drawdown.png)을 따른다 —
  줄: 코스피 고점 대비 하락률 −6~−12 · −12~−18 · −18~−24 · −24~−30 · −30 아래
  칸: 얼마나 자주 오나(사건수) · 3개월(60일)·6개월(120일)·1년(250일) 뒤 코스피 수익(오른 비율)
사건: 새 고점을 찍은 뒤 그 구간에 **처음 들어간 날** 종가에 산다(한 번의 하락에 구간마다 한 번씩).
자료: research/_data/kospi_yahoo_19961211_20260930.csv (배당 뺌).
"""
import pathlib

import numpy as np
import pandas as pd

DATA = pathlib.Path(__file__).resolve().parent / "_data" / "kospi_yahoo_19961211_20260930.csv"
y = pd.read_csv(DATA, header=[0, 1], index_col=0, parse_dates=True)
y.columns = [c[0] for c in y.columns]
c = y["Close"].dropna()
c = c[c > 0]
BANDS = ((-6, -12), (-12, -18), (-18, -24), (-24, -30), (-30, -100))
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"), (500, "2년"), (750, "3년"))

peak = c.cummax()
dd = (c / peak - 1) * 100
cycle = (c >= peak).cumsum()          # 새 고점마다 번호가 바뀐다
years = (c.index[-1] - c.index[0]).days / 365.25

print(f"코스피 {c.index[0].date()} ~ {c.index[-1].date()} ({years:.1f}년) · 배당 뺌\n")
# 견줄 줄 — 아무 날이나 샀다면 (2026-09-30 상하님이 표만 보고 "코스피도 사지 말라는 것 같다"고 하셔서 넣음)
base = []
for h, label in HOLDS:
    r = (c.shift(-h) / c - 1).dropna() * 100
    base.append(f"{label} 평균 {r.mean():+5.1f}% ({(r > 0).mean() * 100:.0f}번/100)")
print("[기준] 아무 날이나 샀다면 · " + " · ".join(base) + "\n")
print("[표] 새 고점 뒤 그 구간에 처음 들어간 날 샀다면 → 코스피 수익 (오른 사건 수 / 사건 수)")
for hi, lo in BANDS:
    inside = (dd <= hi) & (dd > lo)
    first = inside & ~inside.groupby(cycle).shift(1, fill_value=False).astype(bool)
    # 같은 하락(cycle) 안에서 처음만
    first = inside & (inside.groupby(cycle).cumsum() == 1)
    days = c.index[first]
    parts = [f"  {hi:>4}~{lo if lo > -100 else '':>4}%  사건 {len(days):>2}번 ({years/len(days) if len(days) else 0:.1f}년에 한 번)"]
    for h, label in HOLDS:
        rets = []
        for d in days:
            i = c.index.get_loc(d)
            if i + h < len(c):
                rets.append((c.iloc[i + h] / c.iloc[i] - 1) * 100)
        rets = np.array(rets)
        if len(rets):
            parts.append(f"{label} 평균 {rets.mean():+5.1f}% · 가운데 {np.median(rets):+5.1f}% ({(rets>0).sum()}/{len(rets)})")
    print(" · ".join(parts))
    print("        사건 날:", ", ".join(str(d.date()) for d in days))

# ── 기다렸다 사기 vs 다달이 사기 ────────────────────────────────────────────
print("\n[비교] 매달 같은 돈(1)을 모은다. 10년 뒤 가진 돈 (넣은 돈 120 기준 · 현금 이자 0 / 연 3%)")
m_close = c.resample("ME").last()
m_dd = dd.resample("ME").min()          # 그 달 안에 가장 깊었던 하락
m_low_px = c.resample("ME").min()


def run(start, n, rule, rate):
    cash = units = 0.0
    for i in range(start, start + n):
        cash = cash * (1 + rate / 12) + 1.0
        if rule is None:                              # 다달이 바로 산다
            units += cash / m_close.iloc[i]
            cash = 0.0
        elif m_dd.iloc[i] <= rule:                    # 그 달에 코스피가 문턱 아래로 내려간 적이 있으면 그 달 말 종가에 다 산다
            units += cash / m_close.iloc[i]
            cash = 0.0
    return units * m_close.iloc[start + n] + cash


for rate in (0.0, 0.03):
    print(f"  현금 이자 연 {rate*100:.0f}%")
    for rule, label in ((None, "다달이 바로 사기"), (-10, "−10% 아래일 때만 사기"), (-15, "−15% 아래일 때만"),
                        (-20, "−20% 아래일 때만"), (-30, "−30% 아래일 때만")):
        out = np.array([run(s, 120, rule, rate) for s in range(0, len(m_close) - 120)])
        print(f"    {label:<18} 10년 뒤 가운데 {np.median(out):6.1f} · 가장 나쁨 {out.min():6.1f} · 가장 좋음 {out.max():6.1f}")
    base = np.array([run(s, 120, None, rate) for s in range(0, len(m_close) - 120)])
    for rule in (-10, -15, -20, -30):
        alt = np.array([run(s, 120, rule, rate) for s in range(0, len(m_close) - 120)])
        print(f"    −{-rule}% 기다리기가 다달이보다 많았던 시작 달: {(alt > base).mean()*100:4.1f}% ({len(base)}가지)")
