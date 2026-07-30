"""앱이 잠들었다 깨어나도 다시 안 받게 하는 공책(파일) 캐시.

2026-07-30 사용자 실측 — 순위 7이 처음 15초, 다시 누르면 빠른데 창을 닫았다
열면 또 15초. 메모리 캐시가 앱이 잠들 때 통째로 비워지기 때문이다.

여기서 지키는 것은 두 가지다.
  1. **무엇을 적는가** — 느리게 변하는 값(일봉·수급)만. 현재가·지수·분봉처럼
     지금 이 순간을 나타내는 값은 절대 적지 않는다.
  2. **언제 안 쓰는가** — 날짜가 바뀌면 안 쓴다. 어제 값을 오늘 값인 척 보여주지
     않기 위해서다.
"""

import pickle
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import jarvis4_data as j4


class WhatGetsWrittenTests(unittest.TestCase):
    def test_only_slow_moving_values_go_to_disk(self):
        self.assertEqual(("daily", "flow"), j4._DISK_CACHE_KINDS)
        # 지금 이 순간을 나타내는 값은 적히면 안 된다.
        for kind in ("index", "index_intraday", "minute", "market_representative_live_quotes",
                     "us_futures", "theme_list"):
            self.assertIsNone(j4._disk_cache_path((kind, "005930")),
                              f"'{kind}'은 공책에 적으면 안 된다")

    def test_path_is_built_from_a_safe_name(self):
        path = j4._disk_cache_path(("daily", "005930"))
        self.assertIsNotNone(path)
        self.assertEqual("daily__005930.pkl", path.name)
        # 경로를 벗어나게 만드는 글자는 지운다.
        sneaky = j4._disk_cache_path(("flow", "../../etc/passwd"))
        self.assertEqual("flow__etcpasswd.pkl", sneaky.name)

    def test_odd_keys_are_ignored(self):
        for key in ("daily", ("daily",), ("daily", "", "extra"), ("daily", "!!!"), 5):
            self.assertIsNone(j4._disk_cache_path(key))


class ReadWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path("cache") / "jarvis4_test"
        self.patcher = patch.object(j4, "_DISK_CACHE_DIR", self.temp)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(lambda: shutil.rmtree(self.temp, ignore_errors=True))

    def test_written_today_is_read_back(self):
        j4._disk_cache_write(("daily", "005930"), {"hello": 1})
        self.assertEqual({"hello": 1}, j4._disk_cache_read(("daily", "005930")))

    def test_yesterday_is_not_used(self):
        """어제 이동평균을 오늘 값인 척 보여주지 않는다."""
        j4._disk_cache_write(("daily", "005930"), {"hello": 1})
        path = j4._disk_cache_path(("daily", "005930"))
        stale = {"day": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                 "value": {"hello": 1}}
        with path.open("wb") as handle:
            pickle.dump(stale, handle)
        self.assertIsNone(j4._disk_cache_read(("daily", "005930")))

    def test_a_broken_file_is_treated_as_missing(self):
        """공책이 깨져도 화면이 죽으면 안 된다."""
        path = j4._disk_cache_path(("flow", "000660"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"this is not a pickle")
        self.assertIsNone(j4._disk_cache_read(("flow", "000660")))

    def test_writing_never_raises(self):
        with patch.object(j4, "_DISK_CACHE_DIR", Path("Z:/없는곳/그리고/더")):
            j4._disk_cache_write(("daily", "005930"), {"hello": 1})  # 예외가 나면 안 된다


class CacheFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path("cache") / "jarvis4_test_flow"
        self.patcher = patch.object(j4, "_DISK_CACHE_DIR", self.temp)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(lambda: shutil.rmtree(self.temp, ignore_errors=True))
        j4.clear_runtime_cache()
        self.addCleanup(j4.clear_runtime_cache)

    def test_waking_up_reads_the_notebook_instead_of_fetching_again(self):
        calls = []

        def producer():
            calls.append(1)
            return "받아온 값"

        first, stale = j4._cached(("daily", "005930"), 300, producer)
        self.assertEqual("받아온 값", first)
        self.assertFalse(stale)
        self.assertEqual(1, len(calls))

        # 앱이 잠들었다 깨어난 상황 — 메모리만 비고 공책은 남아 있다.
        j4.clear_runtime_cache()
        second, stale = j4._cached(("daily", "005930"), 300, producer)
        self.assertEqual("받아온 값", second)
        self.assertFalse(stale)
        self.assertEqual(1, len(calls), "공책이 있는데도 다시 받아 왔다")

    def test_values_not_on_the_list_still_refetch_after_waking(self):
        """현재가처럼 지금을 나타내는 값은 공책을 안 쓰므로 다시 받아야 한다."""
        calls = []

        def producer():
            calls.append(1)
            return "지금 값"

        j4._cached(("index", "KS11"), 300, producer)
        j4.clear_runtime_cache()
        j4._cached(("index", "KS11"), 300, producer)
        self.assertEqual(2, len(calls), "지금 값을 공책에서 꺼내 쓰면 안 된다")


class GitignoreTests(unittest.TestCase):
    def test_the_notebook_is_not_committed(self):
        """저장소는 공개다. 캐시 파일이 올라가면 안 된다.

        도는 값은 conftest가 임시 폴더로 돌려 두므로 소스에 적힌 자리를 본다.
        """
        ignored = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("cache/", ignored)
        source = Path("jarvis4_data.py").read_text(encoding="utf-8")
        self.assertIn('_DISK_CACHE_DIR = Path("cache") / "jarvis4"', source)


if __name__ == "__main__":
    unittest.main()
