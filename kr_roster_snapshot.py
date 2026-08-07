"""자비스4 화면이 실제로 뒤지는 명부를 한 번 찍어 파일로 남긴다 (2026-08-07).

**왜 필요한가.** 한국 배점을 다시 재려면 '무엇으로 재느냐'부터 정해야 한다.
미국(자비스3)은 명부가 코드에 박혀 있어(US_THEMES 20테마·198종목) 그대로 쓰면
되지만, 자비스4는 네이버 테마를 그때그때 긁어 오므로 **명부가 날마다 바뀐다.**
잰 대상과 화면이 찾는 대상이 다르면 화면이 거짓말을 한다(2026-08-06 미국에서
실제로 겪었다 — 나스닥100 96종목으로 잰 숫자를 테마 198종목 화면에 붙여 뒀다).

그래서 오늘의 명부를 한 번 찍어 두고, 그것으로 12년치를 잰다. 찍은 날짜와 종목
수를 파일에 같이 적어 둔다 — 나중에 "무엇으로 잰 숫자냐"를 답할 수 있어야 한다.

쓰는 법:  python kr_roster_snapshot.py
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

import jarvis4_data as j4


OUT = pathlib.Path(__file__).resolve().parent / "data" / "kr_roster.json"


def main() -> None:
    universe = j4.get_theme_universe(ttl_seconds=0)
    if not universe.get("ok"):
        raise SystemExit(f"명부를 받지 못했습니다: {universe.get('error')}")
    stocks = universe["stocks"]
    rows = {
        code: {"name": entry.get("name"), "themes": list(entry.get("themes") or [])}
        for code, entry in sorted(stocks.items())
    }
    theme_names: set[str] = set()
    for entry in rows.values():
        theme_names.update(entry["themes"])
    payload = {
        "captured_at": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M"),
        "theme_count": universe.get("theme_count"),
        "stock_count": len(rows),
        "stocks": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"테마 {payload['theme_count']}개 · 종목 {payload['stock_count']}개")
    print(f"종목이 속한 테마 이름 {len(theme_names)}가지")
    counts = sorted((len(v["themes"]) for v in rows.values()), reverse=True)
    print(f"한 종목이 속한 테마 수 — 가장 많은 것 {counts[0]}개 · 가운데 {counts[len(counts) // 2]}개")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
