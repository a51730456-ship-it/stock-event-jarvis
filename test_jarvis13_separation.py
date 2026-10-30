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
        # 얼린 mobile_ui 폰 규칙의 옛 이름을 자비스13 이름으로 바꿔 끼우는 두 줄만은 옛 이름이 있어야 한다(2026-10-30 성적표)
        code = _code_only(PAGE).replace('"st-key-j3sc_"', "").replace('"st-key-j3vx_"', "")
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


class OldScreenClosedTests(unittest.TestCase):
    """2026-10-30 상하님 — 「당연히 자비스13으로 연결되어야지 · 그전 한국테마는 중지시켜야지」.

    「한국테마」 이름표는 자비스13 이 쓰고 옛 자비스4 는 「자비스4」 이름표로 닫는다(page_access.OPEN_PAGES 는 그대로라
    온라인에 옛 page_access 가 남아도 열고 닫는 것이 어긋나지 않는다). 한국테마로 가는 길 셋을 모두 자비스13 으로 돌린다.
    """

    def test_jarvis13_is_open_and_jarvis4_is_closed(self):
        import page_access

        self.assertTrue(page_access.is_open("한국테마"))
        self.assertFalse(page_access.is_open("자비스4"))
        self.assertIn("자비스4", page_access.ALL_PAGES)                 # 되살릴 이름은 남긴다
        self.assertIn('page_access.guard(st, "한국테마")', PAGE)
        self.assertIn('page_access.guard(st, "자비스4")', J4)
        for source in (PAGE, J4):                                       # 맨 앞 — 화면 설정 바로 다음
            self.assertLess(source.index("st.set_page_config("), source.index("page_access.guard(st,"))

    def test_menu_keys_point_the_korean_theme_at_jarvis13(self):
        start = APP.index("_ALL_DEST_OPTIONS = [")
        options = ast.literal_eval(APP[start:].split("=", 1)[1].split("]\n", 1)[0] + "]")
        keys = ast.literal_eval(APP[APP.index("_DEST_KEYS = ["):].split("=", 1)[1].split("]", 1)[0] + "]")
        key_of = dict(zip(options, keys))
        self.assertEqual("자비스4", key_of["한국테마 (자비스4)"])
        self.assertEqual("한국테마", key_of["한국테마 (자비스13)"])
        nav = APP[APP.index("_NAV_PATHS = {"):]
        self.assertIn('"한국테마": "자비스13"', nav[:nav.index("}")])
        self.assertIn('"자비스4": "자비스4"', nav[:nav.index("}")])

    def test_the_three_roads_to_the_korean_theme_go_to_jarvis13(self):
        import login_prism
        import method_help

        # ① 자비스12 맨 위 「🌏 한국테마 →」 (자비스12 파일은 안 고치고 같이 쓰는 주소표 한 줄만 바꾼다)
        self.assertEqual(("pages/12_자비스13.py", "🌏 한국테마 →"), method_help.CROSS_PAGES["US"])
        # ② 자비스13 맨 위 「🌎 미국테마 →」 는 그대로 자비스12
        self.assertEqual("pages/11_자비스12.py", method_help.CROSS_PAGES["KR"][0])
        # ③ 첫 화면 PC 오른쪽 큰 판
        panels = {row[0]: row for row in login_prism.PANELS}
        self.assertEqual("pages/12_자비스13.py", panels["KR"][1])
        self.assertEqual("pages/11_자비스12.py", panels["US"][1])
        # 폰·태블릿 판과 판 번호는 그대로(자비스12 시험이 묶어 둔 값 — 자비스12 는 손대지 않는다)
        self.assertEqual("pages/11_자비스12.py", login_prism.PHONE_PANELS["KR"][0])
        self.assertEqual(2026100901, login_prism.MODULE_REVISION)

    def test_the_cross_button_hides_only_when_the_korean_theme_is_closed(self):
        source = (ROOT / "method_help.py").read_text(encoding="utf-8")
        names = source[source.index("def cross_link("):]
        self.assertIn('"pages/12_자비스13.py": "한국테마"', names)
        self.assertIn('"pages/3_자비스4.py": "자비스4"', names)

    def test_old_shared_tables_are_read_again_before_use(self):
        # 주소표(method_help · login_prism)는 번호를 안 올렸다 — 올리면 자비스12 · 자비스3 의 요구 번호까지 고쳐야 한다.
        # 그래서 옛 표가 서버에 남아 있으면 자비스13 · 자비스4 가 다시 읽는다(옛 표로 자비스4 에 오면 거기서 고쳐 둔다).
        for source in (PAGE, J4):
            self.assertIn('!= "pages/12_자비스13.py":\n    method_help = ', source)
            self.assertIn('!= "pages/12_자비스13.py":\n    login_prism = ', source)


if __name__ == "__main__":
    unittest.main()
