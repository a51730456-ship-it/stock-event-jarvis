# -*- coding: utf-8 -*-
"""한국테마 설명서가 「현실과 맞나」 — 2026-08-09 부터 실제로 쌓인 목록의 성적 (2026-11-04 상하님 「한국테마 설명이 너무 길다 ·
그리고 현실과 맞냐?」).

자비스13 「📊 파트별 성적표」와 **같은 셈**을 그대로 부른다(jarvis13_scorecard_compare.split_unfillable · part_table) —
화면과 같은 자료(data/picklist/*.KR.csv · data/picklist_theme15) · 같은 시세(jarvis4_data.get_daily_frame · 코스피 일봉).
여기서 따로 더 세는 것은 **가운데 값**(설명서가 「가운데 값」으로 적어 두었기 때문)과 산 뒤 지난 거래일 수뿐이다.
값을 못 받은 종목은 빼고 센다(0으로 채우지 않는다). 아무것도 쓰지 않는다 — 결과는 J13_OUT 폴더(깃허브가 따로 갈래에 올림).
"""
from __future__ import annotations

import bisect
import os
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jarvis4_data as j4data  # noqa: E402
import jarvis13_market  # noqa: E402
import jarvis13_scorecard_compare as j13vx  # noqa: E402
import jarvis13_theme15  # noqa: E402
import picklist_store  # noqa: E402

OUT = Path(os.environ.get("J13_OUT") or "j13reality")


def load():
    rows = []
    for day in sorted(picklist_store.available_dates("KR")):
        for row in picklist_store.load_rows(day, "KR"):
            kind = str(row.get("list_kind") or "")
            if kind in j13vx.PARTS and picklist_store.should_show(kind, "KR"):
                rows.append(row)
    rows.extend(jarvis13_theme15.load_all(picklist_store))
    codes = sorted({str(row.get("code") or "").strip() for row in rows} - {""})

    def one(code):
        try:
            return code, j4data.get_daily_frame(code, ttl_seconds=1800)
        except Exception:
            return code, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        frames = {code: frame for code, frame in pool.map(one, codes) if frame is not None}
    kospi = jarvis13_market.index_frame("KOSPI")
    return rows, frames, kospi, jarvis13_market.last_finished_day(kospi), len(codes)


def gains(rows, frames, kospi, last_day):
    """파트마다 [(수익 %, 같은 날 코스피 %, 지난 거래일)] — part_table 과 같은 셈(가운데 값을 내려고 줄마다 남긴다)."""
    ix_close = j13vx.series_by_day(kospi, "Close")
    ix_open = j13vx.series_by_day(kospi, "Open")
    calendar = [day for day in ix_close if day in ix_open and day <= last_day]
    end = calendar[-1]
    out = {kind: [] for kind in j13vx.PARTS}
    for row in rows:
        kind = str(row.get("list_kind") or "")
        buy = j13vx._num(row.get("buy_open"))
        code = str(row.get("code") or "").strip()
        if kind not in out or not buy or not code:
            continue
        try:
            listed = date.fromisoformat(str(row.get("trade_date") or "")[:10])
        except ValueError:
            continue
        place = bisect.bisect_right(calendar, listed)
        if place >= len(calendar):
            continue
        bought = calendar[place]
        closes = j13vx.series_by_day(frames.get(code), "Close", listed - timedelta(days=10))
        seen = [value for day, value in closes.items() if day <= end]
        if not seen:
            continue
        out[kind].append(((seen[-1] / buy - 1.0) * 100.0, (ix_close[end] / ix_open[bought] - 1.0) * 100.0,
                          len(calendar) - 1 - place))
    return out, end


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, frames, kospi, last_day, codes = load()
    usable, blocked = j13vx.split_unfillable(rows, frames)
    table = j13vx.part_table(usable, frames, kospi, last_day=last_day)
    detail, end = gains(usable, frames, kospi, last_day)
    first = min(str(row.get("trade_date") or "")[:10] for row in rows)
    lines = [f"기간 {first} ~ {end} · 목록 줄 {len(rows)} · 종목 {codes}개 중 시세 받음 {len(frames)}개 · 상한가라 못 산 줄 {len(blocked)}",
             "파트 | 산 줄 | 이익 난 줄 | 평균 | 가운데 | 같은 날 코스피 평균 | 코스피보다 나은 줄 | 산 뒤 거래일(가운데)"]
    for kind in j13vx.PARTS:
        slot, items = table[kind], detail[kind]
        n = slot["n"]
        if not n:
            lines.append(f"{j13vx.PART_NAMES[kind]} | 0 | - | - | - | - | - | -")
            continue
        median = statistics.median(g for g, _ix, _d in items) if items else None
        held = statistics.median(d for _g, _ix, d in items) if items else None
        lines.append(f"{j13vx.PART_NAMES[kind]} | {n} | {slot['win'] / n * 100:.1f}% ({slot['win']}) | "
                     f"{slot['sum'] / n:+.2f}% | {median:+.2f}% | {slot['ix_sum'] / n:+.2f}% | "
                     f"{slot['beat'] / n * 100:.1f}% ({slot['beat']}) | {held:.0f}")
    text = "\n".join(lines) + "\n"
    (OUT / "result.txt").write_text(text, encoding="utf-8")
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
