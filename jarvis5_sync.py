"""자비스5 수집 자료를 파일로 내보내고 다시 들여오는 동기화 모듈.

노트북을 켜 두지 않아도 자료가 쌓이게 하려고 만들었다(2026-07-24 사용자 요청).
GitHub Actions가 장중에 대신 수집해 하루치 파일을 저장소에 올리고, 노트북을 켜면
그 파일을 읽어 로컬 DB에 합친다. 금요일에 노트북을 끄고 월요일에 켜도 그 사이
자료가 남아 있는 것이 목적이다.

하루치 파일 세 개 (거래일마다) — 종목행 전체는 하루 83만 줄이라 저장소가 감당하지
못한다. 그래서 화면과 판정에 실제로 쓰이는 것만 담는다.
  * ``{날짜}.runs.csv.gz``   수집 시각·간격. 미니차트 가로축과 분당 환산의 기준.
  * ``{날짜}.themes.csv.gz`` 테마별 거래활동. 순위·차트·동일시각 기준선의 재료.
  * ``{날짜}.stocks.csv.gz`` 그날 마지막 수집분만. 다음 수집이 구간값을 이어서
    계산하려면 직전 누적 거래대금이 있어야 한다.

형식은 gzip CSV다. 같은 자료를 JSON으로 담으면 1.87MB인데 CSV에 유효숫자 8자리로
담으면 0.81MB다(2026-07-24 실측). 8자리면 거래대금·비율 모두 사실상 손실이 없다.

수집 id는 컴퓨터마다 다르므로 파일에는 넣지 않고 ``captured_at``으로 묶는다.
들여오기는 몇 번을 돌려도 같은 결과가 된다 — 이미 있는 수집 시각은 건너뛴다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import jarvis5_store as store

_SEOUL = ZoneInfo("Asia/Seoul")

# 저장소에 올리는 하루치 파일이 놓이는 곳.
EXPORT_DIR = Path(__file__).parent / "data" / "jarvis5"
SIGNIFICANT_DIGITS = 8

_RUN_FIELDS = (
    "captured_at", "trade_date", "kind", "status", "theme_count",
    "stock_row_count", "elapsed_seconds", "interval_seconds",
    "parser_version", "error",
)
_THEME_FIELDS = (
    "captured_at", "theme_no", "theme_name", "change_pct", "median_change_pct",
    "relative_change_pct", "member_count", "advancers", "decliners", "unchanged",
    "active_count", "total_trading_value", "interval_trading_value",
    "weighted_interval_value", "activity_intensity", "baseline_ratio",
    "top_contributor_share", "stale_count",
)
_STOCK_FIELDS = (
    "captured_at", "theme_no", "stock_code", "stock_name", "price", "change_pct",
    "volume", "trading_value", "previous_volume", "interval_trading_value",
    "theme_count", "contribution_weight", "parser_version",
)
_PARTS = {"runs": _RUN_FIELDS, "themes": _THEME_FIELDS, "stocks": _STOCK_FIELDS}

# 숫자로 되살려야 하는 칸 — CSV는 전부 글자로 읽히므로 되돌려 준다.
_INT_FIELDS = {
    "theme_no", "member_count", "advancers", "decliners", "unchanged",
    "active_count", "stale_count", "theme_count", "stock_row_count",
    "parser_version",
}
_TEXT_FIELDS = {
    "captured_at", "trade_date", "kind", "status", "error",
    "theme_name", "stock_code", "stock_name",
}


def _today() -> str:
    return datetime.now(_SEOUL).date().isoformat()


def part_path(trade_date: str, part: str, out_dir: Path | str | None = None) -> Path:
    return Path(out_dir or EXPORT_DIR) / f"{trade_date}.{part}.csv.gz"


def _round(value):
    """유효숫자를 줄여 파일 크기를 줄인다. 정수·글자는 그대로 둔다."""
    if not isinstance(value, float) or not math.isfinite(value) or value == 0:
        return value
    exponent = math.floor(math.log10(abs(value)))
    return round(value, max(0, SIGNIFICANT_DIGITS - 1 - exponent))


def _write_csv(path: Path, fields, rows) -> int:
    """임시 파일에 다 쓴 뒤 이름을 바꾼다.

    클라우드에서는 쓰는 도중에 git이 파일을 집어 갈 수 있어, 반쯤 쓰인 파일이
    저장소에 올라가면 안 된다. 이름 바꾸기는 한 번에 일어나므로 그런 일이 없다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _round(row.get(key)) for key in fields})
    temporary.replace(path)
    return path.stat().st_size


