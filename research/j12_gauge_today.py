"""나스닥 고점 대비 숫자를 화면마다 그대로 돌려 본다 (2026-10-27 상하님 「막대의 지금 고점 대비와 급락 후 반등장 설명이 다른 이유 · 어느 게 맞냐」).

화면이 부르는 함수를 그대로 부르고, 막대 밑 QQQ 줄은 같은 식(1년치 종가 ÷ 1년 최고가)으로 새로 받아 잰다.
"""
from __future__ import annotations

import os
import sys

import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jarvis3_data as j3  # noqa: E402
import jarvis12_crash as c12  # noqa: E402

ixic = j3.get_nasdaq_drawdown()
print("① 막대 큰 숫자(나스닥 종합 IXIC · 1년 최고 종가 대비):", {k: ixic.get(k) for k in ("drawdown_pct", "state", "high", "as_of", "high_date", "last")})
ref = c12.reference()
print("② 급락 후 반등장 설명(QQQ · 1년 최고가(고가) 대비 · 2년치로 잼):",
      {k: ref.get(k) for k in ("peak_date", "reference_date", "reference_drop", "today_drop", "as_of", "recovered_on")})
frame = yf.download("QQQ", period="1y", interval="1d", auto_adjust=False, progress=False)
close, high = frame["Close"].squeeze().dropna(), frame["High"].squeeze().dropna()
print("③ 막대 밑 QQQ 줄 식(1년치 마지막 종가 ÷ 1년 최고가):", round((float(close.iloc[-1]) / float(high.max()) - 1) * 100, 2),
      "· 마지막 날", close.index[-1].date(), "· 최고가 날", high.idxmax().date(), "· 받은 날 수", len(close))
info = c12.episodes()
frame2 = info.get("frame")
c2 = frame2["Close"].astype(float)
h52 = frame2["High"].astype(float).rolling(252, min_periods=252).max()
drop = (c2 / h52 - 1) * 100
last = [e for e in info["episodes"]][-1]
seg = drop[(drop.index.date >= __import__("datetime").date.fromisoformat(last["start"]))]
print("④ 이번 하락(QQQ) — 시작", last["start"], "· 가장 깊은 날", last["reference"], f"{last['reference_drop']:.2f}%",
      "· 지금", f"{float(drop.dropna().iloc[-1]):.2f}%", "· 회복", last["recovered_on"])
print("   최근 10장 QQQ 낙폭:", [f"{d.date()} {v:.1f}" for d, v in drop.dropna().tail(10).items()])
old = j3.crash_reference_day()
print("⑤ 자비스3 급락 기준(QQQ · 최근 30장):", {k: old.get(k) for k in ("reference_date", "reference_drop", "today_drop")})
