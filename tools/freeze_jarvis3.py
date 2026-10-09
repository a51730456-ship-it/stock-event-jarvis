"""자비스3 지킴이 — 자비스3 화면 파일과 자비스3 이 쓰는 모든 파일의 지문을 적어 둔다 (2026-10-09 상하님 지시).

    python tools/freeze_jarvis3.py          (지금 상태를 jarvis3_frozen.json 에 적는다)

상하님 — *"미국테마는 예전에 수정을 하니 … 자꾸 되돌리기나 엄한 잘못을 해서 계속 나를 힘들게 해"* ·
*"자비스12 를 수정하면 자비스3 을 건들일까 싶어"*.

test_jarvis3_frozen 이 이 지문과 지금 파일을 견준다. 한 글자라도 바뀌면 시험이 실패한다.
**상하님이 자비스3 을 고치라고 하신 때에만** 고친 뒤 이 도구를 다시 돌려 지문을 새로 적는다.
자비스12 를 고치다 같이 쓰는 파일을 고쳐야 하면 — 그 파일을 고치지 말고 자비스12 전용 사본을 만든다.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = "pages/2_자비스3.py"
RECORD = ROOT / "jarvis3_frozen.json"


def closure(root: Path = ROOT) -> list:
    """자비스3 화면 파일 + 그것이 직접·간접으로 불러오는 이 저장소의 .py 파일(맨 위 폴더) 전부."""
    local = {path.stem for path in root.glob("*.py")}
    seen, todo = set(), [PAGE]
    while todo:
        tree = ast.parse((root / todo.pop()).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in local and name not in seen:
                    seen.add(name)
                    todo.append(f"{name}.py")
    return [PAGE] + sorted(f"{name}.py" for name in seen)


def fingerprint(path: Path) -> str:
    """줄 끝(윈도의 CRLF · 리눅스의 LF)은 같게 친다 — 노트북과 깃허브에서 지문이 갈리지 않게."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def current(root: Path = ROOT) -> dict:
    return {name: fingerprint(root / name) for name in closure(root)}


if __name__ == "__main__":
    data = current()
    RECORD.write_text(json.dumps({"files": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"자비스3 지킴이 — {len(data)}개 파일 지문을 적었다 → {RECORD.name}")
