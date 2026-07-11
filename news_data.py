"""Mockable Naver News Search client used by the read-only news feature later."""

import email.utils
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import timezone

TIMEOUT = 10
ENDPOINT = "https://openapi.naver.com/v1/search/news.json"
_TAG_RE = re.compile(r"<[^>]*>")

_MATERIALITY_RULES = (
    ("실적", ("실적", "매출", "영업이익", "순이익", "흑자", "적자", "전망", "가이던스")),
    ("수주·계약", ("수주", "공급계약", "계약 체결", "납품", "공급", "선정")),
    ("투자·M&A", ("투자", "인수", "합병", "매각", "분할", "증설")),
    ("주주환원·자본", ("배당", "자사주", "유상증자", "무상증자", "감자", "최대주주", "지분")),
    ("규제·법적위험", ("조사", "제재", "소송", "리콜", "사고", "횡령", "배임", "압수수색")),
    ("제품·기술", ("출시", "승인", "특허", "개발", "양산")),
)


def _result(status, status_code, data=None, message=""):
    return {
        "status": status,
        "status_code": str(status_code),
        "data": data if data is not None else [],
        "message": message,
    }


def _clean_text(value):
    return html.unescape(_TAG_RE.sub("", str(value or ""))).strip()


def classify_news_materiality(news_item, company_name, ticker=""):
    """Classify a news item by explicit keywords without inferring direction."""
    title = str(news_item.get("title") or "")
    description = str(news_item.get("description") or "")
    def matches(text):
        found = []
        for category, keywords in _MATERIALITY_RULES:
            for keyword in keywords:
                if keyword == "공급" and "공급계약" not in text and not any(
                    context in text for context in ("계약", "납품", "수주")
                ):
                    continue
                if keyword in text:
                    found.append((category, keyword, text.find(keyword)))
        return found

    title_matches = matches(title)
    description_matches = matches(description)
    chosen_matches = title_matches or description_matches
    if not chosen_matches:
        return {"level": "일반 참고", "category": "기타", "matched_keywords": [], "reason": "제목·설명에 중요 재료 키워드가 없습니다."}

    # 제목에 여러 범주가 있으면 고정된 우선순위를 사용해 배열 순서 의존을 피한다.
    category = next(category for category, _ in _MATERIALITY_RULES if any(match[0] == category for match in chosen_matches))
    matches = []
    for _, keyword, _ in sorted(chosen_matches, key=lambda match: (match[2], match[1])):
        if keyword not in matches:
            matches.append(keyword)
    field_name = "제목" if title_matches else "설명"
    return {
        "level": "중요 재료",
        "category": category,
        "matched_keywords": matches,
        "reason": f"{field_name}에서 {', '.join(matches)} 키워드가 일치했습니다.",
    }


def _normalize_pub_date(value):
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(str(value))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.isoformat(sep=" ")
    except (TypeError, ValueError, OverflowError):
        return str(value).strip()


def _read_response(response):
    status_code = getattr(response, "status", getattr(response, "status_code", 200))
    body = response.read() if hasattr(response, "read") else response
    return bytes(body), int(status_code)


def _request(url, headers, http_get):
    if http_get is not None:
        return http_get(url, headers=headers, timeout=TIMEOUT)
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def _http_status_result(status_code):
    if status_code in (401, 403):
        return "인증 오류"
    if status_code == 429:
        return "요청 제한"
    if 400 <= status_code < 500:
        return "잘못된 요청"
    if status_code >= 500:
        return "서버 오류"
    return None


def _api_error_result(payload, status_code):
    error_code = str(payload.get("errorCode") or payload.get("error_code") or status_code)
    message = _clean_text(payload.get("errorMessage") or payload.get("message"))
    if error_code in {"024", "SE01", "401", "403"}:
        status = "인증 오류"
    elif error_code in {"023", "429"}:
        status = "요청 제한"
    elif error_code in {"SE02", "400"}:
        status = "잘못된 요청"
    else:
        status = "서버 오류" if int(status_code or 0) >= 500 else "응답 오류"
    return _result(status, error_code, message=message or "네이버 뉴스 요청에 실패했습니다")


def fetch_naver_news(
    client_id,
    client_secret,
    query,
    display=10,
    start=1,
    sort="date",
    http_get=None,
):
    """Fetch and normalize Naver news search results without exposing credentials."""
    if not client_id or not client_secret:
        return _result("인증 오류", "INVALID_CREDENTIALS", message="네이버 뉴스 인증정보 설정이 필요합니다")
    if not str(query or "").strip():
        return _result("잘못된 요청", "INVALID_QUERY", message="검색어가 필요합니다")
    if not isinstance(display, int) or isinstance(display, bool) or not 1 <= display <= 100:
        return _result("잘못된 요청", "INVALID_DISPLAY", message="display는 1~100이어야 합니다")
    if not isinstance(start, int) or isinstance(start, bool) or not 1 <= start <= 1000:
        return _result("잘못된 요청", "INVALID_START", message="start는 1~1000이어야 합니다")
    if sort not in ("date", "sim"):
        return _result("잘못된 요청", "INVALID_SORT", message="sort는 date 또는 sim이어야 합니다")

    params = urllib.parse.urlencode({"query": str(query).strip(), "display": display, "start": start, "sort": sort})
    url = f"{ENDPOINT}?{params}"
    headers = {"X-Naver-Client-Id": str(client_id), "X-Naver-Client-Secret": str(client_secret)}
    try:
        raw, http_status = _read_response(_request(url, headers, http_get))
        http_error = _http_status_result(http_status)
        if http_error:
            return _result(http_error, http_status, message="네이버 뉴스 요청에 실패했습니다")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return _result("응답 오류", http_status, message="응답 형식이 올바르지 않습니다")
        if payload.get("errorCode") or payload.get("error_code"):
            return _api_error_result(payload, http_status)
        items = payload.get("items")
        if not isinstance(items, list):
            return _result("응답 오류", http_status, message="응답 형식이 올바르지 않습니다")
        data = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            originallink = str(item.get("originallink") or "").strip()
            link = str(item.get("link") or "").strip()
            identity = originallink or link
            if identity in seen:
                continue
            seen.add(identity)
            data.append({
                "title": _clean_text(item.get("title")),
                "originallink": originallink,
                "link": link,
                "description": _clean_text(item.get("description")),
                "pub_date": _normalize_pub_date(item.get("pubDate")),
            })
        return _result("정상" if data else "데이터 없음", http_status, data=data)
    except (TimeoutError, urllib.error.URLError, OSError):
        return _result("네트워크 오류", "NETWORK_ERROR", message="네이버 뉴스 네트워크 요청에 실패했습니다")
    except (json.JSONDecodeError, UnicodeError, ValueError):
        return _result("응답 오류", "INVALID_JSON", message="응답 형식이 올바르지 않습니다")
    except Exception:
        return _result("응답 오류", "UNEXPECTED_ERROR", message="네이버 뉴스 응답을 처리하지 못했습니다")