def _read_csv(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return [_restore_types(row) for row in csv.DictReader(handle)]


def _restore_types(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if value == "" or value is None:
            out[key] = None
        elif key in _TEXT_FIELDS:
            out[key] = value
        elif key in _INT_FIELDS:
            try:
                out[key] = int(float(value))
            except ValueError:
                out[key] = None
        else:
            try:
                out[key] = float(value)
            except ValueError:
                out[key] = value
    return out


def export_day(
    trade_date: str | None = None,
    *,
    out_dir: Path | str | None = None,
    db_path=None,
) -> dict:
    """하루치 수집 결과를 파일 세 개로 내보낸다."""
    trade_date = trade_date or _today()
    store.ensure_schema(db_path)
    with store.connection(db_path) as conn:
        runs = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM collection_runs WHERE trade_date = ? ORDER BY id",
                (trade_date,),
            )
        ]
        if not runs:
            return {"ok": False, "error": f"{trade_date} 자료가 없습니다", "run_count": 0}
        at_by_id = {int(row["id"]): str(row["captured_at"]) for row in runs}
        run_ids = list(at_by_id)
        placeholders = ",".join("?" for _ in run_ids)
        themes = [
            dict(row, captured_at=at_by_id[int(row["run_id"])])
            for row in conn.execute(
                f"SELECT * FROM theme_snapshots WHERE run_id IN ({placeholders}) "
                "ORDER BY run_id, theme_no",
                run_ids,
            )
        ]
        # 종목행은 마지막 수집분만 — 다음 수집이 구간값을 이어 계산하는 데만 쓴다.
        last_run_id = run_ids[-1]
        stocks = [
            dict(row, captured_at=at_by_id[last_run_id])
            for row in conn.execute(
                "SELECT * FROM theme_stock_snapshots WHERE run_id = ? "
                "ORDER BY theme_no, stock_code",
                (last_run_id,),
            )
        ]

    sizes = {
        "runs": _write_csv(part_path(trade_date, "runs", out_dir), _RUN_FIELDS, runs),
        "themes": _write_csv(part_path(trade_date, "themes", out_dir), _THEME_FIELDS, themes),
        "stocks": _write_csv(part_path(trade_date, "stocks", out_dir), _STOCK_FIELDS, stocks),
    }
    return {
        "ok": True,
        "trade_date": trade_date,
        "run_count": len(runs),
        "theme_row_count": len(themes),
        "stock_row_count": len(stocks),
        "bytes": sum(sizes.values()),
        "files": {part: str(part_path(trade_date, part, out_dir)) for part in _PARTS},
    }


def available_dates(directory: Path | str | None = None) -> list[str]:
    """폴더에 들어 있는 거래일 목록(오래된 순)."""
    directory = Path(directory or EXPORT_DIR)
    if not directory.exists():
        return []
    return sorted({path.name.split(".")[0] for path in directory.glob("*.runs.csv.gz")})


def _existing_captured_at(trade_date: str, db_path=None) -> set[str]:
    with store.connection(db_path) as conn:
        return {
            str(row["captured_at"])
            for row in conn.execute(
                "SELECT captured_at FROM collection_runs WHERE trade_date = ?",
                (trade_date,),
            )
        }


