"""더 파기 ⑤ — 한국 외국인·기관 '동반 매수'가 정말 거꾸로인가.

앱과 같은 판정(jarvis4_data._day_flow_mark)을 쓴다. 그날 거래대금의 0.05% 미만은
보합으로 보고, 외국인과 기관을 **합치지 않고** 둘 다 순매수인 날만 '동반'으로 센다.
"""
import pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\jangs_tjkt17a\Documents\stock_event_jarvis")
from jarvis4_data import _day_flow_mark

S = str(Path(__file__).parent / "_data")
KR = pickle.load(open(S + r"\kr_daily.pkl", "rb"))
FLOW = pickle.load(open(S + r"\kr_flow.pkl", "rb"))

print(f"수급을 받은 종목 {len(FLOW)}개")


def prep(df):
    c, h = df["Close"], df["High"]
    hi = h.rolling(252, min_periods=252).max()
    return pd.DataFrame({
        "open": df["Open"], "close": c, "high": h, "hi252": hi,
        "from_high": c / hi - 1.0, "is_new_high": h >= hi,
    }, index=df.index)


KM = {c: prep(v["df"]) for c, v in KR["stocks"].items()}
KK = prep(KR["kospi"])
CR = {d for d, v in ((KK["from_high"] <= -0.10) & (KK["close"].diff() > 0) &
                     (KK["close"].shift(1).diff() < 0)).fillna(False).items() if v}
ma200 = KK["close"].rolling(200, min_periods=200).mean()
UP = {d for d, v in ((KK["close"] > ma200) & (KK["from_high"] > -0.10)).fillna(False).items() if v}

# 수급을 날짜 순 배열로 바꾸고 '동반 매수' 표식을 미리 매긴다
MARKS = {}
for code, rows in FLOW.items():
    if not rows:
        continue
    recs = []
    for ds, row in rows.items():
        try:
            d = pd.Timestamp(ds.replace(".", "-"))
        except Exception:
            continue
        recs.append((d, _day_flow_mark(row), row))
    recs.sort()
    MARKS[code] = {"dates": [r[0] for r in recs],
                   "mark": [r[1] for r in recs],
                   "row": [r[2] for r in recs]}
print(f"날짜로 정리된 종목 {len(MARKS)}개")
ex = max(MARKS, key=lambda c: len(MARKS[c]["dates"]))
print(f"가장 긴 것 {ex}: {MARKS[ex]['dates'][0].date()} ~ {MARKS[ex]['dates'][-1].date()} "
      f"({len(MARKS[ex]['dates'])}일)")


def both_buy_5(code, day):
    """그날까지의 최근 5거래일 중 외국인·기관이 둘 다 순매수한 날 수(0~5)."""
    m = MARKS.get(code)
    if not m:
        return None
    i = np.searchsorted(m["dates"], day, side="right") - 1
    if i < 4 or m["dates"][i] != day:
        return None
    return sum(1 for k in range(i - 4, i + 1) if m["mark"][k] == "both_buy")


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


def show(nm, s, base=None, w=22):
    if s is None or s["n"] < 30:
        return f"  {nm:<{w}}     표본 부족" + (f" ({s['n']}건)" if s else "")
    mk = ""
    if base:
        mk = "   ← 기준 " + ("위" if s["win"] > base["win"] else "아래")
    return f"  {nm:<{w}} {s['n']:>6,}건  가운데 {s['med']:+6.2f}%  100번 중 {s['win']:5.1f}번{mk}"


def breakout_sigs(m):
    out, n = [], len(m)
    nh, cl, hg, h2 = m["is_new_high"].values, m["close"].values, m["high"].values, m["hi252"].values
    i = 251
    while i < n:
        if not (np.isfinite(h2[i]) and nh[i]):
            i += 1
            continue
        peak, fired, j = hg[i], False, i
        for k in range(1, 6):
            j = i + k
            if j >= n or nh[j]:
                break
            peak = max(peak, hg[j])
            if k >= 3 and -0.06 <= cl[j] / peak - 1.0 <= -0.04:
                out.append(j)
                fired = True
                break
        i = (j if fired else i + 1)
    return out


print("\n" + "=" * 100)
print("⑧ 급락 후 반등장 낙폭(-30~-50%) — 외국인·기관 동반 5일이 갈리는가")
print("=" * 100)
for hold in (20, 60):
    rows = []
    for code, m in KM.items():
        if code not in MARKS:
            continue
        fh = m["from_high"].values
        for i in range(251, len(m)):
            d = m.index[i]
            if d not in CR or not np.isfinite(fh[i]) or not (-0.50 <= fh[i] < -0.30):
                continue
            b = both_buy_5(code, d)
            if b is None:
                continue
            r = fwd(m, i, hold)
            if r is not None:
                rows.append((b, r))
    base = stat([r for _b, r in rows])
    print(f"\n▶ {hold}거래일 보유")
    print(show("갈래 전체(기준)", base))
    for k in range(6):
        print(show(f"동반 {k}일", stat([r for b, r in rows if b == k]), base))
    print(show("동반 3일 이상", stat([r for b, r in rows if b >= 3]), base))

print("\n" + "=" * 100)
print("⑨ 상승장 신고가 눌림 — 같은 값이 여기서는 갈리는가")
print("=" * 100)
for hold in (60, 120):
    rows = []
    for code, m in KM.items():
        if code not in MARKS:
            continue
        for j in breakout_sigs(m):
            d = m.index[j]
            if d not in UP:
                continue
            b = both_buy_5(code, d)
            if b is None:
                continue
            r = fwd(m, j, hold)
            if r is not None:
                rows.append((b, r))
    base = stat([r for _b, r in rows])
    print(f"\n▶ {hold}거래일 보유")
    print(show("갈래 전체(기준)", base))
    for lo, hi, nm in ((0, 1, "동반 0일"), (1, 3, "동반 1~2일"), (3, 6, "동반 3일 이상")):
        print(show(nm, stat([r for b, r in rows if lo <= b < hi]), base))

print("\n" + "=" * 100)
print("⑩ 아무 날이나 — 동반 매수가 그 자체로 뜻이 있는가 (표본 가장 큼)")
print("=" * 100)
for hold in (20, 60):
    rows = []
    for code, m in KM.items():
        if code not in MARKS:
            continue
        mk = MARKS[code]
        for i in range(251, len(m) - hold - 1, 2):
            d = m.index[i]
            b = both_buy_5(code, d)
            if b is None:
                continue
            r = fwd(m, i, hold)
            if r is not None:
                rows.append((b, r))
    base = stat([r for _b, r in rows])
    print(f"\n▶ {hold}거래일 보유")
    print(show("전체(기준)", base))
    for k in range(6):
        print(show(f"동반 {k}일", stat([r for b, r in rows if b == k]), base))
