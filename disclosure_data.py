"""Small, network-injectable OpenDART data client.

The public functions return ``{"status": ..., "data": ...}`` and never include
the API key in errors or diagnostic values.
"""

import io
import json
import re
import urllib.parse
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

TIMEOUT = 10
_DATE = re.compile(r"^\d{8}$")
_STATUSES = {"정상", "데이터 없음", "인증키 오류", "요청 제한", "서버 점검", "timeout·네트워크 오류", "ZIP·XML·JSON 형식 오류"}


def _get(url, http_get):
    if http_get is not None:
        try:
            return http_get(url, timeout=TIMEOUT)
        except TypeError:
            return http_get(url)
    req = urllib.request.Request(url, headers={"User-Agent": "stock-event-jarvis"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _body(response):
    if isinstance(response, (bytes, bytearray)):
        return bytes(response), 200
    status = getattr(response, "status", getattr(response, "status_code", 200))
    value = response.read() if hasattr(response, "read") else response
    return bytes(value), status


def _result(status, data=None, message=None, status_code=None):
    result = {"status": status, "data": data if data is not None else []}
    if message:
        result["message"] = message
    if status_code is not None:
        result["status_code"] = status_code
    return result


def _classify_error(raw, http_status=200):
    text = raw.decode("utf-8", "replace").lower()
    if http_status >= 500 or any(x in text for x in ("점검", "maintenance", "temporarily unavailable")):
        return "서버 점검"
    if any(x in text for x in ("인증", "api key", "apikey", "invalid key", "unauthorized")):
        return "인증키 오류"
    if any(x in text for x in ("제한", "limit", "too many", "429")):
        return "요청 제한"
    return None


def fetch_dart_corp_code_map(api_key, http_get=None):
    """Fetch a map of listed stock code to corp code/name."""
    if not api_key:
        return _result("인증키 오류", message="API key is required")
    url = "https://opendart.fss.or.kr/api/corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": api_key})
    try:
        raw, code = _body(_get(url, http_get))
        error = _classify_error(raw, code)
        if error:
            return _result(error)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml = archive.read("CORPCODE.xml")
        root = ET.fromstring(xml)
        result = {}
        for item in root.findall("list"):
            stock = (item.findtext("stock_code") or "").strip()
            corp = (item.findtext("corp_code") or "").strip()
            name = (item.findtext("corp_name") or "").strip()
            if stock and corp:
                result[stock] = {"corp_code": corp, "corp_name": name}
        return _result("정상", result)
    except (TimeoutError, OSError, urllib.error.URLError):
        return _result("timeout·네트워크 오류")
    except (zipfile.BadZipFile, KeyError, ET.ParseError, UnicodeError):
        return _result("ZIP·XML·JSON 형식 오류")


def fetch_recent_dart_disclosures(api_key, corp_code, start_date, end_date, http_get=None):
    """Fetch and deduplicate recent disclosures for a corporation."""
    if not api_key:
        return _result("인증키 오류", message="API key is required")
    if not (_DATE.fullmatch(start_date) and _DATE.fullmatch(end_date)) or start_date > end_date:
        return _result("데이터 없음", message="invalid date range")
    params = {"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": start_date, "end_de": end_date, "page_no": 1, "page_count": 100}
    url = "https://opendart.fss.or.kr/api/list.json?" + urllib.parse.urlencode(params)
    try:
        raw, code = _body(_get(url, http_get))
        error = _classify_error(raw, code)
        if error:
            return _result(error)
        payload = json.loads(raw.decode("utf-8"))
        api_status = str(payload.get("status", "000"))
        if api_status != "000":
            msg = str(payload.get("message", ""))
            status = _classify_error(msg.encode()) or ("데이터 없음" if api_status == "013" else "인증키 오류" if api_status in {"010", "011"} else "요청 제한" if api_status == "020" else "서버 점검" if api_status == "800" else "데이터 없음")
            return _result(status, status_code=api_status, message=msg or None)
        rows = payload.get("list") or []
        unique = {str(row.get("rcept_no")): row for row in rows if row.get("rcept_no")}
        data = sorted(unique.values(), key=lambda row: (row.get("rcept_dt", ""), row.get("rcept_no", "")), reverse=True)
        return _result("정상" if data else "데이터 없음", data, status_code="000")
    except (TimeoutError, OSError, urllib.error.URLError):
        return _result("timeout·네트워크 오류")
    except (json.JSONDecodeError, UnicodeError):
        return _result("ZIP·XML·JSON 형식 오류")