def import_day(trade_date: str, *, directory=None, db_path=None) -> dict:
    """거래일 하나를 로컬 DB에 합친다. 여러 번 돌려도 안전하다."""
    runs_path = part_path(trade_date, "runs", directory)
    if not runs_path.exists():
        return {"ok": False, "trade_date": trade_date, "error": "수집 목록 파일이 없습니다"}
    try:
        runs = _read_csv(runs_path)
        themes_path = part_path(trade_date, "themes", directory)
        stocks_path = part_path(trade_date, "stocks", directory)
        themes = _read_csv(themes_path) if themes_path.exists() else []
        stocks = _read_csv(stocks_path) if stocks_path.exists() else []
    except Exception as exc:
        return {"ok": False, "trade_date": trade_date, "error": f"읽기 실패: {exc}"}

    store.ensure_schema(db_path)
    already = _existing_captured_at(trade_date, db_path=db_path)

    themes_by_at: dict[str, list[dict]] = {}
    for row in themes:
        themes_by_at.setdefault(str(row.get("captured_at")), []).append(row)
    stocks_by_at: dict[str, list[dict]] = {}
    for row in stocks:
        stocks_by_at.setdefault(str(row.get("captured_at")), []).append(row)

    added_runs = 0
    added_themes = 0
    for run in runs:
        captured_at = str(run.get("captured_at"))
        if captured_at in already:
            continue
        run_themes = themes_by_at.get(captured_at) or []
        run_stocks = stocks_by_at.get(captured_at) or []
        store.save_collection(
            {
                "captured_at": captured_at,
                "trade_date": run.get("trade_date") or trade_date,
                "kind": run.get("kind") or "full",
                "status": run.get("status") or "ok",
                "theme_count": run.get("theme_count") or len(run_themes),
                "stock_row_count": run.get("stock_row_count") or len(run_stocks),
                "elapsed_seconds": run.get("elapsed_seconds"),
                "interval_seconds": run.get("interval_seconds"),
                "parser_version": run.get("parser_version"),
                "error": run.get("error"),
            },
            run_themes,
            run_stocks,
            db_path=db_path,
        )
        already.add(captured_at)
        added_runs += 1
        added_themes += len(run_themes)

    return {
        "ok": True,
        "trade_date": trade_date,
        "added_runs": added_runs,
        "added_theme_rows": added_themes,
        "skipped_runs": len(runs) - added_runs,
    }


def import_dir(
    directory: Path | str | None = None,
    *,
    days: int | None = None,
    db_path=None,
) -> dict:
    """폴더 안의 하루치 자료를 오래된 것부터 모두 합친다."""
    dates = available_dates(directory)
    if not dates:
        return {"ok": False, "error": "가져올 자료가 아직 없습니다", "days": []}
    if days is not None:
        cutoff = (datetime.now(_SEOUL).date() - timedelta(days=int(days))).isoformat()
        dates = [value for value in dates if value >= cutoff]
    results = [import_day(value, directory=directory, db_path=db_path) for value in dates]
    return {
        "ok": True,
        "days": results,
        "day_count": len(results),
        "added_runs": sum(item.get("added_runs") or 0 for item in results),
        "added_theme_rows": sum(item.get("added_theme_rows") or 0 for item in results),
    }


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="자비스5 수집 자료 내보내기·들여오기")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="하루치를 파일로 내보낸다")
    export.add_argument("--date", default=None, help="거래일(YYYY-MM-DD), 기본값 오늘")
    export.add_argument("--out", default=None, help="내보낼 폴더")
    export.add_argument("--db", default=None, help="테스트용 DB 경로")

    load = sub.add_parser("import", help="폴더 자료를 로컬 DB에 합친다")
    load.add_argument("--dir", default=None, help="가져올 폴더")
    load.add_argument("--date", default=None, help="거래일 하나만")
    load.add_argument("--days", type=int, default=None, help="최근 며칠치만")
    load.add_argument("--db", default=None, help="테스트용 DB 경로")

    args = parser.parse_args()
    if args.command == "export":
        result = export_day(args.date, out_dir=args.out, db_path=args.db)
    elif args.date:
        result = import_day(args.date, directory=args.dir, db_path=args.db)
    else:
        result = import_dir(args.dir, days=args.days, db_path=args.db)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
