import io
import json
import logging
import unittest
import urllib.error
import zipfile

import disclosure_data as d


def response(value, status=200):
    class R:
        def read(self):
            return value
    R.status = status
    return R()


def corp_zip(xml=None, filename="CORPCODE.xml"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        if xml is not None:
            archive.writestr(filename, xml)
    return out.getvalue()


class DisclosureTests(unittest.TestCase):
    def test_corp_zip_xml_excludes_unlisted_and_preserves_six_digits(self):
        xml = b"""<result><list><corp_code>001</corp_code><corp_name>A</corp_name><stock_code>012345</stock_code></list>
        <list><corp_code>002</corp_code><corp_name>Private</corp_name><stock_code></stock_code></list></result>"""
        result = d.fetch_dart_corp_code_map("SECRET", lambda *a, **k: response(corp_zip(xml)))
        self.assertEqual(result["status"], "정상")
        self.assertEqual(result["data"], {"012345": {"corp_code": "001", "corp_name": "A"}})

    def test_bad_zip_missing_xml_and_bad_xml(self):
        for payload in (b"not zip", corp_zip(b"<result/>", "OTHER.xml"), corp_zip(b"<broken>")):
            self.assertEqual(
                d.fetch_dart_corp_code_map("SECRET", lambda *a, p=payload, **k: response(p))["status"],
                "ZIP·XML·JSON 형식 오류",
            )

    def test_normal_disclosures_status_and_raw_code(self):
        payload = {"status": "000", "message": "정상", "list": [{"rcept_no": "1", "rcept_dt": "20240102"}]}
        result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", lambda *a, **k: response(json.dumps(payload).encode()))
        self.assertEqual(result["status"], "정상")
        self.assertEqual(result["status_code"], "000")
        self.assertEqual(result["data"][0]["rcept_no"], "1")

    def test_no_data_and_dedup_latest_first(self):
        rows = [{"rcept_no": "2", "rcept_dt": "20240102"}, {"rcept_no": "1", "rcept_dt": "20240103"}, {"rcept_no": "2", "rcept_dt": "20240102"}]
        get = lambda *a, **k: response(json.dumps({"status": "000", "list": rows}).encode())
        result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", get)
        self.assertEqual([x["rcept_no"] for x in result["data"]], ["1", "2"])
        empty = lambda *a, **k: response(b'{"status":"013","message":"No data"}')
        result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", empty)
        self.assertEqual((result["status"], result["status_code"]), ("데이터 없음", "013"))

    def test_date_validation_and_empty_key_do_not_call(self):
        def fail(*args, **kwargs):
            raise AssertionError("http_get called")
        for args in (("20240201", "20240101"), ("2024-01-01", "20240101"), ("20240101", "2024-01-31")):
            self.assertEqual(d.fetch_recent_dart_disclosures("SECRET", "001", *args, http_get=fail)["status"], "데이터 없음")
        self.assertEqual(d.fetch_recent_dart_disclosures("", "001", "20240101", "20240131", fail)["status"], "인증키 오류")
        self.assertEqual(d.fetch_dart_corp_code_map("", fail)["status"], "인증키 오류")

    def test_api_error_codes(self):
        for code, expected in (("010", "인증키 오류"), ("011", "인증키 오류"), ("020", "요청 제한"), ("800", "서버 점검")):
            result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", lambda *a, c=code, **k: response(json.dumps({"status": c, "message": "safe"}).encode()))
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["status_code"], code)
            self.assertNotIn("SECRET", repr(result))

    def test_timeout_network_json_and_unexpected_errors(self):
        for error in (TimeoutError(), urllib.error.URLError("offline")):
            result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", lambda *a, e=error, **k: (_ for _ in ()).throw(e))
            self.assertEqual(result["status"], "timeout·네트워크 오류")
        bad = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", lambda *a, **k: response(b"not json"))
        self.assertEqual(bad["status"], "ZIP·XML·JSON 형식 오류")

    def test_timeout_is_passed_and_secret_is_not_logged_or_returned(self):
        seen = {}
        def get(url, **kwargs):
            seen.update(kwargs)
            return response(b'{"status":"013","message":"no data"}')
        result = d.fetch_recent_dart_disclosures("SECRET", "001", "20240101", "20240131", get)
        self.assertEqual(seen["timeout"], d.TIMEOUT)
        self.assertNotIn("SECRET", repr(result))
        self.assertNotIn("SECRET", "".join(logging.Logger.manager.loggerDict))


if __name__ == "__main__":
    unittest.main()
