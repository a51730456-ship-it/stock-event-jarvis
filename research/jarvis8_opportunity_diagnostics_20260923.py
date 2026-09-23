"""Reproduce J8-only opportunity diagnostics; no BitMEX or Jarvis 3 imports.

This is a descriptive audit of the already-seen 12-1 momentum study, not a
new trading gate. The top 20 cycles are chosen *after* returns are known.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLES = ROOT / "output/independent_research/high_screen_20260922/cycles.csv"
STUDY = ROOT / "output/independent_research/high_screen_20260922/result.json"
CLOSE = ROOT / "output/jarvis3_audit_20260909/fresh_close.parquet"
OUTPUT = ROOT / "data/jarvis8/opportunity_diagnostics_20260923.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate(root: Path = ROOT) -> dict:
    cycles_path = root / CYCLES.relative_to(ROOT)
    study_path = root / STUDY.relative_to(ROOT)
    close_path = root / CLOSE.relative_to(ROOT)
    study = json.loads(study_path.read_text(encoding="utf-8"))
    expected_close = study["metadata"]["input_hashes"][str(CLOSE.relative_to(ROOT)).replace("\\", "/")]
    if sha256(close_path) != expected_close:
        raise ValueError("QQQ source prices differ from the frozen study")

    all_cycles = pd.read_csv(cycles_path)
    cycles = all_cycles.loc[
        (all_cycles["offset"] == 0) & (all_cycles["hold"] == 20)
        & (all_cycles["cost"] == .5)
    ].copy()
    if len(cycles) != 121 * 3 or cycles.duplicated(["day", "method"]).any():
        raise ValueError("Frozen cycle grid is incomplete or duplicated")
    returns = cycles.pivot(index="day", columns="method", values="return_pct")
    exposure = cycles.pivot(index="day", columns="method", values="exposure")
    if len(returns) != 121 or not {"momentum", "qqq", "high"}.issubset(returns.columns):
        raise ValueError("Frozen method/date grid does not match the study")
    active = exposure["momentum"].gt(0)
    if int(active.sum()) != 102 or not np.allclose(
        exposure.loc[active, "momentum"], exposure.loc[active, "qqq"]
    ):
        raise ValueError("Momentum and QQQ do not use matching signal exposure")
    if not np.isfinite(returns.loc[active, ["momentum", "qqq"]].to_numpy()).all():
        raise ValueError("Selected cycle returns contain invalid values")
    summary = next(r for r in study["summary"] if r["offset"] == 0
                   and r["method"] == "momentum" and r["hold"] == 20 and r["cost"] == .5)
    if summary["signals"] != 121 or summary["active"] != 102:
        raise ValueError("Study summary and cycle counts do not match")

    concentration = {}
    for method in ("momentum", "qqq"):
        selected = returns.loc[active, method]
        best = selected.nlargest(20)
        concentration[method] = {
            "all_simple_sum_pct_points": float(selected.sum()),
            "best20_simple_sum_pct_points": float(best.sum()),
            "remaining_simple_sum_pct_points": float(selected.sum() - best.sum()),
        }
    momentum_best_days = returns.loc[active, "momentum"].nlargest(20).index
    same_day_qqq = returns.loc[active, "qqq"]
    concentration["qqq_on_momentum_best_dates"] = {
        "best20_simple_sum_pct_points": float(same_day_qqq.loc[momentum_best_days].sum()),
        "remaining_simple_sum_pct_points": float(same_day_qqq.drop(momentum_best_days).sum()),
    }

    close = pd.read_parquet(close_path)["QQQ"].dropna()
    close.index = pd.to_datetime(close.index).normalize()
    # Every volatility input ends on the signal date; future prices are unused.
    vol20 = close.pct_change(fill_method=None).rolling(20, min_periods=20).std(ddof=1)
    vol20 *= math.sqrt(252) * 100
    days = pd.to_datetime(returns.index[active])
    signal_vol = vol20.reindex(days)
    if signal_vol.isna().any() or not np.isfinite(signal_vol.to_numpy()).all():
        raise ValueError("Pre-signal QQQ volatility is incomplete")
    edge = (returns.loc[active, "momentum"] - returns.loc[active, "qqq"]).to_numpy()
    quartile = pd.qcut(signal_vol, 4, labels=False, duplicates="raise")
    frame = pd.DataFrame({"vol": signal_vol.to_numpy(), "edge": edge,
                          "quartile": quartile.to_numpy()})
    quarters = [{
        "quartile": int(number) + 1,
        "signals": int(len(group)),
        "min_prior_vol_pct": float(group["vol"].min()),
        "max_prior_vol_pct": float(group["vol"].max()),
        "mean_excess_pct_points": float(group["edge"].mean()),
    } for number, group in frame.groupby("quartile", sort=True)]

    return {
        "version": "J8-OPPORTUNITY-DIAGNOSTICS-20260923.1",
        "inputs": {
            "script_sha256": sha256(ROOT / "research/jarvis8_opportunity_diagnostics_20260923.py"),
            "study_sha256": sha256(study_path),
            "cycles_sha256": sha256(cycles_path),
            "close_sha256": sha256(close_path),
        },
        "method": {
            "offset": 0, "hold": 20, "roundtrip_cost_pct": .5,
            "signal_count": 121, "active_count": 102, "best_count": 20,
            "pre_signal_volatility": "QQQ prior 20 completed daily returns, sample std (ddof=1) × sqrt(252)",
            "comparison": "same dates, next open, 20-session close, same exposure and cost QQQ",
        },
        "concentration": concentration,
        "volatility_quartiles": quarters,
        "volatility_edge_pearson": float(frame["vol"].corr(frame["edge"])),
        "limits": [
            "Already-seen current-survivor roster; not out-of-sample or future performance",
            "Top 20 cycles selected after returns; cannot be used as an advance no-trade filter",
            "Simple cycle sums are percentage points, not compounded account returns",
            "Four volatility groups are exploratory and have no multiple-testing correction",
            "BTC execution analysis was not an input to this US-equity calculation",
        ],
    }


if __name__ == "__main__":
    result = calculate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print("wrote", OUTPUT.relative_to(ROOT), "active", result["method"]["active_count"])
    print("concentration", result["concentration"])
    print("quartiles", result["volatility_quartiles"])
