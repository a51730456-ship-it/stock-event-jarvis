"""자비스5가 쌓은 자료로 '무엇을 봐야 이후 주가가 오르나'를 직접 계산한다.

경보로 걸러진 몇십 건이 아니라 모든 시점 x 모든 테마를 전수로 본다. 각 지표를
시각 t에서 재고, t+h분 뒤 그 테마의 중앙값 수익률이 얼마나 움직였는지 짝지어
순위상관을 낸다. 시장이 통째로 오르면 모든 테마가 같이 오르므로 횡단면 중앙값을
빼서 시장중립화한다 — 이걸 안 하면 아무 지표나 맞아 보인다.

    python jarvis5_analyze.py

며칠에 한 번 다시 돌려서 상관이 유지되는지 본다. 하루치 결과로 배점이나
임계값을 고치면 그날 장세에 맞춰 과적합된다.
"""
from __future__ import annotations

import io
import statistics
import sys
from datetime import datetime

# 윈도우 콘솔 기본 인코딩(cp949)에서 한글·기호가 깨지지 않게 한다.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import jarvis5_data as engine
import jarvis5_store as store

HORIZONS = (10, 20, 30)
MIN_THEMES = 50
MIN_SAMPLES = 200


def spearman(xs: list[float], ys: list[float]) -> float:
    """순위상관. 표본 분포가 치우쳐 있어 피어슨은 쓰지 않는다."""
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            k = i
            while k + 1 < len(order) and values[order[k + 1]] == values[order[i]]:
                k += 1
            shared = (i + k) / 2.0 + 1
            for m in range(i, k + 1):
                out[order[m]] = shared
            i = k + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = (
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    ) ** 0.5
    return numerator / denominator if denominator else 0.0


def _load(db_path=None):
    store.ensure_schema(db_path)
    with store.connection(db_path) as conn:
        runs = [dict(row) for row in conn.execute(
            "SELECT id, captured_at, trade_date FROM collection_runs "
            "WHERE kind = 'full' AND status != 'failed' ORDER BY captured_at"
        )]
        snapshots: dict[int, dict[int, dict]] = {}
        for row in conn.execute("SELECT * FROM theme_snapshots"):
            snapshots.setdefault(row["run_id"], {})[row["theme_no"]] = dict(row)
        pace: dict[int, dict[int, float]] = {}
        for row in conn.execute(
            "SELECT run_id, theme_no, SUM(volume) v, SUM(previous_volume) p "
            "FROM theme_stock_snapshots GROUP BY run_id, theme_no"
        ):
            if row["p"]:
                pace.setdefault(row["run_id"], {})[row["theme_no"]] = row["v"] / row["p"]
    for run in runs:
        run["moment"] = datetime.fromisoformat(str(run["captured_at"]))
    return runs, snapshots, pace


def _indicators(snapshot: dict, pace_value):
    members = max(1, int(snapshot.get("member_count") or 0))
    return {
        "거래활동 강도": snapshot.get("activity_intensity"),
        "구간 거래대금": snapshot.get("interval_trading_value"),
        "거래 참여 비율": (snapshot.get("active_count") or 0) / members,
        "상승 종목 비율": (snapshot.get("advancers") or 0) / members,
        "단일종목 독점도": snapshot.get("top_contributor_share"),
        "전일대비 거래페이스": pace_value,
        "현재 수익률(모멘텀)": snapshot.get("median_change_pct"),
        "동일시각 배수": snapshot.get("baseline_ratio"),
    }


