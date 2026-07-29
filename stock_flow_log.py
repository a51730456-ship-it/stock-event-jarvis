"""종목별 하루치 수급을 저녁에 모아 둔다.

왜 필요한가 (2026-07-29 실측)
-----------------------------
네이버 종목별 수급표는 **20거래일치만** 준다. 한 달이 지나면 그 앞은
사라진다. 지금은 `2026.06.30 ~ 2026.07.28` 스무 줄뿐이다.

지나간 수급은 **소급할 수 없다.** 오늘 안 받아 두면 두 달 뒤에
"외국인이 산 다음 날 올랐나"를 물어볼 수 없다. 자비스6이 나중에
답해야 할 질문이 그것이다.

무엇을 하지 않는가
------------------
- **장중에 부르지 않는다.** 종목별 당일 수급은 거래소가 장중에 공개하지
  않는다. 장 마감 뒤(저녁)에야 그날 줄이 생긴다.
- 값을 만들지 않는다. 네이버가 준 줄을 그대로 옮겨 적을 뿐이다.
- 신호도 판정도 여기서 만들지 않는다.

쌓이는 곳
---------
`data/stock_flow/{종목코드}.csv` — 날짜 하나에 한 줄. 같은 날짜를 다시
받으면 덮어쓴다(네이버가 잠정치를 확정치로 고치는 경우가 있다).

    python stock_flow_log.py --export-dir data/stock_flow
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_SEOUL = ZoneInfo("Asia/Seoul")
EXPORT_DIR = Path("data/stock_flow")

# 대표종목. 자비스4 카드가 쓰는 것과 같다.
STOCKS = (("005930", "삼성전자"), ("000660", "SK하이닉스"))

FIELDS = ("date", "close", "foreign_net", "institution_net")


def _read_existing(path: Path) -> dict:
    """이미 쌓아 둔 것을 날짜별로 읽는다. 없으면 빈 것."""
    if not path.exists():
        return {}
    saved = {}
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                date = (row.get("date") or "").strip()
                if date:
                    saved[date] = {key: row.get(key) for key in FIELDS}
    except Exception:
        # 파일 하나가 깨져도 오늘 것은 받아 둔다. 다만 덮어써서 날리지 않도록
        # 빈 것을 돌려주고, 아래에서 새 줄만 더한다.
        return {}
    return saved


def collect(*, export_dir=None, flow_fn=None, stocks=STOCKS) -> dict:
    """종목별 수급 줄을 받아 쌓아 둔 파일에 합친다.

    같은 날짜는 새로 받은 값으로 덮어쓴다 — 네이버가 잠정치를 나중에
    확정치로 고치는 경우가 있어서다. 날짜가 열쇠라 몇 번을 돌려도
    줄이 늘어나지 않는다.
    """
    if flow_fn is None:
        import jarvis4_data

        flow_fn = jarvis4_data.get_stock_flow

    folder = Path(export_dir or EXPORT_DIR)
    folder.mkdir(parents=True, exist_ok=True)

    added = kept = 0
    failures = []
    for code, label in stocks:
        try:
            flow = flow_fn(code) or {}
        except Exception as exc:
            failures.append(f"{label} 조회 실패: {exc}")
            continue
        rows = flow.get("rows") or []
        if not flow.get("ok") or not rows:
            failures.append(f"{label} 수급 줄 없음")
            continue

        path = folder / f"{code}.csv"
        saved = _read_existing(path)
        before = len(saved)
        for row in rows:
            date = str(row.get("date") or "").strip()
            if not date:
                continue
            saved[date] = {
                "date": date,
                "close": row.get("close"),
                "foreign_net": row.get("foreign_net"),
                "institution_net": row.get("institution_net"),
            }
        added += len(saved) - before
        kept += len(saved)

        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for date in sorted(saved):
                writer.writerow(saved[date])
        tmp.replace(path)

    return {"ok": not failures or kept > 0, "added": added, "total": kept,
            "failures": failures}


def load_history(code, *, source_dir=None) -> list[dict]:
    """쌓아 둔 것을 날짜 오름차순으로 돌려준다. 없으면 빈 목록."""
    path = Path(source_dir or EXPORT_DIR) / f"{str(code).strip()}.csv"
    saved = _read_existing(path)
    return [saved[date] for date in sorted(saved)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="종목별 하루치 수급 모으기")
    parser.add_argument("--export-dir", default=str(EXPORT_DIR))
    parser.add_argument("--allow-any-time", action="store_true",
                        help="장 마감 전에도 돌린다 (손으로 시험할 때만)")
    args = parser.parse_args(argv)

    now = datetime.now(_SEOUL)
    # 장 마감(15:30) 전에는 그날 줄이 아예 없다. 굳이 부르지 않는다.
    if now.hour < 16 and not args.allow_any_time:
        print(f"아직 장 마감 자료가 없습니다 ({now.strftime('%H:%M')}). "
              "종목별 당일 수급은 저녁에 올라옵니다.")
        return 0

    result = collect(export_dir=Path(args.export_dir))
    for line in result["failures"]:
        print(f"  ! {line}")
    print(f"새로 {result['added']}줄 · 모두 {result['total']}줄")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
