"""자비스13(한국테마)이 다른 자비스와 섞이지 않는지 본다 (2026-10-30 상하님 「둘 다 해라」 · 「자비스4 와 자비스12 둘 다 장점을 베낌」).

자비스12 를 자비스3 에서 베낄 때(2026-10-09) 보관함 이름까지 같이 베껴져, 자비스12 에서 누른 결과가 자비스3 에 그대로
나왔다(2026-10-23 · 상하님 「자비스12 는 자비스3 과 연결하지 말고 별도로 · 다른 자비스도 연결하지 말라」).
2026-10-27 에는 단추 이름만 바꾸고 같이 쓰는 폰 규칙이 옛 이름을 봐서 폰 단추 모양이 깨졌다. 자비스13 은 처음부터 막는다.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
J4 = (ROOT / "pages" / "3_자비스4.py").read_text(encoding="utf-8")
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")

_STATE = re.compile(r"""(?:key\s*=\s*|session_state(?:\.get\(|\[|\.pop\(|\.setdefault\()\s*)f?["']([A-Za-z0-9_]+)""")


def _names(text: str) -> set:
    # f"btn_{key}" 처럼 앞머리만 글자인 것은 뒤가 화면마다 다른 이름이라 뺀다(앞머리만 남은 "btn_"·"close_")
    return {name for name in _STATE.findall(text) if not name.endswith("_")}


def _code_only(text: str) -> str:
    """설명 글(# 줄 끝 · /* */)을 뺀 코드 — 「미국 화면(j3_my_stock_query)과 같은 색」 같은 설명은 연결이 아니다."""
    import io
    import tokenize

    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.COMMENT:
            kept.append(tok.string)
    return re.sub(r"/\*.*?\*/", "", " ".join(kept), flags=re.S)


class Jarvis13SeparationTests(unittest.TestCase):
    def test_page_title_and_origin(self):
        self.assertIn('st.set_page_config(page_title="자비스13 — 한국테마", layout="wide")', PAGE)
        self.assertTrue(PAGE.startswith('"""자비스13 — 한국테마.'))
        self.assertIn("tools/build_jarvis13.py", PAGE)

    def test_no_jarvis4_box_names_left(self):
        # 꾸밈 이름(j4-…) · 계산 파일 이름(j4data · j4store)만 남는다
        left = set(re.findall(r"(?<![A-Za-z0-9])(j4[A-Za-z0-9_]*)(?![-A-Za-z0-9_])", PAGE)) - {"j4data", "j4store"}
        self.assertEqual(set(), left)
        self.assertGreater(len(re.findall(r"(?<![A-Za-z0-9])j13", PAGE)), 250)

    def test_not_connected_to_jarvis12_or_jarvis3_names(self):
        code = _code_only(PAGE)
        self.assertEqual([], re.findall(r"(?<![A-Za-z0-9])(j12[A-Za-z_][A-Za-z0-9_]*)", code))
        self.assertEqual([], re.findall(r"(?<![A-Za-z0-9])(j3(?:_|b_|add_|rb|vx_|sc_)[A-Za-z0-9_]*)", code))

    def test_box_names_do_not_overlap_with_jarvis4_or_jarvis12(self):
        # 같이 써야 하는 것 — 로그인 · 한국 시장 수급 카드가 담아 두는 값(market_signal_ui · 읽기만 · 화면과 상관없이 같은 값)
        shared_ok = {"authenticated", "kr_flow_result"}
        mine = _names(PAGE)
        self.assertEqual(set(), (mine & _names(J4)) - shared_ok)
        self.assertEqual(set(), (mine & _names(J12)) - shared_ok)

    def test_shared_state_helpers_are_jarvis13_copies(self):
        tree = ast.parse(PAGE)
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name] = alias.name
        self.assertEqual("jarvis13_scroll_to", imports.get("scroll_to"))
        self.assertEqual("jarvis13_back_nav", imports.get("back_nav"))
        self.assertEqual("jarvis13_picklist_ui", imports.get("jarvis13_picklist_ui"))
        self.assertNotIn("picklist_ui.render(", PAGE.replace("jarvis13_picklist_ui.render(", ""))
        self.assertEqual(2, PAGE.count('jarvis13_picklist_ui.render(st, "KR"'))

    def test_copies_use_jarvis13_names(self):
        import jarvis13_back_nav
        import jarvis13_picklist_ui
        import jarvis13_scroll_to

        self.assertEqual("_j13_backnav_open", jarvis13_back_nav._STACK)
        self.assertEqual("j13_scroll_target", jarvis13_scroll_to.REQUEST_KEY)
        self.assertEqual("j13_scroll_seq", jarvis13_scroll_to.COUNTER_KEY)
        self.assertEqual("j13_picklist_archive_open_KR", jarvis13_picklist_ui.open_key("KR"))
        self.assertEqual("j13_picklist_picked_KR", jarvis13_picklist_ui.pick_key("KR"))
        self.assertEqual("j13_picklist_date_", jarvis13_picklist_ui.DATE_KEY_PREFIX)
        self.assertIn("j13_picklist_archive_open", jarvis13_picklist_ui.CSS)
        self.assertIn("__jarvis13NoKeyboard", jarvis13_picklist_ui._KEYBOARD_SCRIPT)
        self.assertIn("st-key-j13_picklist_date_", jarvis13_picklist_ui._KEYBOARD_SCRIPT)
        body = (ROOT / "jarvis13_picklist_ui.py").read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertEqual([], re.findall(r"(?<![A-Za-z0-9])j12[_A-Za-z]", body))

    def test_menu_lists_it_on_pc_only_and_keeps_phone_straight_to_jarvis12(self):
        start = APP.index("_ALL_DEST_OPTIONS = [")
        options = ast.literal_eval(APP[start:].split("=", 1)[1].split("]\n", 1)[0] + "]")
        keys = ast.literal_eval(APP[APP.index("_DEST_KEYS = ["):].split("=", 1)[1].split("]", 1)[0] + "]")
        self.assertEqual("한국테마 (자비스13)", options[-1])       # 맨 끝 — 폰 숨김 줄 번호가 안 밀린다
        self.assertEqual(len(options), len(keys))
        self.assertEqual("한국테마", keys[-1])
        pages = APP[APP.index("_DEST_PAGES = {"):]
        self.assertLess(pages.index('"한국테마 (자비스13)": "pages/12_자비스13.py"'), pages.index('"한국테마": "pages/3_자비스4.py"'))
        phone = APP[APP.index("_PHONE_DEST_OPTIONS = ("):].split(")", 1)[0]
        self.assertNotIn("자비스13", phone)


if __name__ == "__main__":
    unittest.main()
