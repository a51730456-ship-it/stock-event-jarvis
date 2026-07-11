import io
import unittest
import zipfile

import disclosure_data as d


def response(value, status=200):
    class R:
        def read(self): return value
    R.status = status
    return R()


class DisclosureTests(unittest.TestCase):
    def test_corp_zip_and_bad_zip_xml(self):
        xml = b'<result><list><corp_code>001</corp_code><corp_name>A</corp_name><stock_code>123456</stock_code></list><list><corp_code>002</corp_code><corp_name>B</corp_name><stock_code></stock_code></list></result>'
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z: z.writestr('CORPCODE.xml', xml)
        self.assertEqual(d.fetch_dart_corp_code_map('SECRET', lambda *a, **k: response(out.getvalue()))['data']['123456']['corp_code'], '001')
        self.assertEqual(d.fetch_dart_corp_code_map('SECRET', lambda *a, **k: response(b'bad'))['status'], 'ZIP·XML·JSON 형식 오류')

    def test_disclosures_dedup_sort_and_empty(self):
        payload = {'status':'000','list':[{'rcept_no':'2','rcept_dt':'20240102'},{'rcept_no':'1','rcept_dt':'20240103'},{'rcept_no':'2','rcept_dt':'20240102'}]}
        get = lambda *a, **k: response(__import__('json').dumps(payload).encode())
        result = d.fetch_recent_dart_disclosures('SECRET','001','20240101','20240131',get)
        self.assertEqual([x['rcept_no'] for x in result['data']], ['1','2'])
        self.assertEqual(d.fetch_recent_dart_disclosures('SECRET','001','20240201','20240131',get)['status'], '데이터 없음')
        self.assertEqual(d.fetch_recent_dart_disclosures('SECRET','001','bad','20240131',get)['status'], '데이터 없음')

    def test_error_states_and_key_not_exposed(self):
        for body, expected in [(b'{"status":"020","message":"bad key"}', '인증키 오류'), (b'{"status":"021"}', '요청 제한'), (b'{"status":"800"}', '서버 점검'), (b'no-json', 'ZIP·XML·JSON 형식 오류')]:
            result = d.fetch_recent_dart_disclosures('SECRET','001','20240101','20240131',lambda *a, **k: response(body))
            self.assertEqual(result['status'], expected)
            self.assertNotIn('SECRET', repr(result))
        self.assertEqual(d.fetch_recent_dart_disclosures('SECRET','001','20240101','20240131',lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))['status'], 'timeout·네트워크 오류')


if __name__ == '__main__': unittest.main()
