"""논문에 나온 한국 기준들을 두세 달 보유로 다시 잰다 (2026-09-30, 자비스10 연구용 · 상장폐지 포함).

기준마다 그날 울타리 안 종목을 다섯 무리로 나눠(1=값 큰 쪽), 무리마다
  오른 확률 · 같은 기간 코스피 이긴 확률 · 가운데 수익 을 낸다. 앞 절반(2015-07~2020-12)·뒤 절반(2021-01~)도 따로.
사는 때 다음 날 시가 · 파는 때 N일 뒤 종가(그 전에 폐지되면 마지막 거래 가격).
울타리: 20일 평균 거래대금 10억↑ · 그날 거래 있음 · 250거래일 이상 주가 있음.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_baseline_full_20260930 import forward, load  # noqa: E402

STEP = 5
SPLIT = pd.Timestamp("2021-01-01")


def factors(px):
    close, vol = px["close"], px["volume"]
    high = pd.read_parquet(pathlib.Path(__file__).resolve().parent / "_data/wide_full/high.parquet")
    ret = close.pct_change(fill_method=None)
    value = close * vol / 1e8
    return {
        "52주 고가에 가까움(종가/52주 최고가)": close / high.rolling(250, min_periods=240).max(),
        "6개월 상승률": close / close.shift(120) - 1,
        "12개월 상승률(최근 1달 뺌)": close.shift(20) / close.shift(250) - 1,
        "최근 1달 상승률": close / close.shift(20) - 1,
        "최근 1달 하루 최대 상승(복권 같은 종목)": ret.rolling(20, min_periods=15).max(),
        "60일 흔들림(하루 등락 표준편차)": ret.rolling(60, min_periods=50).std(),
        "거래대금 급증(5일/60일)": value.rolling(5).mean() / value.rolling(60, min_periods=40).mean(),
        "거래대금 크기(60일 평균)": value.rolling(60, min_periods=40).mean(),
        "200일선 위 거리(종가/200일선)": close / close.rolling(200, min_periods=190).mean(),
    }


def main() -> None:
    px, kospi, meta = load()
    close = px["close"]
    value20 = (close * px["volume"]).rolling(20, min_periods=10).mean() / 1e8
    history = close.notna().cumsum() >= 250
    uni = (value20 >= 10) & (px["volume"] > 0) & history
    k = kospi["Close"]
    k_above = (k > k.rolling(200).mean()).to_numpy()
    facs = factors(px)
    for hold in (40, 60):
        fwd, kf = forward(px, kospi, hold)
        F, KF = fwd.to_numpy(), kf.to_numpy()
        print(f"\n######## {hold}거래일 보유 ########")
        for name, fac in facs.items():
            A = fac.to_numpy()
            U = uni.to_numpy()
            res = {q: {"up": [], "beat": [], "med": [], "med_a": [], "med_b": [], "on": []} for q in range(5)}
            for row in range(260, len(close) - hold - 1, STEP):
                sel = U[row] & ~np.isnan(A[row]) & ~np.isnan(F[row])
                if sel.sum() < 100 or np.isnan(KF[row]):
                    continue
                a, f = A[row][sel], F[row][sel]
                ranks = pd.Series(a).rank(pct=True, ascending=False).to_numpy()
                q = np.minimum((ranks * 5).astype(int), 4)  # 0 = 값 큰 무리
                for g in range(5):
                    fg = f[q == g]
                    r = res[g]
                    r["up"].append((fg > 0).mean() * 100)
                    r["beat"].append((fg > KF[row]).mean() * 100)
                    med = np.median(fg)
                    r["med"].append(med)
                    (r["med_a"] if close.index[row] < SPLIT else r["med_b"]).append(med)
                    if k_above[row]:
                        r["on"].append(med)
            print(f"\n  [{name}]  (1 = 값 큰 무리)")
            for g in range(5):
                r = res[g]
                print(f"    {g+1}무리 오름 {np.mean(r['up']):4.1f} · 코스피 이김 {np.mean(r['beat']):4.1f} · 가운데 {np.median(r['med']):+5.1f}% "
                      f"(앞 {np.median(r['med_a']):+5.1f} · 뒤 {np.median(r['med_b']):+5.1f} · 코스피 200일선 위일 때 {np.median(r['on']):+5.1f})")


if __name__ == "__main__":
    main()
