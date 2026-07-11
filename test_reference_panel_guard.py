import ast
import functools
import unittest
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
GUARD_NODE = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == "_reference_panel_guard")


class _StreamlitStub:
    def __init__(self):
        self.messages = []

    def warning(self, message):
        self.messages.append(message)


class _LoggerStub:
    def __init__(self):
        self.calls = []

    def error(self, *args, **kwargs):
        self.calls.append(("error", args, kwargs))

    def exception(self, *args, **kwargs):
        self.calls.append(("exception", args, kwargs))


class ReferencePanelGuardTests(unittest.TestCase):
    def _load_guard(self, modules):
        st = _StreamlitStub()
        logger = _LoggerStub()
        namespace = {
            "functools": functools,
            "globals": lambda: modules,
            "st": st,
            "_reference_panel_logger": logger,
        }
        exec(compile(ast.Module(body=[GUARD_NODE], type_ignores=[]), "app.py", "exec"), namespace)
        return namespace["_reference_panel_guard"], st, logger

    def test_missing_function_shows_restart_notice(self):
        guard, st, logger = self._load_guard({"news_data": object()})

        @guard("시장 뉴스", (("news_data", "fetch_naver_news"),), "뉴스 실패")
        def panel():
            raise AssertionError("must not run")

        self.assertIsNone(panel())
        self.assertIn("Streamlit을 완전히 종료한 뒤 다시 실행하세요", st.messages[0])
        self.assertEqual(logger.calls[0][0], "error")

    def test_unexpected_error_is_panel_scoped_and_not_raw_ui(self):
        class Module:
            def fetch_naver_news(self):
                return None

        guard, st, logger = self._load_guard({"news_data": Module()})

        @guard("시장 뉴스", (("news_data", "fetch_naver_news"),), "현재 뉴스 조회에 실패했습니다.")
        def panel():
            raise RuntimeError("https://secret.example/?key=SECRET")

        panel()
        self.assertEqual(st.messages, ["현재 뉴스 조회에 실패했습니다."])
        self.assertNotIn("SECRET", " ".join(st.messages))
        self.assertEqual(logger.calls[0][0], "exception")

    def test_guard_contract_and_no_reload(self):
        self.assertIn("error_type=%s", SOURCE)
        self.assertIn("현재 공시 조회에 실패했습니다. 잠시 후 다시 시도하세요.", SOURCE)
        self.assertIn("현재 뉴스 조회에 실패했습니다. 잠시 후 다시 시도하세요.", SOURCE)
        self.assertNotIn("importlib.reload", SOURCE)


if __name__ == "__main__":
    unittest.main()
