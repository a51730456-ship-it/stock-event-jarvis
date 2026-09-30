"""자비스10 후보 규칙을 두세 달(40·60거래일) 보유로 코스피와 견준다 (2026-09-30 · 상장폐지 포함).

잰 것 (규칙마다)
  종목 하나씩: 오른 확률 · 코스피 이긴 확률 · 가운데 수익
  그날 목록을 똑같이 나눠 샀다면(묶음): 코스피를 이긴 날의 비율 · 묶음 평균 수익 · 같은 날 코스피 평균
  앞 절반(~2020) · 뒤 절반(2021~) 묶음 평균도 따로
빼기(개잡주 거르기) — kr_factor_quintiles_20260930 에서 가장 나쁜 무리였던 것:
  60일 흔들림 상위 40% · 최근 1달 하루 최대 상승 상위 40% · 최근 1달 상승률 상위 20% · 거래대금 급증 상위 20%
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_baseline_full_20260930 import forward, load  # noqa: E402

W = pathlib.Path(__file__).resolve().parent / "_data" / "wide_full"
SPLIT = pd.Timestamp("2021-01-01")


def pct_rank(df: pd.DataFrame, uni: pd.DataFrame) -> pd.DataFrame:
    return df.where(uni).rank(axis=1, pct=True, ascending=False)  # 0에 가까울수록 값 큼


def main() -> None:
    px, kospi, meta = load()
    close, vol = px["close"], px["volume"]
    high = pd.read_parquet(W / "high.parquet")
    ret = close.pct_change(fill_method=None)
    value = close * vol / 1e8
    value20 = value.rolling(20, min_periods=10).mean()
    history = close.notna().cumsum() >= 250
    base = (value20 >= 10) & (vol > 0) & history
    big = (value20 >= 50) & (vol > 0) & history

    volat = ret.rolling(60, min_periods=50).std()
    max20 = ret.rolling(20, min_periods=15).max()
    r20 = close / close.shift(20) - 1
    surge = value.rolling(5).mean() / value.rolling(60, min_periods=40).mean()
    bad = ((pct_rank(volat, base) <= 0.4) | (pct_rank(max20, base) <= 0.4)
           | (pct_rank(r20, base) <= 0.2) | (pct_rank(surge, base) <= 0.2))
    clean = base & ~bad

    hi250 = high.rolling(250, min_periods=240).max()
    near_hi = close / hi250
    near_rank = pct_rank(near_hi, base)
    # 신고가 눌림 — 지금 한국테마 상승장 그물: 52주 신고가 3~10거래일 뒤 · 고가 대비 −4~−6% · 50억↑
    new_high = high >= hi250
    days_since = new_high.astype(float).replace(0, np.nan)
    days_since = days_since.where(days_since.isna(), 0)
    last_hi_pos = pd.DataFrame(np.where(new_high, np.arange(len(close))[:, None], np.nan),
                               index=close.index, columns=close.columns).ffill()
    since = np.arange(len(close))[:, None] - last_hi_pos
    pull = close / hi250 - 1
    pullback = big & (since >= 3) & (since <= 10) & (pull <= -0.04) & (pull >= -0.06)
    pullback_wide = base & (since >= 3) & (since <= 20) & (pull <= -0.04) & (pull >= -0.15)

    k = kospi["Close"]
    k_dd = k / k.cummax() - 1
    k_above = (k > k.rolling(200).mean())
    kospi_low = pd.Series(k_dd.to_numpy() <= -0.15, index=k.index)
    stock_dd = close / hi250 - 1
    crash = big & (stock_dd <= -0.40) & (stock_dd >= -0.60)

    gate_on = pd.DataFrame(np.repeat(k_above.to_numpy()[:, None], close.shape[1], 1), index=close.index, columns=close.columns)
    gate_low = pd.DataFrame(np.repeat(kospi_low.to_numpy()[:, None], close.shape[1], 1), index=close.index, columns=close.columns)

    value_rank = pct_rank(value.rolling(60, min_periods=40).mean(), base)
    gate_low20 = pd.DataFrame(np.repeat((k_dd.to_numpy() <= -0.20)[:, None], close.shape[1], 1),
                              index=close.index, columns=close.columns)
    rules = [
        ("아무 종목 (10억↑)", base),
        ("빼기만 통과 (10억↑)", clean),
        ("빼기 통과 + 거래대금 상위 10% (큰 종목)", clean & (value_rank <= 0.1)),
        ("52주 고가 가까움 상위 20%", base & (near_rank <= 0.2)),
        ("빼기 통과 + 52주 고가 가까움 상위 20%", clean & (near_rank <= 0.2)),
        ("지금 상승장 그물 (신고가 3~10일 · −4~−6% · 50억↑)", pullback),
        ("  └ 지금 상승장 그물 + 빼기 통과", pullback & clean),
        ("넓힌 눌림 (신고가 3~20일 · −4~−15% · 10억↑)", pullback_wide),
        ("  └ 넓힌 눌림 + 빼기 통과", pullback_wide & clean),
        ("  └ 넓힌 눌림 + 빼기 통과 + 코스피 200일선 위", pullback_wide & clean & gate_on),
        ("코스피 −15%↓ 인 날 · 아무 종목 (10억↑)", base & gate_low),
        ("코스피 −15%↓ 인 날 · 종목 −40~−60% · 50억↑", crash & gate_low),
        ("  └ 코스피 −15%↓ · 종목 −40~−60% + 빼기 통과", crash & gate_low & clean),
        ("코스피 −20%↓ 인 날 · 종목 −40~−60% · 50억↑", crash & gate_low20),
        ("  └ 코스피 −20%↓ · 종목 −40~−60% + 빼기 통과", crash & gate_low20 & clean),
    ]
    for hold in (40, 60):
        fwd, kf = forward(px, kospi, hold)
        F, KF = fwd.to_numpy(), kf.to_numpy()
        idx = close.index
        print(f"\n######## {hold}거래일 보유 ########")
        # 코스피 자체
        kk = KF[260:len(idx) - hold - 1]
        kk = kk[~np.isnan(kk)]
        print(f"  (참고) 코스피 아무 날: 오름 {(kk>0).mean()*100:4.1f}번 · 평균 {kk.mean():+5.1f}% · 가운데 {np.median(kk):+5.1f}%")
        for name, mask in rules:
            M = mask.fillna(False).to_numpy()
            ups = beats = cnt = 0
            meds, port, kos, pbeat, pa, pb, days = [], [], [], [], [], [], 0
            for row in range(260, len(idx) - hold - 1, 1 if "코스피 −" in name else 5):
                sel = M[row] & np.isfinite(F[row])
                if sel.sum() == 0 or np.isnan(KF[row]):
                    continue
                f = F[row][sel]
                cnt += len(f)
                ups += (f > 0).sum()
                beats += (f > KF[row]).sum()
                meds.extend(f.tolist())
                pm = f.mean()
                port.append(pm)
                kos.append(KF[row])
                pbeat.append(pm > KF[row])
                (pa if idx[row] < SPLIT else pb).append(pm - KF[row])
                days += 1
            if cnt == 0:
                print(f"  {name}: 없음")
                continue
            print(f"  {name}\n      종목 {cnt:,}건 · 오름 {ups/cnt*100:4.1f}번 · 코스피 이김 {beats/cnt*100:4.1f}번 · 가운데 {np.median(meds):+5.1f}%"
                  f"  ‖ 목록 {days}날 · 묶음이 코스피 이긴 날 {np.mean(pbeat)*100:4.1f}% · 묶음 평균 {np.mean(port):+5.1f}% vs 코스피 {np.mean(kos):+5.1f}%"
                  f" · 코스피보다 (앞 {np.mean(pa) if pa else float('nan'):+5.1f} · 뒤 {np.mean(pb) if pb else float('nan'):+5.1f})")


if __name__ == "__main__":
    main()
