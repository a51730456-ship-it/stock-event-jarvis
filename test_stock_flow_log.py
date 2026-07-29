"""종목별 하루치 수급 쌓기 테스트.

여기서 지키려는 것.
1) 네이버에서 **사라진 옛 줄이 살아남는다** — 이게 이 파일의 존재 이유다
   (네이버는 20거래일치만 준다)
2) 다시 받아도 줄이 늘지 않는다 — 늘면 나중에 성적이 부풀어 보인다
3) 잠정치가 확정치로 바뀌면 새 값으로 덮어쓴다
4) 한 종목이 실패해도 나머지는 쌓인다
5) 장 마감 전에는 부르지 않는다 (그날 줄이 아예 없다)
"""

import tempfile
import unittest
from pathlib import Path

import stock_flow_log as log


def _rows(*items):
    return {"ok": True, "rows": [
        {"date": d, "close": c, "foreign_net": f, "institution_net": i}
        for d, c, f, i in items
    ]}


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.out = Path(self.tempdir.name) / "flow"
        self.one = (("005930", "삼성전자"),)

    def tearDown(self):
        self.tempdir.cleanup()

    def _collect(self, payload, stocks=None):
        return log.collect(export_dir=self.out, stocks=stocks or self.one,
                           flow_fn=lambda code: payload)

    def test_old_rows_survive_after_naver_drops_them(self):
        """네이버는 20거래일치만 준다. 밀려난 줄이 사라지면 안 된다."""
        self._collect(_rows(("2026.06.30", 1, 10, 20), ("2026.07.01", 2, 30, 40)))
        # 다음 날 네이버가 06.30을 빼고 07.02를 새로 줬다고 하자.
        self._collect(_rows(("2026.07.01", 2, 30, 40), ("2026.07.02", 3, 50, 60)))
        dates = [row["date"] for row in log.load_history("005930", source_dir=self.out)]
        self.assertEqual(dates, ["2026.06.30", "2026.07.01", "2026.07.02"])

    def test_collecting_twice_does_not_add_rows(self):
        payload = _rows(("2026.07.28", 220000, -6554668, -635592))
        self._collect(payload)
        second = self._collect(payload)
        self.assertEqual(second["added"], 0)
        self.assertEqual(len(log.load_history("005930", source_dir=self.out)), 1)

    def test_revised_number_overwrites_the_old_one(self):
        """네이버가 잠정치를 확정치로 고치는 경우가 있다."""
        self._collect(_rows(("2026.07.28", 220000, -1000, -2000)))
        self._collect(_rows(("2026.07.28", 220000, -6554668, -635592)))
        history = log.load_history("005930", source_dir=self.out)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["foreign_net"], "-6554668")

    def test_one_stock_failing_does_not_stop_the_other(self):
        def flow(code):
            if code == "005930":
                raise RuntimeError("조회 실패")
            return _rows(("2026.07.28", 1, 2, 3))

        result = log.collect(export_dir=self.out, flow_fn=flow,
                             stocks=(("005930", "삼성전자"), ("000660", "SK하이닉스")))
        self.assertTrue(result["failures"])
        self.assertEqual(len(log.load_history("000660", source_dir=self.out)), 1)

    def test_empty_result_is_not_written_as_an_empty_file(self):
        """줄이 없다고 빈 파일을 쓰면 쌓아 둔 것이 날아간다."""
        self._collect(_rows(("2026.07.28", 1, 2, 3)))
        log.collect(export_dir=self.out, stocks=self.one,
                    flow_fn=lambda code: {"ok": False, "rows": []})
        self.assertEqual(len(log.load_history("005930", source_dir=self.out)), 1)

    def test_history_of_unknown_code_is_empty(self):
        self.assertEqual(log.load_history("999999", source_dir=self.out), [])


class ScheduleTests(unittest.TestCase):
    def test_does_not_run_before_market_close(self):
        """장 마감 전에는 그날 줄이 아예 없다. 굳이 부르지 않는다."""
        import unittest.mock as mock
        with mock.patch.object(log, "collect") as collect:
            with mock.patch.object(log, "datetime") as clock:
                clock.now.return_value.hour = 12
                clock.now.return_value.strftime.return_value = "12:00"
                self.assertEqual(log.main([]), 0)
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
