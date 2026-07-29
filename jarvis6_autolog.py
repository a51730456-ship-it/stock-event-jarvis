"""자비스6 자동 기록 — 매일 15:18에 사람 없이 그날 후보를 남긴다.

왜 만들었나 (2026-07-26 사용자 지시: "그냥 니가 자동으로 눌러라")
--------------------------------------------------------------
자비스1~4가 실패한 이유는 판단만 쌓이고 결과가 안 남아서였고, 그 원인은
**입력 마찰**이었다. 자비스6은 클릭 한 번으로 줄였지만 그 한 번도 매일
하기는 어렵다. 안 누르면 자료가 영영 0건이고, 0건이면 이 매매가 되는지
안 되는지 끝까지 모른다.

그래서 기계가 매일 남긴다. 사람은 아무것도 안 해도 자료가 쌓인다.

주의
----
- **주문이 아니다.** 종이에 적어 두는 것뿐이고 돈이 오가지 않는다.
- 남기는 것은 `is_good`을 통과한 것만이다. 화면에서 초록으로 보이는 것과
  같은 기준을 쓴다(기준은 jarvis6_data 한 곳에만 있다).
- 결과는 `data/jarvis6/YYYY-MM-DD.json`에 쌓는다. DB에 바로 넣지 않는다 —
  온라인과 노트북이 서로 다른 DB를 쓰기 때문이다. 화면이 열릴 때
  `jarvis6_store.import_auto_logs()`가 이 파일들을 DB로 들여온다.
- 저장소가 공개다. 여기 담기는 것은 공개 시세와 판정뿐이고 비밀은 없다.

쓰는 법

    python jarvis6_autolog.py --export-dir data/jarvis6
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jarvis6_data as j6

_SEOUL = ZoneInfo("Asia/Seoul")
EXPORT_DIR = Path("data/jarvis6")


def _slim(row: dict) -> dict:
    """파일에 담을 것만 남긴다. 차트 원본까지 넣으면 저장소가 불어난다."""
    metrics = row.get("metrics") or {}
    keep = ("current", "prev_close", "day_open", "day_high", "day_low",
            "from_high_pct", "high52_days_ago", "avg_trading_value",
            "volume_ratio", "change_pct", "ret5", "last_date", "day_is_today")
    return {
        "code": row.get("code"),
        "name": row.get("name"),
        "theme": row.get("theme"),
        "stock": row.get("stock") or {},
        "metrics": {k: metrics.get(k) for k in keep},
        "eval": row.get("eval") or {},
        "theme_row": {"advancers": (row.get("theme_row") or {}).get("advancers")},
    }


def collect(*, now: datetime | None = None, export_dir: Path | None = None,
            builder=None) -> dict:
    """오늘 후보를 재서 파일로 남긴다. 이미 있으면 덮어쓴다.

    덮어쓰는 이유: 하루에 두 번 돌아도 마지막 것 하나만 남아야 한다.
    같은 날 자료가 두 벌이면 나중에 성적이 두 배로 부풀어 보인다.
    """
    stamp = now or datetime.now(_SEOUL)
    build = builder or j6.build_candidates
    data = build()
    if not data.get("ok"):
        return {"ok": False, "error": data.get("error"), "saved": 0}

    good = [_slim(r) for r in data["rows"] if j6.is_good(r)]
    payload = {
        "trade_date": stamp.date().isoformat(),
        "decided_at": stamp.isoformat(timespec="seconds"),
        "phase": j6.market_phase(stamp)["label"],
        "rows": good,
    }

    target_dir = Path(export_dir or EXPORT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{payload['trade_date']}.json"
    # 쓰다 만 파일이 남지 않게 임시로 쓰고 옮긴다.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    tmp.replace(path)
    return {"ok": True, "saved": len(good), "path": str(path),
            "phase": payload["phase"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="자비스6 자동 기록")
    parser.add_argument("--export-dir", default=str(EXPORT_DIR))
    parser.add_argument("--allow-any-time", action="store_true",
                        help="장 시간이 아니어도 돌린다 (손으로 시험할 때만)")
    args = parser.parse_args(argv)

    now = datetime.now(_SEOUL)
    phase = j6.market_phase(now)
    # 15:20이 지난 자료를 15:18로 쓰면 검증이 아니라 속임수가 된다.
    # 예약 실행이 늦어 관찰 구간을 놓치면 **남기지 않는 쪽**이 맞다.
    if not phase["watching"] and not args.allow_any_time:
        print(f"관찰 구간이 아니라 남기지 않습니다 ({phase['label']}, "
              f"{now.strftime('%H:%M')}). 관찰 구간은 평일 14:30~15:18입니다.")
        return 0

    result = collect(now=now, export_dir=Path(args.export_dir))
    if not result["ok"]:
        print(f"후보를 못 냈습니다: {result.get('error')}")
        return 1
    print(f"{result['saved']}건 남겼습니다 → {result['path']} ({result['phase']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