def _forward_pairs(runs, snapshots, pace, horizon: int):
    """(지표, 선행점수, 순위, 시장중립 이후수익률) 짝을 모은다."""
    pairs = []
    for index, run in enumerate(runs):
        target = next(
            (later for later in runs[index + 1:]
             if (later["moment"] - run["moment"]).total_seconds() / 60 >= horizon),
            None,
        )
        if target is None:
            continue
        rows = list(snapshots.get(run["id"], {}).values())
        if len(rows) < MIN_THEMES:
            continue
        moves = {}
        for snapshot in rows:
            before = snapshot.get("median_change_pct")
            after = snapshots.get(target["id"], {}).get(
                snapshot["theme_no"], {}).get("median_change_pct")
            if before is not None and after is not None:
                moves[snapshot["theme_no"]] = after - before
        if len(moves) < MIN_THEMES:
            continue
        middle = statistics.median(moves.values())
        ranked = engine.rank_lead_themes(rows)
        for rank, scored in enumerate(ranked, 1):
            theme_no = scored["theme_no"]
            if theme_no not in moves:
                continue
            pairs.append((
                _indicators(scored, pace.get(run["id"], {}).get(theme_no)),
                float(scored.get("lead_score") or 0),
                rank,
                moves[theme_no] - middle,
            ))
    return pairs


def main(db_path=None) -> None:
    runs, snapshots, pace = _load(db_path)
    if len(runs) < 5:
        print("수집 자료가 부족합니다. 수집기를 더 돌린 뒤 다시 실행하십시오.")
        return
    days = sorted({run["trade_date"] for run in runs})
    print("수집 %d회 · %d거래일 (%s) · %s ~ %s"
          % (len(runs), len(days), ", ".join(days),
             runs[0]["moment"].strftime("%m-%d %H:%M"),
             runs[-1]["moment"].strftime("%m-%d %H:%M")))
    if len(days) < 5:
        print("주의: 거래일이 적어 그날 장세에 좌우됩니다. 배점·임계값을 고치지 마십시오.")

    tables = {horizon: _forward_pairs(runs, snapshots, pace, horizon) for horizon in HORIZONS}
    names = list(_indicators({"member_count": 1}, None))

    print("\n[1] 지표가 '이후' 시장중립 수익률과 얼마나 관계있나 (순위상관)")
    print("    0이면 관계없음, + 면 높을수록 이후 상승, - 면 이후 하락")
    print("    %-20s %9s %9s %9s %9s" % ("지표", "10분", "20분", "30분", "표본"))
    for key in names:
        cells, sample = [], 0
        for horizon in HORIZONS:
            xs = [float(i[key]) for i, _, _, _ in tables[horizon] if i.get(key) is not None]
            ys = [f for i, _, _, f in tables[horizon] if i.get(key) is not None]
            if len(xs) >= MIN_SAMPLES:
                cells.append("%+9.3f" % spearman(xs, ys))
                sample = max(sample, len(xs))
            else:
                cells.append("%9s" % "-")
        print("    %-20s %s %9d" % (key, "".join(cells), sample))

    print("\n[2] 합산 '선행 후보점수'는 어떤가")
    for horizon in HORIZONS:
        pairs = tables[horizon]
        if len(pairs) < MIN_SAMPLES:
            continue
        scores = [s for _, s, _, _ in pairs]
        forwards = [f for _, _, _, f in pairs]
        top = [f for _, _, rank, f in pairs if rank <= 20]
        rest = [f for _, _, rank, f in pairs if rank > 20]
        print("    %2d분: 상관 %+0.3f · 상위20위 %+0.3f%%p / 나머지 %+0.3f%%p (표본 %d)"
              % (horizon, spearman(scores, forwards),
                 statistics.median(top) if top else 0.0,
                 statistics.median(rest) if rest else 0.0, len(pairs)))

    print("\n[3] 지표 상위 10% vs 하위 10% · 30분 뒤 시장중립 수익률 중앙값")
    pairs = tables[30]
    for key in names:
        values = [(float(i[key]), f) for i, _, _, f in pairs if i.get(key) is not None]
        if len(values) < MIN_SAMPLES:
            continue
        values.sort(key=lambda pair: -pair[0])
        cut = max(1, len(values) // 10)
        high = statistics.median(value for _, value in values[:cut])
        low = statistics.median(value for _, value in values[-cut:])
        print("    %-20s 상위 %+0.3f%%p · 하위 %+0.3f%%p · 차이 %+0.3f%%p"
              % (key, high, low, high - low))

    print("\n표본은 구간이 겹치므로 서로 독립이 아닙니다. 실제로 독립인 것은 시점 수뿐입니다.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
