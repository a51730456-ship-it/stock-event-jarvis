"""자비스5 테마 선행감지의 순수 계산 엔진.

이 모듈은 매수 신호를 만들지 않는다. 네이버의 누적 거래대금 스냅샷을 비교해
``거래활동 급증``과 ``여러 종목 확산`` 가설을 분리해서 기록하고, 이후 수익률로
검증할 실험 후보만 만든다. 거래대금은 매수·매도 합계이므로 자금 순유입이라고
부르지 않는다.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from statistics import median


MODEL_LABELS = {
    "A": "거래활동 급증",
    "B": "다종목 확산",
    "C": "급증+가격확산",
}
DETECTOR_VERSION = 2
DEFAULT_HORIZONS = (5, 10, 20, 30)


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percentile_ranks(rows: list[dict], field: str) -> dict[int, float]:
    values = []
    for row in rows:
        value = _finite(row.get(field))
        if value is None and field == "activity_intensity":
            weighted = _finite(row.get("weighted_interval_value"))
            members = max(1, int(row.get("member_count") or 0))
            value = weighted / math.sqrt(members) if weighted is not None else None
        if value is not None and value > 0:
            values.append((int(row["theme_no"]), value))
    values.sort(key=lambda item: item[1])
    if not values:
        return {}
    denominator = max(1, len(values) - 1)
    return {theme_no: index / denominator for index, (theme_no, _value) in enumerate(values)}


def rank_lead_themes(theme_rows: list[dict]) -> list[dict]:
    """테마 선행 후보를 '거래금액순'이 아닌 다요소 점수로 정렬한다.

    과거 동일시각 기준선이 있으면 자기 평소 대비 증가를 가장 크게 보고, 아직
    학습 중이면 거래활동 횡단면 순위의 비중을 20점으로 제한한다. 나머지는
    거래 참여 종목 수, 상승 확산, 단일종목 독점도를 사용한다.

    시가총액으로 단순 나누지 않는 이유는 작은 테마·저유동성 종목이 비정상적으로
    상단을 독점할 수 있기 때문이다. 대신 큰 종목의 평소 거래규모는 동일시각
    자기 기준선에서 상쇄하고, 여러 테마에 겹친 종목은 이미 1/√소속테마수로 줄인다.
    """
    rows = [dict(row) for row in theme_rows]
    activity_ranks = _percentile_ranks(rows, "activity_intensity")
    ranked = []
    for fallback_no, row in enumerate(rows, 1):
        theme_no = int(row.get("theme_no") or fallback_no)
        members = max(1, int(row.get("member_count") or 0))
        active = int(row.get("active_count") or 0)
        advancers = int(row.get("advancers") or 0)
        participation = min(1.0, active / members)
        breadth = min(1.0, advancers / members)
        share = _finite(row.get("top_contributor_share"))
        concentration_health = max(0.0, 1.0 - share) if share is not None else 0.0
        percentile = activity_ranks.get(theme_no, 0.0)
        baseline_ratio = _finite(row.get("baseline_ratio"))

        if baseline_ratio is not None:
            baseline_points = max(0.0, min(35.0, (baseline_ratio - 1.0) / 2.0 * 35.0))
            components = {
                "동일시각 증가": baseline_points,
                "횡단면 활동": percentile * 15.0,
                "거래 참여": participation * 20.0,
                "상승 확산": breadth * 20.0,
                "독점도 건전성": concentration_health * 10.0,
            }
            stage = "선행점수"
        else:
            components = {
                "횡단면 활동": percentile * 20.0,
                "거래 참여": participation * 30.0,
                "상승 확산": breadth * 30.0,
                "독점도 건전성": concentration_health * 20.0,
            }
            stage = "학습점수"

        quality_penalty = 0.0
        quality_flags = []
        if active < 3:
            quality_penalty += 15.0
            quality_flags.append("참여 3종목 미만")
        if share is None or share > 0.55:
            quality_penalty += 20.0
            quality_flags.append("단일종목 집중")
        median_change = _finite(row.get("median_change_pct"))
        if median_change is not None and median_change >= 4.0:
            quality_penalty += 15.0
            quality_flags.append("이미 4% 이상 상승")

        lead_score = max(0.0, min(100.0, sum(components.values()) - quality_penalty))
        row.update({
            "theme_no": theme_no,
            "lead_score": round(lead_score, 1),
            "lead_stage": stage,
            "lead_components": {key: round(value, 1) for key, value in components.items()},
            "lead_penalty": round(quality_penalty, 1),
            "lead_flags": quality_flags,
            "activity_percentile": percentile,
            "participation_ratio": participation,
            "breadth_ratio": breadth,
        })
        ranked.append(row)
    ranked.sort(
        key=lambda row: (
            float(row.get("lead_score") or 0),
            float(row.get("baseline_ratio") or 0),
            float(row.get("activity_intensity") or 0),
        ),
        reverse=True,
    )
    for index, row in enumerate(ranked, 1):
        row["lead_rank"] = index
    return ranked


def build_theme_snapshot(
    raw_themes: list[dict],
    *,
    previous_values: dict[tuple[int, str], float] | None = None,
    baselines: dict[int, float] | None = None,
    interval_seconds: float | None = None,
    quotes: dict[str, dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """원시 테마 상세를 테마행·종목행으로 바꾼다.

    ``previous_values``가 비어 있는 첫 수집은 누적값만 저장하고 구간 거래대금은
    계산하지 않는다. 누적값이 감소한 행도 장 전환/파서 불연속 가능성이 있어
    구간값을 만들지 않는다.
    """
    previous_values = previous_values or {}
    baselines = baselines or {}
    # 당일 시가·고가·저가는 테마 상세에 없어 실시간 시세 묶음조회로 따로 받는다
    # (2026-07-26). 못 받아도 예전처럼 동작해야 하므로 없으면 빈 사전이다.
    quotes = quotes or {}
    interval_minutes = (
        max(float(interval_seconds), 1.0) / 60.0
        if _finite(interval_seconds) is not None and float(interval_seconds) > 0
        else 1.0
    )

    theme_memberships: dict[str, set[int]] = {}
    for theme in raw_themes:
        theme_no = int(theme["no"])
        for stock in theme.get("stocks") or []:
            code = str(stock.get("code") or "").strip()
            if code:
                theme_memberships.setdefault(code, set()).add(theme_no)

    stock_rows: list[dict] = []
    theme_rows: list[dict] = []
    for theme in raw_themes:
        theme_no = int(theme["no"])
        members = []
        for stock in theme.get("stocks") or []:
            code = str(stock.get("code") or "").strip()
            if not code:
                continue
            current_value = _finite(stock.get("trading_value"))
            previous = _finite(previous_values.get((theme_no, code)))
            interval = None
            if current_value is not None and previous is not None and current_value >= previous:
                # 수집 간격이 31초든 180초든 같은 단위로 비교하도록 분당 값으로 정규화한다.
                interval = (current_value - previous) / interval_minutes
            theme_count = max(1, len(theme_memberships.get(code) or {theme_no}))
            weight = 1 / math.sqrt(theme_count)
            row = {
                "theme_no": theme_no,
                "stock_code": code,
                "stock_name": str(stock.get("name") or code),
                "price": _finite(stock.get("price")),
                "change_pct": _finite(stock.get("change_pct")),
                "volume": _finite(stock.get("volume")),
                "trading_value": current_value,
                "previous_volume": _finite(stock.get("previous_volume")),
                "interval_trading_value": interval,
                "theme_count": theme_count,
                "contribution_weight": weight,
                "parser_version": stock.get("parser_version"),
            }
            quote = quotes.get(code)
            if quote:
                # 거래정지 종목은 고가·저가가 0이나 옛값으로 굳어 있다. 그대로
                # 저장하면 나중에 종가위치가 엉뚱하게 계산되므로 넣지 않는다.
                if quote.get("tradable"):
                    row["day_open"] = quote.get("day_open")
                    row["day_high"] = quote.get("day_high")
                    row["day_low"] = quote.get("day_low")
                row["market_cap"] = quote.get("market_cap")
            stock_rows.append(row)
            members.append(row)

        changes = [row["change_pct"] for row in members if row["change_pct"] is not None]
        intervals = [
            row["interval_trading_value"]
            for row in members
            if row["interval_trading_value"] is not None
        ]
        weighted = [
            row["interval_trading_value"] * row["contribution_weight"]
            for row in members
            if row["interval_trading_value"] is not None
            and row["interval_trading_value"] > 0
        ]
        total_weighted = sum(weighted) if weighted else None
        contributor_rows = sorted(
            (
                (row["interval_trading_value"] * row["contribution_weight"], row["stock_code"])
                for row in members
                if row["interval_trading_value"] is not None
                and row["interval_trading_value"] > 0
            ),
            reverse=True,
        )
        baseline = _finite(baselines.get(theme_no))
        activity_intensity = (
            total_weighted / math.sqrt(len(members))
            if total_weighted is not None and members else None
        )
        theme_rows.append({
            "theme_no": theme_no,
            "theme_name": str(theme.get("name") or theme_no),
            "change_pct": _finite(theme.get("change_pct")),
            "median_change_pct": median(changes) if changes else None,
            "relative_change_pct": None,
            "member_count": len(members),
            "advancers": sum(value > 0 for value in changes),
            "decliners": sum(value < 0 for value in changes),
            "unchanged": sum(value == 0 for value in changes),
            "active_count": sum(value > 0 for value in intervals),
            "total_trading_value": sum(
                row["trading_value"] for row in members if row["trading_value"] is not None
            ),
            "interval_trading_value": sum(intervals) if intervals else None,
            "weighted_interval_value": total_weighted,
            "activity_intensity": activity_intensity,
            "baseline_ratio": (
                activity_intensity / baseline
                if activity_intensity is not None and baseline is not None and baseline > 0
                else None
            ),
            "top_contributor_share": (
                max(weighted) / total_weighted if weighted and total_weighted and total_weighted > 0 else None
            ),
            "top_contributors": [code for _value, code in contributor_rows[:5]],
            "stale_count": sum(row["trading_value"] is None for row in members),
        })

    theme_medians = [
        row["median_change_pct"]
        for row in theme_rows
        if row["median_change_pct"] is not None
    ]
    market_median = median(theme_medians) if theme_medians else None
    for row in theme_rows:
        if row["median_change_pct"] is not None and market_median is not None:
            row["relative_change_pct"] = row["median_change_pct"] - market_median
    return theme_rows, stock_rows


def detect_experiment_signals(
    theme_rows: list[dict],
    *,
    created_at: datetime,
    min_interval_value: float = 300_000_000,
) -> list[dict]:
    """서로 다른 세 가설의 실험 후보를 만든다.

    횡단면 상위라는 이유만으로 경보하지 않고 최소 거래활동, 다종목 참여,
    단일종목 독점 제한을 함께 적용한다. 동일시각 기준선이 아직 없으면 A/C는
    ``학습중``으로만 기록한다.
    """
    ranks = _percentile_ranks(theme_rows, "activity_intensity")
    market_values = [
        row.get("median_change_pct")
        for row in theme_rows
        if _finite(row.get("median_change_pct")) is not None
    ]
    market_median = median(market_values) if market_values else None
    signals: list[dict] = []

    for row in theme_rows:
        theme_no = int(row["theme_no"])
        interval = _finite(row.get("weighted_interval_value"))
        intensity = _finite(row.get("activity_intensity"))
        if intensity is None and interval is not None:
            intensity = interval / math.sqrt(max(1, int(row.get("member_count") or 0)))
        percentile = ranks.get(theme_no, 0.0)
        active = int(row.get("active_count") or 0)
        members = max(1, int(row.get("member_count") or 0))
        share = _finite(row.get("top_contributor_share"))
        baseline_ratio = _finite(row.get("baseline_ratio"))
        relative = _finite(row.get("relative_change_pct"))
        theme_change = _finite(row.get("median_change_pct"))
        breadth = int(row.get("advancers") or 0) / members

        common_features = {
            "theme_name": row.get("theme_name"),
            "interval_value": interval,
            "activity_intensity": intensity,
            "interval_percentile": percentile,
            "active_count": active,
            "member_count": members,
            "top_contributor_share": share,
            "baseline_ratio": baseline_ratio,
            "breadth": breadth,
            "theme_change_pct": theme_change,
            "relative_change_pct": relative,
            "market_median_change_pct": market_median,
            "top_contributors": list(row.get("top_contributors") or []),
        }

        activity_gate = (
            interval is not None
            and interval >= min_interval_value
            and percentile >= 0.97
            and active >= 3
            and share is not None
            and share <= 0.55
        )
        if activity_gate and (baseline_ratio is None or baseline_ratio >= 1.5):
            stage = "학습중" if baseline_ratio is None else "실험감지"
            score = min(100.0, 55 + percentile * 20 + min(active, 8) * 2.5)
            signals.append({
                "theme_no": theme_no,
                "model": "A",
                "model_version": DETECTOR_VERSION,
                "score": round(score, 1),
                "stage": stage,
                "reason": (
                    f"거래활동 상위 {(1-percentile)*100:.1f}% · 참여 {active}종목 · "
                    f"최대기여 {share*100:.0f}%"
                ),
                "features": common_features,
                "created_at": created_at,
            })

        breadth_gate = (
            interval is not None
            and interval >= min_interval_value * 0.5
            and percentile >= 0.90
            and active >= max(3, math.ceil(members * 0.25))
            and breadth >= 0.60
            and share is not None
            and share <= 0.45
            and relative is not None
            and relative > 0.10
            and theme_change is not None
            and theme_change < 4.0
        )
        if breadth_gate:
            score = min(100.0, 40 + percentile * 20 + breadth * 20 + min(active, 8) * 2.5)
            signals.append({
                "theme_no": theme_no,
                "model": "B",
                "model_version": DETECTOR_VERSION,
                "score": round(score, 1),
                "stage": "실험감지",
                "reason": (
                    f"상승확산 {breadth*100:.0f}% · 참여 {active}종목 · 시장대비 {relative:+.2f}%p"
                ),
                "features": common_features,
                "created_at": created_at,
            })

        combined_gate = (
            activity_gate
            and breadth >= 0.60
            and share is not None
            and share <= 0.45
            and relative is not None
            and relative > 0.10
            and theme_change is not None
            and 0.05 < theme_change < 4.0
            and (baseline_ratio is None or baseline_ratio >= 1.5)
        )
        if combined_gate:
            stage = "학습중" if baseline_ratio is None else "실험감지"
            score = min(100.0, 45 + percentile * 20 + breadth * 20 + min(active, 6) * 2.5)
            signals.append({
                "theme_no": theme_no,
                "model": "C",
                "model_version": DETECTOR_VERSION,
                "score": round(score, 1),
                "stage": stage,
                "reason": (
                    f"거래활동+상승확산 동시 · 시장대비 {relative:+.2f}%p · "
                    f"최대기여 {share*100:.0f}%"
                ),
                "features": common_features,
                "created_at": created_at,
            })
    # 같은 핵심 종목 사건이 여러 유사 테마로 복제되는 경보를 모델별로 한 번만 남긴다.
    deduped = []
    for signal in sorted(signals, key=lambda item: item["score"], reverse=True):
        signature = set(signal["features"].get("top_contributors") or [])
        duplicate = False
        if signature:
            for kept in deduped:
                if kept["model"] != signal["model"]:
                    continue
                kept_signature = set(kept["features"].get("top_contributors") or [])
                denominator = min(len(signature), len(kept_signature))
                if denominator and len(signature & kept_signature) / denominator >= 0.60:
                    duplicate = True
                    break
        if not duplicate:
            deduped.append(signal)
    return sorted(deduped, key=lambda item: (item["theme_no"], item["model"]))


def evaluate_due_outcomes(
    pending: list[dict],
    current_run: dict,
    current_theme_rows: list[dict],
    *,
    horizons=DEFAULT_HORIZONS,
) -> list[dict]:
    """현재 스냅샷 시각을 지난 미평가 신호의 선행성과를 계산한다."""
    now = datetime.fromisoformat(str(current_run["captured_at"]))
    current_by_theme = {int(row["theme_no"]): row for row in current_theme_rows}
    market_values = [
        _finite(row.get("median_change_pct"))
        for row in current_theme_rows
        if _finite(row.get("median_change_pct")) is not None
    ]
    current_market = median(market_values) if market_values else None
    outcomes = []
    for signal in pending:
        start = datetime.fromisoformat(str(signal["captured_at"]))
        elapsed_minutes = (now - start).total_seconds() / 60
        current = current_by_theme.get(int(signal["theme_no"]))
        start_change = _finite(signal.get("signal_change_pct"))
        current_change = _finite(current.get("median_change_pct")) if current else None
        if current_change is None or start_change is None:
            continue
        try:
            features = json.loads(signal.get("feature_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            features = {}
        start_market = _finite(features.get("market_median_change_pct"))
        forward = current_change - start_change
        relative_forward = (
            forward - (current_market - start_market)
            if current_market is not None and start_market is not None
            else None
        )
        for horizon in horizons:
            if elapsed_minutes < int(horizon):
                continue
            outcomes.append({
                "signal_id": int(signal["id"]),
                "horizon_minutes": int(horizon),
                "evaluated_run_id": int(current_run["id"]),
                "forward_return_pct": round(forward, 6),
                "relative_forward_return_pct": (
                    round(relative_forward, 6) if relative_forward is not None else None
                ),
                "success": int(forward > 0 and (relative_forward is None or relative_forward > 0)),
                "evaluated_at": now,
            })
    return outcomes
