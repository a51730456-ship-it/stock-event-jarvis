"""자비스4 지킴이 — 자비스4 화면 파일과 자비스4 가 쓰는 모든 파일의 지문을 적어 둔다 (2026-10-30 상하님 「둘 다 해라」).

    python tools/freeze_jarvis4.py          (지금 상태를 jarvis4_frozen.json 에 적는다)

한국테마는 이제 자비스4 를 베낀 **자비스13**(pages/12_자비스13.py)에서 고친다 — 자비스3 → 자비스12 와 같은 방식이다.
test_jarvis4_frozen 이 이 지문과 지금 파일을 견준다. 한 글자라도 바뀌면 시험이 실패한다.
**상하님이 자비스4 를 고치라고 하신 때에만** 고친 뒤 이 도구를 다시 돌려 지문을 새로 적는다.
자비스13 을 고치다 같이 쓰는 파일을 고쳐야 하면 — 그 파일을 고치지 말고 자비스13 전용 사본(jarvis13_*.py)을 만든다.
고르는 법은 tools/freeze_jarvis3.py 와 같다(화면 + 직접·간접으로 불러오는 이 저장소 맨 위 폴더의 .py 전부).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import freeze_jarvis3  # noqa: E402  — 고르는 법·지문 만드는 법을 그대로 쓴다

PAGE = "pages/3_자비스4.py"
RECORD = ROOT / "jarvis4_frozen.json"


def closure(root: Path = ROOT) -> list:
    """자비스4 화면 파일 + 그것이 직접·간접으로 불러오는 이 저장소의 .py 파일(맨 위 폴더) 전부."""
    saved = freeze_jarvis3.PAGE
    try:
        freeze_jarvis3.PAGE = PAGE
        return freeze_jarvis3.closure(root)
    finally:
        freeze_jarvis3.PAGE = saved


def current(root: Path = ROOT) -> dict:
    return {name: freeze_jarvis3.fingerprint(root / name) for name in closure(root)}


if __name__ == "__main__":
    data = current()
    RECORD.write_text(json.dumps({"files": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"자비스4 지킴이 — {len(data)}개 파일 지문을 적었다 → {RECORD.name}")
