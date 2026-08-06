"""표를 처음부터 다시 검증한다.

앞서 쓴 함수를 하나도 재사용하지 않는다. 자료도 새로 받고, 계산도 다른 방식
(반복문 대신 통째 밀어내기)으로 짠다. 두 방식이 같은 값을 내야 믿을 수 있다.
"""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

S = str(Path(__file__).parent / "_data")

print("=" * 96)
print("① 자료를 새로 받아 앞서 쓴 것과 같은지 본다")
print("=" * 96)
fresh = yf.download("QQQ", period="10y", interval="1d", auto_adjust=True, progress=False)
if isinstance(fresh.columns, pd.MultiIndex):
    fresh.columns = fresh.columns.droplevel(1)
fresh = fresh[["Open", "High", "Low", "Close", "Volume"]].dropna()
old = pickle.load(open(S + r"\us_adj2.pkl", "rb"))["QQQ"]
join = fresh.join(old, how="inner", lsuffix="_new", rsuffix="_old")
d_close = (join["Close_new"] - join["Close_old"]).abs().max()
d_open = (join["Open_new"] - join["Open_old"]).abs().max()
print(f"  겹치는 날 {len(join):,}일 · 종가 최대 차이 {d_close:.6f} · 시가 최대 차이 {d_open:.6f}")
print(f"  기간 {fresh.index[0].date()} ~ {fresh.index[-1].date()} · {len(fresh):,}일")
c = fresh["Close"]
yrs = (c.index[-1] - c.index[0]).days / 365.25
print(f"  QQQ 총수익 {(c.iat[-1]/c.iat[0]-1)*100:+.1f}% · 해마다 {((c.iat[-1]/c.iat[0])**(1/yrs)-1)*100:+.2f}%")

print("\n" + "=" * 96)
print("② 계산을 다른 방식으로 다시 — 통째 밀어내기(shift)")
print("=" * 96)
hi252 = fresh["High"].rolling(252, min_periods=252).max()
ddown = fresh["Close"] / hi252 - 1.0

GR = [(-0.06, 0.00, "-0~-6%"), (-0.12, -0.06, "-6~-12%"), (-0.18, -0.12, "-12~-18%"),
      (-0.24, -0.18, "-18~-24%"), (-0.30, -0.24, "-24~-30%"), (-2.00, -0.30, "-30% 아래")]
HOLDS = [(20, "1달"), (60, "3달"), (120, "6달"), (250, "1년")]

print(f"  {'등급':<12}{'날 비율':>9}" + "".join(f"{lab:>12}" for _h, lab in HOLDS))
rows = {}
for hold, lab in HOLDS:
    buy = fresh["Open"].shift(-1)                 # 다음날 시가에 산다
    sell = fresh["Close"].shift(-(1 + hold))      # hold거래일 뒤 종가에 판다
    rows[lab] = (sell / buy - 1.0) * 100

valid = ddown.notna()
line = f"  {'아무 날이나':<11}{'—':>10}"
for _h, lab in HOLDS:
    r = rows[lab][valid].dropna()
    line += f"{r.median():+11.1f}%"
print(line)
tot = int(valid.sum())
for lo, hi, nm in GR:
    sel = valid & (ddown > lo) & (ddown <= hi)
    line = f"  {nm:<12}{sel.sum()/tot*100:8.1f}%"
    for _h, lab in HOLDS:
        r = rows[lab][sel].dropna()
        line += f"{r.median():+11.1f}%" if len(r) >= 20 else f"{'—':>12}"
    print(line)

print("\n" + "=" * 96)
print("③ 앞서 낸 표와 한 칸씩 대조 (6달 · 가운데 값)")
print("=" * 96)
BEFORE = {"아무 날이나": 11.0, "-0~-6%": 10.0, "-6~-12%": 15.4, "-12~-18%": 18.5,
          "-18~-24%": 22.4, "-24~-30%": -0.6, "-30% 아래": 17.5}
r6 = rows["6달"]
now = {"아무 날이나": r6[valid].dropna().median()}
for lo, hi, nm in GR:
    sel = valid & (ddown > lo) & (ddown <= hi)
    now[nm] = r6[sel].dropna().median()
print(f"  {'등급':<12}{'앞서 낸 값':>12}{'다시 잰 값':>12}{'차이':>10}")
ok = True
for k in BEFORE:
    diff = now[k] - BEFORE[k]
    if abs(diff) > 0.15:
        ok = False
    print(f"  {k:<13}{BEFORE[k]:+11.1f}%{now[k]:+11.1f}%{diff:+9.2f}%p")
print(f"\n  → {'전부 일치한다' if ok else '어긋난 칸이 있다'}")

print("\n" + "=" * 96)
print("④ 당초 측정과 왜 다른가 — 세 판을 나란히 (6달 · 가운데 값)")
print("=" * 96)
raw_old = yf.download("QQQ", period="10y", interval="1d", auto_adjust=False, progress=False)
if isinstance(raw_old.columns, pd.MultiIndex):
    raw_old.columns = raw_old.columns.droplevel(1)
raw_old = raw_old[["Open", "High", "Low", "Close"]].dropna()
h2 = raw_old["High"].rolling(252, min_periods=252).max()
dd2 = raw_old["Close"] / h2 - 1.0
r2 = (raw_old["Close"].shift(-121) / raw_old["Open"].shift(-1) - 1.0) * 100
v2 = dd2.notna()
print(f"  {'등급':<12}{'배당 뺀 것(당초)':>18}{'배당 넣은 것(지금)':>20}{'차이':>10}")
for lo, hi, nm in GR:
    a = r2[v2 & (dd2 > lo) & (dd2 <= hi)].dropna()
    b = r6[valid & (ddown > lo) & (ddown <= hi)].dropna()
    if len(a) >= 20 and len(b) >= 20:
        print(f"  {nm:<13}{a.median():+17.1f}%{b.median():+19.1f}%{b.median()-a.median():+9.2f}%p")

print("\n" + "=" * 96)
print("⑤ 앞을 훔쳐보지 않았는지 — 신호일과 매수일이 겹치나")
print("=" * 96)
i = 300
print(f"  {fresh.index[i].date()} 신호 · 그날 종가 {fresh['Close'].iat[i]:.2f} · "
      f"고점 대비 {ddown.iat[i]*100:+.1f}%")
print(f"  {fresh.index[i+1].date()} 매수 · 시가 {fresh['Open'].iat[i+1]:.2f}")
print(f"  {fresh.index[i+121].date()} 매도 · 종가 {fresh['Close'].iat[i+121]:.2f}")
print(f"  손익 {(fresh['Close'].iat[i+121]/fresh['Open'].iat[i+1]-1)*100:+.2f}%  "
      f"· 표 계산값 {r6.iat[i]:+.2f}%")
print(f"  52주 고가는 그날까지만 본다: {hi252.iat[i]:.2f} = "
      f"{fresh['High'].iloc[i-251:i+1].max():.2f} (직접 계산)")
