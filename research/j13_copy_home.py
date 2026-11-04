# -*- coding: utf-8 -*-
"""자비스12 관심종목(홈) 꾸밈 규칙을 글자 그대로 베껴 자비스13 용 파일(jarvis13_home_css.py)을 만든다
(2026-11-04 상하님 「관심종목도 미국테마 그대로 따라 만들어라」).

자비스12 화면 파일(pages/11_자비스12.py)은 **읽기만** 한다. 파이썬 문법 나무(ast)로 꾸밈 덩어리를 그대로 꺼내
이름만 바꾼다 — j3b- → j13h- · j12b → j13h (자비스13 의 다른 이름 j13b · j13w 와 안 겹치게 h). 같은 브라우저에서
자비스12 관심종목과 섞이지 않는다(CLAUDE.md 0-3 ⑤). 값 · 계산은 없다 — 보여 주는 모양만이다.

자비스12 관심종목 모양이 바뀌면 이 도구를 다시 돌려 jarvis13_home_css.py 를 새로 만든다(한국 색 바꿈은 jarvis13_home.py 에 따로).
쓰는 법: python research/j13_copy_home.py
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pages" / "11_자비스12.py"
TARGET = ROOT / "jarvis13_home_css.py"
CONSTANTS = ("_J3B_HOME_CSS", "_BRIEFING_OPEN_CSS", "_BRIEFING_TABLET_CSS", "_BRIEFING_GESTURE_CSS", "_BRIEFING_TOUCH_CSS",
             "_J3B_POP_CLOSE",
             "_J12B_CROSS_CSS")
# 베낀 꾸밈을 다시 만들면 올린다 — jarvis13_home 의 REQUIRED_CSS_REVISION 도 같이(옛 모듈이 남으면 다시 읽게 · CLAUDE.md 11).
REVISION = 2026110403
RENAMES = (("j3b-", "j13h-"), ("j12b_", "j13h_"), ("j12b-", "j13h-"), ("j3bPop", "j13hPop"))


def rename(text: str) -> str:
    for old, new in RENAMES:
        text = text.replace(old, new)
    return text


def extract() -> dict:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in CONSTANTS:
            out[node.targets[0].id] = ast.literal_eval(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == "_briefing_css":
            blocks = [sub.args[0].value for sub in ast.walk(node)
                      if isinstance(sub, ast.Call) and getattr(sub.func, "attr", "") == "markdown"
                      and sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str)]
            out["_BRIEFING_CSS"] = blocks
    missing = [name for name in CONSTANTS + ("_BRIEFING_CSS",) if name not in out]
    if missing:
        raise SystemExit(f"자비스12 에서 못 찾음: {missing}")
    return out


def main() -> int:
    found = extract()
    lines = [
        '"""자비스13 관심종목 꾸밈 — 자비스12 관심종목 꾸밈을 **글자 그대로** 베낀 것(이름만 j13h). 손으로 고치지 않는다.',
        "",
        "research/j13_copy_home.py 가 pages/11_자비스12.py 에서 만든다(2026-11-04 상하님 「관심종목도 미국테마 그대로 따라 만들어라」).",
        '한국 색(오름 빨강 · 내림 파랑) 같은 다른 점은 jarvis13_home.py 의 KR_CSS 에 따로 둔다."""',
        "",
        f"MODULE_REVISION = {REVISION}",
        f"BRIEFING_CSS = {json.dumps([rename(block) for block in found['_BRIEFING_CSS']], ensure_ascii=False)}",
    ]
    for name in CONSTANTS:
        lines.append(f"{name.lstrip('_').replace('J3B_', 'J13H_').replace('J12B_', 'J13H_')} = {json.dumps(rename(found[name]), ensure_ascii=False)}")
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"만듦: {TARGET.name} · 덩어리 {len(found['_BRIEFING_CSS'])}+{len(CONSTANTS)} · {TARGET.stat().st_size:,} 바이트")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
