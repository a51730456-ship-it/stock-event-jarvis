"""자비스5 테마 선행감지 원자료 수집기.

기본 루프는 장중 3분마다 네이버 전체 테마를 수집한다. Streamlit 화면과 분리되어
있으므로 브라우저를 늦게 열어도 이전 확산 과정이 전용 DB에 남는다.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

import jarvis4_data as j4
import jarvis5_data as engine
import jarvis5_store as store


_SEOUL = ZoneInfo("Asia/Seoul")
_COLLECTOR_LOCK_PORT = 51655


def _now() -> datetime:
    return datetime.now(_SEOUL)


def is_collection_window(now: datetime | None = None) -> bool:
    stamp = (now or _now()).astimezone(_SEOUL)
    return stamp.weekday() < 5 and dt_time(8, 50) <= stamp.time() <= dt_time(15, 40)


@contextmanager
def collector_instance_lock(port: int = _COLLECTOR_LOCK_PORT):
    """로컬 포트를 점유해 장중 수집기 중복 실행을 막고 비정상 종료 시 자동 해제한다."""
    guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        guard.bind(("127.0.0.1", int(port)))
        guard.listen(1)
    except OSError as exc:
        guard.close()
        raise RuntimeError("자비스5 수집기가 이미 실행 중입니다") from exc
    try:
        yield
    finally:
        guard.close()


def fetch_raw_themes(
    *,
    theme_nos: set[int] | None = None,
    max_workers: int = 10,
    fresh: bool = True,
) -> tuple[list[dict], list[str]]:
    listing = j4.get_all_themes(ttl_seconds=0 if fresh else 60)
    if not listing.get("ok"):
        raise RuntimeError(listing.get("error") or "테마 목록 조회 실패")
    themes = list(listing["themes"].values())
    if theme_nos:
        themes = [theme for theme in themes if int(theme["no"]) in theme_nos]
    if not themes:
        raise RuntimeError("수집할 테마가 없습니다")

    raw = []
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        futures = {
            executor.submit(
                j4.get_theme_stocks,
                int(theme["no"]),
                ttl_seconds=0 if fresh else 60,
            ): theme
            for theme in themes
        }
        for future in as_completed(futures):
            theme = futures[future]
            try:
                detail = future.result()
            except Exception as exc:
                failures.append(f"{theme['name']}: {exc}")
                continue
            if not detail.get("ok") or not detail.get("stocks"):
                failures.append(f"{theme['name']}: {detail.get('error') or '상세 없음'}")
                continue
            raw.append({**theme, "stocks": detail["stocks"]})
    raw.sort(key=lambda row: int(row["no"]))
    return raw, failures


def collect_once(
    *,
    kind: str = "full",
    theme_nos: set[int] | None = None,
    max_workers: int = 10,
    fresh: bool = True,
    db_path: str | Path | None = None,
) -> dict:
    started = time.perf_counter()
    captured_at = _now()
    run_base = {
        "captured_at": captured_at,
        "trade_date": captured_at.date().isoformat(),
        "kind": kind,
        "parser_version": j4.THEME_DETAIL_PARSER_VERSION,
    }
    try:
        raw_themes, failures = fetch_raw_themes(
            theme_nos=theme_nos, max_workers=max_workers, fresh=fresh
        )
        previous_snapshot = store.previous_stock_snapshot(
            captured_at.date().isoformat(), db_path=db_path
        )
        previous = previous_snapshot["values"] if previous_snapshot else {}
        interval_seconds = None
        if previous_snapshot:
            previous_at = datetime.fromisoformat(str(previous_snapshot["captured_at"]))
            if previous_at.tzinfo is None:
                previous_at = previous_at.replace(tzinfo=_SEOUL)
            interval_seconds = max(1.0, (captured_at - previous_at).total_seconds())
        baselines = store.same_time_interval_baselines(captured_at, db_path=db_path)
        theme_rows, stock_rows = engine.build_theme_snapshot(
            raw_themes,
            previous_values=previous,
            baselines=baselines,
            interval_seconds=interval_seconds,
        )
        status = "partial" if failures else "ok"
        run_id = store.save_collection(
            {
                **run_base,
                "status": status,
                "theme_count": len(theme_rows),
                "stock_row_count": len(stock_rows),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "interval_seconds": interval_seconds,
                "error": " / ".join(failures[:10]) if failures else None,
            },
            theme_rows,
            stock_rows,
            db_path=db_path,
        )

        signals = []
        if kind == "full" and previous:
            signals = engine.detect_experiment_signals(theme_rows, created_at=captured_at)
            store.save_signals(run_id, signals, db_path=db_path)

        current_run = store.latest_run(db_path=db_path)
        pending = store.pending_signals(db_path=db_path)
        outcomes = engine.evaluate_due_outcomes(pending, current_run, theme_rows)
        saved_outcomes = store.save_outcomes(outcomes, db_path=db_path)
        return {
            "ok": True,
            "run_id": run_id,
            "status": status,
            "theme_count": len(theme_rows),
            "stock_row_count": len(stock_rows),
            "failure_count": len(failures),
            "signal_count": len(signals),
            "outcome_count": saved_outcomes,
            "first_snapshot": not bool(previous),
            "interval_seconds": interval_seconds,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "captured_at": captured_at.isoformat(timespec="seconds"),
        }
    except Exception as exc:
        elapsed = round(time.perf_counter() - started, 3)
        run_id = store.save_failed_run(
            {**run_base, "elapsed_seconds": elapsed, "error": str(exc)},
            db_path=db_path,
        )
        return {
            "ok": False,
            "run_id": run_id,
            "error": str(exc),
            "elapsed_seconds": elapsed,
            "captured_at": captured_at.isoformat(timespec="seconds"),
        }


def _parse_clock(text: str | None) -> dt_time | None:
    """'15:35' 같은 한국시각 문자열을 시각으로 바꾼다."""
    if not text:
        return None
    hour, _, minute = str(text).partition(":")
    return dt_time(int(hour), int(minute or 0))


def run_loop(
    *,
    interval_seconds: int = 180,
    max_workers: int = 10,
    db_path=None,
    until: str | None = None,
    export_dir=None,
) -> None:
    """장중 반복 수집.

    ``until``과 ``export_dir``은 클라우드(GitHub Actions)용이다. 노트북을 켜 두지
    않아도 자료가 쌓이게 하려고 붙였다(2026-07-24). 클라우드 작업은 최대 6시간까지만
    살 수 있어 정해진 시각에 스스로 끝나야 하고, 끝나면 사라지므로 수집할 때마다
    하루치 파일을 남겨 저장소에 올릴 수 있게 한다.
    """
    interval_seconds = max(60, int(interval_seconds))
    stop_at = _parse_clock(until)
    with collector_instance_lock():
        print("자비스5 수집기 시작 — 장중 전체 테마 거래활동을 실험용 DB에 저장합니다.", flush=True)
        if stop_at:
            print(f"종료 예정 시각(한국시각): {stop_at.strftime('%H:%M')}", flush=True)
        while True:
            now = _now()
            if stop_at and now.time() >= stop_at:
                print("예정 시각이 되어 수집을 마칩니다.", flush=True)
                return
            if is_collection_window(now):
                result = collect_once(max_workers=max_workers, db_path=db_path)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if export_dir:
                    _export_quietly(export_dir, db_path=db_path)
            time.sleep(interval_seconds if is_collection_window() else 60)


def _export_quietly(export_dir, *, db_path=None) -> None:
    """하루치 파일을 다시 쓴다. 실패해도 수집은 계속되어야 한다."""
    try:
        import jarvis5_sync as sync

        result = sync.export_day(out_dir=export_dir, db_path=db_path)
        if not result.get("ok"):
            print(f"[내보내기 건너뜀] {result.get('error')}", flush=True)
    except Exception as exc:
        print(f"[내보내기 실패] {exc}", flush=True)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="자비스5 테마 선행감지 수집기")
    parser.add_argument("--once", action="store_true", help="한 번만 수집")
    parser.add_argument("--interval", type=int, default=180, help="장중 반복 간격(초, 최소 60)")
    parser.add_argument("--workers", type=int, default=10, help="네이버 상세 조회 동시 작업 수")
    parser.add_argument("--db", type=Path, default=None, help="테스트용 DB 경로")
    parser.add_argument(
        "--until", default=None,
        help="이 시각(한국시각 HH:MM)이 되면 스스로 끝낸다 — 클라우드 작업용",
    )
    parser.add_argument(
        "--export-dir", default=None,
        help="수집할 때마다 하루치 파일을 이 폴더에 남긴다 — 클라우드 작업용",
    )
    args = parser.parse_args()
    if args.once:
        result = collect_once(max_workers=args.workers, db_path=args.db)
        if args.export_dir:
            _export_quietly(args.export_dir, db_path=args.db)
        print(json.dumps(result, ensure_ascii=False))
        return
    run_loop(
        interval_seconds=args.interval,
        max_workers=args.workers,
        db_path=args.db,
        until=args.until,
        export_dir=args.export_dir,
    )


if __name__ == "__main__":
    main()
