"""Mockable Naver News Search client used by the read-only news feature later."""

import email.utils
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TIMEOUT = 10
ENDPOINT = "https://openapi.naver.com/v1/search/news.json"
_TAG_RE = re.compile(r"<[^>]*>")
_SEOUL_TZ = ZoneInfo("Asia/Seoul")

_DIRECT_RULES = (
    ("실적", ("실적 발표", "매출 증가", "매출 감소", "매출 발표", "영업이익", "순이익", "흑자전환", "적자전환", "실적 전망 상향", "실적 전망 하향", "가이던스 발표", "가이던스 변경")),
    ("수주·계약", ("수주", "공급계약", "납품계약", "계약 체결", "공급사 선정", "우선협상대상자 선정")),
    ("투자·M&A", ("시설투자 결정", "공장 증설", "설비 증설", "타법인 지분 투자", "지분 투자", "인수 결정", "기업 인수", "합병 결정", "사업 매각", "자산 매각", "회사 분할", "투자 결정")),
    ("주주환원·자본", ("배당 결정", "자사주 취득", "자사주 처분", "자사주 소각", "유상증자", "무상증자", "감자", "최대주주 변경", "지분 취득", "지분 매각")),
    ("규제·법적위험", ("조사", "제재", "소송", "리콜", "사고", "횡령", "배임", "압수수색", "거래정지", "상장폐지")),
    ("제품·기술", ("신제품 출시", "품목허가", "규제기관 승인", "특허 취득", "개발 완료", "양산 시작", "임상 주요 결과")),
)
_WEAK_KEYWORDS = ("실적", "매출", "전망", "가이던스", "공급", "선정", "투자", "인수", "배당", "지분", "조사", "제재", "소송", "출시", "승인", "개발", "양산")
_NON_DIRECT_CONTEXT = ("ETF", "ETN", "펀드", "투자상품", "목표주가", "주가 전망", "차트", "급등주", "급락주", "정치인", "헌법소원", "국회", "정당", "정치", "발언", "비교", "관련", "연관", "업계", "시장", "경쟁사", "파트너")
_MARKET_REACTION_PENDING = "시장 반응 확인 전"


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
    """Classify direct company events without inferring sentiment or price direction."""
    title = str(news_item.get("title") or "")
    description = str(news_item.get("description") or "")
    company = str(company_name or "").strip()
    symbol = str(ticker or "").strip()

    def has_subject(text):
        return bool(company and company in text) or bool(symbol and symbol in text)

    def direct_matches(text):
        if not has_subject(text):
            return []
        matches = [
            (category, phrase, text.find(phrase))
            for category, phrases in _DIRECT_RULES
            for phrase in phrases
            if phrase in text
        ]
        if any(term in text for term in _NON_DIRECT_CONTEXT):
            matches = [match for match in matches if match[0] != "투자·M&A"]
            if any(term in text for term in ("비교", "관련", "연관", "업계", "시장", "경쟁사", "파트너")):
                return []
        return matches

    title_matches = direct_matches(title)
    description_matches = direct_matches(description)
    chosen = title_matches or description_matches
    if chosen:
        # 고정 우선순위로 범주를 결정하고, 실제 일치 문구는 모두 사용자에게 남긴다.
        category = next(category for category, _ in _DIRECT_RULES if any(match[0] == category for match in chosen))
        matched = []
        for _, phrase, position in sorted(chosen, key=lambda match: (match[2], match[1])):
            if phrase not in matched:
                matched.append(phrase)
        field_name = "제목" if title_matches else "설명"
        return {
            "level": "기업 직접 재료 후보",
            "category": category,
            "market_reaction": _MARKET_REACTION_PENDING,
            "matched_keywords": matched,
            "reason": f"{field_name}에서 회사 직접 사건 문구 '{matched[0]}'가 일치했습니다.",
        }

    weak_matches = [keyword for keyword in _WEAK_KEYWORDS if keyword in title or keyword in description]
    context_text = f"{title} {description}"
    if any(word in context_text for word in ("ETF", "ETN", "펀드", "투자상품")):
        reason = "ETF·펀드·투자상품 문맥으로 직접적인 회사 투자 결정이 아닙니다."
    elif any(word in context_text for word in ("목표주가", "주가 전망", "차트", "급등주", "급락주")):
        reason = "주가·차트 전망 문맥으로 회사의 직접 사건이 아닙니다."
    elif any(word in context_text for word in ("정치인", "헌법소원", "국회", "정당", "정치", "발언")):
        reason = "정치·정책 문맥의 기업 언급으로 직접 사건이 아닙니다."
    elif any(word in context_text for word in ("IPO", "비교", "관련", "연관")):
        reason = "다른 회사가 주인공인 비교·연관 언급 기사입니다."
    elif weak_matches:
        reason = "중요 키워드는 있으나 회사 직접 사건 문구가 없어 일반 참고로 분류했습니다."
    else:
        reason = "회사 직접 사건을 확인할 수 없어 일반 참고로 분류했습니다."
    return {
        "level": "일반 참고",
        "category": "기타",
        "market_reaction": _MARKET_REACTION_PENDING,
        "matched_keywords": weak_matches,
        "reason": reason,
    }


def _normalize_pub_date(value):
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(str(value))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(_SEOUL_TZ).replace(tzinfo=None)
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
