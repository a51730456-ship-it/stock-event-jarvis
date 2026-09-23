"""J8 EOD research engine. No network, Streamlit, orders or database writes.

Existing J3 pure score helpers are read-only comparators; all J8 choices live here.
Scores describe rules, never probabilities. Universe is a dated, frozen roster.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "J8-20260923.1"
ROOT = Path(__file__).resolve().parent
UNIVERSE = json.loads((ROOT / "data/jarvis8/universe.json").read_text(encoding="utf-8"))
THEMES = UNIVERSE["themes"]
TICKERS = tuple(UNIVERSE["tickers"])
MEMBERS = {s: [t["name"] for t in THEMES if s in t["stocks"]] for s in TICKERS}
FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def clean(frame, as_of):
    if frame is None or not set(FIELDS).issubset(frame.columns):
        return pd.DataFrame(columns=FIELDS)
    f = frame[FIELDS].copy()
    f.index = pd.to_datetime(f.index).tz_localize(None).normalize()
    f = f.loc[~f.index.duplicated(keep="last")].sort_index().loc[:pd.Timestamp(as_of)]
    return f.apply(pd.to_numeric, errors="coerce").dropna(how="all")


def quality(frame, as_of, minimum=252):
    """Do not hide missing bars by filling or silently dropping invalid prices."""
    if frame.empty:
        return "시세 없음"
    if frame.index[-1] != pd.Timestamp(as_of):
        return "기준일 시세 누락"
    if len(frame) < minimum:
        return f"이력 부족 ({len(frame)}/{minimum}일)"
    recent = frame.tail(252)
    if not np.isfinite(recent.to_numpy(dtype=float)).all():
        return "OHLCV 결측"
    if (recent[FIELDS[:4]] <= 0).any().any():
        return "0 이하 가격"
    bad = ((recent.High < recent[["Open", "Close", "Low"]].max(axis=1)) |
           (recent.Low > recent[["Open", "Close", "High"]].min(axis=1)))
    if bad.any():
        return "고가·저가 모순"
    if (recent.Volume.tail(20) <= 0).any():
        return "최근 20일 거래량 0 또는 음수"
    if recent.Close.pct_change(fill_method=None).abs().gt(.8).any():
        return "하루 80% 초과 변동: 기업행사·가격 확인 필요"
    return ""


def reference(qqq):
    drop = (qqq.Close / qqq.High.rolling(252, min_periods=252).max() - 1) * 100
    recent = drop.dropna().tail(30)
    inside = recent[recent.between(-100, -6)]
    return {"armed": not inside.empty,
            "date": inside.idxmin().date().isoformat() if not inside.empty else None,
            "drop": float(inside.min()) if not inside.empty else None,
            "today_drop": float(recent.iloc[-1]) if len(recent) else None}


def build(frames, as_of, ixic=None):
    """One immutable completed-session bundle; future rows are cut before metrics."""
    import jarvis3_data as j3
    import jarvis8_momentum
    import us_swing_selector as swing

    day = pd.Timestamp(as_of).normalize()
    data = {s: clean(f, day) for s, f in frames.items()}
    for benchmark in ("SPY", "QQQ"):
        error = quality(data.get(benchmark, pd.DataFrame()), day)
        if error:
            raise ValueError(f"{benchmark}: {error}")
    # Independent 12-1 return ranking; the older J8 momentum below divides by
    # volatility and remains unchanged as a distinct, unvalidated experiment.
    try:
        independent_momentum = jarvis8_momentum.select(data, day, TICKERS)
    except ValueError as exc:
        # A shorter provider history can disable this 253-session study without
        # hiding the other independent J8 views that need only 252 sessions.
        independent_momentum = {"ok": False, "error": str(exc), "as_of": day.date().isoformat(),
                                "strategy_id": "J8_MOMENTUM_12_1", "top5": [], "rows": []}
    excluded = {s: quality(data.get(s, pd.DataFrame()), day) for s in TICKERS}
    prices = {s: data[s] for s in TICKERS if not excluded[s]}
    if len(prices) < 30:
        raise ValueError(f"검증 가능한 종목 {len(prices)}개: 순위 계산에 필요한 최소 30개 미달")
    metrics = {s: j3._series_metrics_uncached(f) for s, f in prices.items()}
    spy = j3._series_metrics_uncached(data["SPY"])
    themes = []
    for t in THEMES:
        mm = [metrics[s] for s in t["stocks"] if s in metrics]
        n = len(mm)
        row = {"name": t["name"], "count": n, "total": len(t["stocks"]),
               "coverage": n / len(t["stocks"]), "etf": t["etf"]}
        if n >= 3 and row["coverage"] >= .8:
            row.update(strength_60=float(np.mean([m["ret60"] - spy["ret60"] for m in mm])),
                       strength_120=float(np.mean([m["ret120"] - spy["ret120"] for m in mm])),
                       strong_members=float(np.mean([m["ret60"] > spy["ret60"] and m["ret120"] > spy["ret120"] for m in mm])*100),
                       ret60=float(np.mean([m["ret60"] for m in mm])),
                       ret120=float(np.mean([m["ret120"] for m in mm])))
            themes.append(row)
    for k, weight in [("strength_120", 35), ("strength_60", 30), ("strong_members", 25)]:
        j3._general_rank_points(themes, k, weight)
    for row in themes:
        row["score"] = round(sum(row[k + "_score"] for k in ("strength_120", "strength_60", "strong_members")), 1)
    themes.sort(key=lambda r: (-r["score"], r["name"]))

    ref = reference(data["QQQ"])
    crash = []
    for s, m in metrics.items():
        if not ref["armed"]:
            continue
        historic = prices[s].loc[:ref["date"]]
        # J8 requires a complete reference history; unlike J3 no current-price fallback.
        if len(historic) < 252:
            continue
        then_drop = (historic.Close.iloc[-1] / historic.High.tail(252).max() - 1) * 100
        if -50 <= then_drop < -20:
            crash.append({"ticker": s, "themes": MEMBERS[s], "metrics": m,
                          "reference_drop": float(then_drop),
                          "since_reference": float((m["current"] / historic.Close.iloc[-1]-1)*100)})
    j3._attach_crash_volatility(crash)
    j3._attach_theme_together(crash, MEMBERS)
    j3._attach_theme_rank(crash, MEMBERS, metrics, prefix="theme_above150",
                          derive=j3._above_sma150, top_n=j3.CRASH_ABOVE150_TOP_N)
    j3._attach_theme_rank(crash, MEMBERS, metrics, prefix="theme_ret120",
                          metric_key="ret120", top_n=j3.CRASH_RET120_TOP_N)
    for r in crash:
        old = j3.crash_rebound_score(r)
        r["baseline_score"] = old["score"]
        r["score"] = round(old["score"] - old["parts"][0][1], 1)
        r["parts"] = old["parts"][1:]
        r["state"] = "기준일 이후 상승: 추격 여부 확인" if r["since_reference"] > 10 else "기준일 후보 · 반등 확인 필요"
    # Matched-date top-K audit on 2026-09-14 rejected recovery-only superiority.
    # Preserve baseline ordering; expose 60 points as a diagnostic, not a winner.
    crash.sort(key=lambda r: (-r["baseline_score"], r["ticker"]))

    history = clean(ixic, day)
    # ATH state needs long history, not a rolling two-year replacement.
    index_ok = (len(history) >= 3000 and history.index[-1] == day and
                not history.Close.isna().any() and (history.Close > 0).all())
    rise = swing.scan_eod(prices, history, MEMBERS,
             universe_records=[{"ticker": s, "asset_type": "COMMON_STOCK"} for s in prices],
             universe_mode="LEGACY_RESEARCH_200", as_of=day,
             config={"universe": {"include_adr": True}}) if index_ok else {
                 "ok": False, "error": "Nasdaq 장기 이력 부족 또는 기준일 불일치: 상승장 판정 보류",
                 "primary_rows": [], "watch_rows": [], "market": {}}

    # A transparent alternative: 12m momentum excluding the latest 21 sessions,
    # divided by trailing daily volatility. This J8 variant has NOT been validated.
    momentum = []
    for s, f in prices.items():
        if len(f) < 274:
            continue
        m = metrics[s]
        ret = (f.Close.iloc[-22] / f.Close.iloc[-253] - 1) * 100
        vol = f.Close.pct_change(fill_method=None).tail(252).std() * np.sqrt(252) * 100
        if vol and m["current"] > m["sma200"] and data["QQQ"].Close.iloc[-1] > data["QQQ"].Close.tail(200).mean():
            momentum.append({"ticker": s, "themes": MEMBERS[s], "momentum": float(ret),
                             "risk_adjusted": float(ret / vol), "metrics": m})
    momentum.sort(key=lambda r: (-r["risk_adjusted"], r["ticker"]))
    reversal = []
    for s, m in metrics.items():
        # Leave-self-out peers, de-duplicated across overlapping themes.
        peers = {p for t in THEMES if t["name"] in MEMBERS[s] for p in t["stocks"]
                 if p != s and p in metrics}
        if len(peers) < 4 or m["ret20"] >= 0 or m["avg_dollar_volume"] < 20_000_000:
            continue
        peer_return = float(np.mean([metrics[p]["ret20"] for p in peers]))
        residual = m["ret20"] - peer_return
        if residual < 0:
            reversal.append({"ticker": s, "themes": MEMBERS[s], "metrics": m,
                             "residual": residual, "peer_return": peer_return, "peers": len(peers)})
    reversal.sort(key=lambda r: (r["residual"], r["ticker"]))
    fingerprints = {s: hashlib.sha256(pd.util.hash_pandas_object(f, index=True).values.tobytes()).hexdigest()
                    for s, f in dict(data, **{"^IXIC_LONG": history}).items()}
    return {"ok": True, "version": VERSION, "as_of": day.date().isoformat(),
            "universe_version": UNIVERSE["version"], "valid": len(prices), "total": len(TICKERS),
            "excluded": {s: reason for s, reason in excluded.items() if reason},
            "themes": themes, "crash": crash, "reference": ref, "rise": rise,
            "momentum": momentum, "independent_momentum": independent_momentum,
            "reversal": reversal, "metrics": metrics, "spy": spy,
            "qqq": j3._series_metrics_uncached(data["QQQ"]),
            "charts": {s: {str(d.date()): float(v) for d, v in f.Close.tail(252).items()}
                       for s, f in prices.items()}, "input_hashes": fingerprints,
            "engine_hashes": {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                              for p in ("jarvis8_engine.py", "jarvis8_data.py", "jarvis8_momentum.py", "jarvis3_data.py", "us_swing_selector.py",
                                        "data/jarvis8/universe.json", "us_market_calendar.py")}}


def unique_risk(rows, selected, equity, risk_percent, atr_multiple=2., cap_percent=10.):
    """Illustrative sizing only; gaps can exceed the stated ATR loss budget."""
    by_ticker = {r["ticker"]: r for r in rows}
    result = []
    for s in dict.fromkeys(selected):
        if s not in by_ticker:
            continue
        m = by_ticker[s]["metrics"]
        price, atr = m.get("current"), m.get("atr_pct")
        if not price or not atr or atr <= 0:
            continue
        distance = price * atr / 100 * atr_multiple
        shares = int(min(equity * risk_percent / 100 / distance,
                         equity * cap_percent / 100 / price))
        result.append({"ticker": s, "shares": shares, "notional": shares*price,
                       "weight": shares*price/equity*100, "atr_distance": distance,
                       "planned_risk": shares*distance, "themes": MEMBERS.get(s, [])})
    # Never silently suggest spending more than the available cash.
    total = sum(r["notional"] for r in result)
    if total > equity:
        factor = equity / total
        for r in result:
            old_shares = r["shares"]
            r["shares"] = int(old_shares*factor)
            ratio = r["shares"]/old_shares if old_shares else 0
            for k in ("notional", "weight", "planned_risk"):
                r[k] *= ratio
    return result
