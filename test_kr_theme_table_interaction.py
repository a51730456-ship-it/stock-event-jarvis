import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from test_login_transition import _offline_market_stubs


ROOT = Path(__file__).parent
TEST_PASSWORD = "jarvis-theme-table-interaction-test"


def _socket_block():
    return patch.object(socket.socket, "connect", side_effect=AssertionError("external socket blocked"))


def _logged_in_app():
    """로그인하고, 이후 위젯 상호작용만 격리해서 테스트할 수 있도록 자동조회 단계를
    전부 완료 상태로 표시한 AppTest 인스턴스를 반환한다."""
    app = AppTest.from_file(ROOT / "app.py", default_timeout=60)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    with _socket_block(), _offline_market_stubs():
        app.run()
        app.radio[0].set_value("자비스1 (기록장)")
        app.text_input[0].set_value(TEST_PASSWORD)
        app.button[0].click().run(timeout=60)

    app.session_state["kr_auto_run_stage1_done"] = True
    app.session_state["kr_auto_run_stage2_done"] = True
    app.session_state["kr_auto_run_version"] = "2026-07-14-previous-close-v2"
    app.session_state["kr_theme_auto_fetch_pending"] = False
    app.session_state["kr_bookmaker_auto_fetch_pending"] = False
    app.session_state["parallel_warmup_done"] = True
    app.session_state["us_auto_run_stage1_done"] = True
    app.session_state["us_auto_run_stage2_done"] = True
    app.session_state["us_auto_run_version"] = "2026-07-15-v1"
    with _socket_block(), _offline_market_stubs():
        app.run(timeout=60)
    return app


class KrThemeTableClickSyncTests(unittest.TestCase):
    def test_clicking_a_theme_row_syncs_detail_selector_to_that_theme(self):
        # 2026-07-15 사용자 스크린샷: "전력기기/전력망" 행을 클릭했는데 체크 표시만
        # 바뀌고 "세부 입력할 테마 선택" 드롭다운과 "선택 테마 현재 상태"는 계속
        # "반도체/HBM"으로 남아있었다는 지적. 이 테스트로 실제 app.py 코드에서
        # 클릭이 정확히 동기화되는지 검증한다(단순화한 재현 스크립트가 아니라
        # 실제 _render_kr_theme_chip_editor 코드 경로를 그대로 실행).
        app = _logged_in_app()

        theme_df_widgets = [d for d in app.get("dataframe") if d.key == "kr_theme_table_df"]
        self.assertEqual(len(theme_df_widgets), 1, "테마 표 위젯(key=kr_theme_table_df)을 찾을 수 없음")
        table_value = theme_df_widgets[0].value
        clicked_theme_name = table_value["테마"].iloc[1]

        # st.dataframe에 key가 있으므로, 위젯 값은 session_state[key]에 저장된다.
        # 실제 클릭 시 프론트엔드가 보내는 것과 같은 모양의 선택 상태를 넣어
        # "1번 행을 클릭했다"를 재현한다.
        app.session_state["kr_theme_table_df"] = {
            "selection": {"rows": [1], "columns": [], "cells": []}
        }
        with _socket_block(), _offline_market_stubs():
            app.run(timeout=60)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.session_state.filtered_state.get("kr_theme_detail_selector"),
            clicked_theme_name,
            "표에서 클릭한 테마와 세부 입력 드롭다운 선택값이 일치해야 한다",
        )


if __name__ == "__main__":
    unittest.main()
