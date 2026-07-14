"""DeepL Free API를 이용한 영어 -> 한국어 번역 전용 모듈 (읽기 전용, 참고 표시용).

도박사(예측시장) 신호의 영어 원문 질문을 한국어로 보여주기 위해서만 쓴다. 점수·판정·
DB 저장에는 사용하지 않는다. 호출 시점은 이 모듈이 정하지 않는다 — 호출부(app.py)가
"도박사 신호 불러오기" 버튼을 눌렀을 때만, 그리고 아직 캐시에 없는 문장만 넘긴다.

API 키·요청 헤더·원시 예외 메시지는 절대 반환하지 않는다(화면에 노출 금지 요구사항).
DeepL 키가 없는 경우에도 자주 노출되는 금융 이벤트 제목은 아래 로컬 규칙으로
한국어 요약을 제공한다. 규칙에 없는 문장은 원문을 임의 번역하지 않는다.
"""

import re

import requests

DEEPL_FREE_ENDPOINT = "https://api-free.deepl.com/v2/translate"
REQUEST_TIMEOUT = 8

_MONTH_KO = {
    "january": "1월", "february": "2월", "march": "3월", "april": "4월",
    "may": "5월", "june": "6월", "july": "7월", "august": "8월",
    "september": "9월", "october": "10월", "november": "11월", "december": "12월",
}


def _month_to_ko(month_name):
    return _MONTH_KO.get(str(month_name).lower())


def translate_market_text_locally(text):
    """키 없이도 안전하게 번역할 수 있는 반복 금융 제목·질문을 한국어화한다."""
    if not text:
        return None
    original = str(text).strip()

    fed_match = re.fullmatch(r"Fed Decision in ([A-Za-z]+)\??", original, re.IGNORECASE)
    if fed_match:
        month = _month_to_ko(fed_match.group(1))
        if month:
            return f"{month} 연준 금리 결정"

    wti_match = re.fullmatch(
        r"What will WTI Crude Oil \(WTI\) hit in ([A-Za-z]+) (\d{4})\?",
        original,
        re.IGNORECASE,
    )
    if wti_match:
        month = _month_to_ko(wti_match.group(1))
        if month:
            return f"{wti_match.group(2)}년 {month} WTI 원유 가격은 어디까지 오를까?"

    fed_unchanged = re.fullmatch(
        r"Will there be no change in Fed interest rates after the ([A-Za-z]+) (\d{4}) meeting\?",
        original,
        re.IGNORECASE,
    )
    if fed_unchanged:
        month = _month_to_ko(fed_unchanged.group(1))
        if month:
            return f"{fed_unchanged.group(2)}년 {month} 연준 회의 후 기준금리가 동결될까?"

    fed_move = re.fullmatch(
        r"Will the Fed (increase|decrease) interest rates by (\d+)(\+)? bps after the "
        r"([A-Za-z]+) (\d{4}) meeting\?",
        original,
        re.IGNORECASE,
    )
    if fed_move:
        direction, amount, plus, month_name, year = fed_move.groups()
        month = _month_to_ko(month_name)
        if month:
            amount_text = f"{amount}bp 이상" if plus else f"{amount}bp"
            direction_text = "인상" if direction.lower() == "increase" else "인하"
            return f"{year}년 {month} 연준 회의 후 기준금리가 {amount_text} {direction_text}될까?"

    wti_level = re.fullmatch(
        r"Will WTI Crude Oil \(WTI\) hit \(HIGH\) \$(\d+(?:\.\d+)?) in ([A-Za-z]+)\?",
        original,
        re.IGNORECASE,
    )
    if wti_level:
        month = _month_to_ko(wti_level.group(2))
        if month:
            return f"{month} WTI 원유 가격이 {wti_level.group(1)}달러 이상 오를까?"

    fed_cut_count = re.fullmatch(r"Will the Fed cut rates (\d+) times\?", original, re.IGNORECASE)
    if fed_cut_count:
        return f"연준이 금리를 {fed_cut_count.group(1)}회 인하할까?"

    no_fed_cuts = re.fullmatch(r"Will no Fed rate cuts happen in (\d{4})\?", original, re.IGNORECASE)
    if no_fed_cuts:
        return f"{no_fed_cuts.group(1)}년 연준이 금리를 한 번도 인하하지 않을까?"

    largest_company = re.fullmatch(
        r"Will (.+?) be the largest company in the world by market cap on ([A-Za-z]+) (\d{1,2})\?",
        original,
        re.IGNORECASE,
    )
    if largest_company:
        company, month_name, day = largest_company.groups()
        month = _month_to_ko(month_name)
        if month:
            return f"{month} {int(day)}일 시가총액 세계 1위 기업이 {company}일까?"

    cpi_compare = re.fullmatch(
        r"Will core CPI inflation exceed headline CPI inflation in ([A-Za-z]+) (\d{4})\?",
        original,
        re.IGNORECASE,
    )
    if cpi_compare:
        month = _month_to_ko(cpi_compare.group(1))
        if month:
            return f"{cpi_compare.group(2)}년 {month} 근원 CPI 상승률이 전체 CPI 상승률을 웃돌까?"

    exact_titles = {
        "us cpi this year": "올해 미국 소비자물가지수(CPI)",
        "cpi inflation": "소비자물가지수(CPI) 인플레이션",
        "fed decision": "연준 금리 결정",
        "how many fed rate cuts in 2026?": "2026년 연준 금리 인하 횟수",
        "fed rate hike in 2026?": "2026년 연준 금리 인상 여부",
        "largest company end of july?": "7월 말 시가총액 1위 기업",
        "will the federal reserve cut rates before 2027?": "2027년 이전 연준 금리 인하 여부",
        "will the bank of japan hike 25bps at the july 2026 monetary policy meeting?":
            "2026년 7월 일본은행이 기준금리를 25bp 인상할까?",
        "will any 2026 freddie mac primary mortgage market survey (pmms) report a 30-year fixed-rate mortgage rate below 5.75%?":
            "2026년 미국 30년 고정 모기지 금리가 5.75% 아래로 내려갈까?",
        "will china obtains or develops a functional extreme ultraviolet (euv) lithography machine that capable of patterning semiconductor wafers in a fabrication facility be confirmed before jan 1, 2030?":
            "2030년 이전 중국의 반도체용 EUV 노광장비 확보·개발이 확인될까?",
        "will the bank of mexico maintain current rate at the august bank of mexico governing board meeting?":
            "8월 멕시코 중앙은행이 현재 기준금리를 유지할까?",
    }
    return exact_titles.get(original.lower())


def translate_market_title_locally(text):
    """기존 호출자 호환용 별칭."""
    return translate_market_text_locally(text)


def translate_texts_to_ko(texts, api_key, timeout=REQUEST_TIMEOUT):
    """영어 문장 리스트를 한국어로 일괄 번역한다.

    반환: {"ok": bool, "translations": {원문: 번역문}, "error": str|None}
    - texts가 비어 있으면 API를 호출하지 않고 즉시 ok=True, 빈 dict를 반환한다.
    - api_key가 없으면 ok=False, "DeepL API 키가 설정되지 않았습니다"를 반환한다
      (원시 예외/헤더는 절대 노출하지 않는다).
    - 요청 실패 시에도 예외를 던지지 않고 ok=False로 반환한다. 에러 메시지는
      사람이 읽을 수 있는 일반화된 문구만 담고, requests 예외의 원문(URL·키 포함
      가능성)은 절대 그대로 노출하지 않는다.
    """
    # 같은 사건 제목이 두 출처에 반복되어도 번역 API에는 한 번만 보낸다. 원문
    # 문자열은 번역 캐시 키이므로 정규화하거나 변경하지 않는다.
    texts = list(dict.fromkeys(t for t in (texts or []) if t))
    if not texts:
        return {"ok": True, "translations": {}, "error": None}
    if not api_key:
        return {"ok": False, "translations": {}, "error": "DeepL API 키가 설정되지 않았습니다"}

    try:
        resp = requests.post(
            DEEPL_FREE_ENDPOINT,
            data={
                "auth_key": api_key,
                "text": texts,
                "target_lang": "KO",
                "source_lang": "EN",
            },
            timeout=timeout,
        )
    except Exception:
        return {"ok": False, "translations": {}, "error": "번역 서버 연결에 실패했습니다"}

    if resp.status_code != 200:
        return {"ok": False, "translations": {}, "error": "번역 요청이 거부되었습니다(요청 한도 또는 키 오류 가능)"}

    try:
        payload = resp.json()
        result_list = payload.get("translations", [])
    except Exception:
        return {"ok": False, "translations": {}, "error": "번역 응답 형식이 올바르지 않습니다"}

    if len(result_list) != len(texts):
        return {"ok": False, "translations": {}, "error": "번역 응답 개수가 일치하지 않습니다"}

    translations = {}
    for original, item in zip(texts, result_list):
        translated = item.get("text") if isinstance(item, dict) else None
        if not translated:
            return {"ok": False, "translations": {}, "error": "번역 결과가 비어 있습니다"}
        translations[original] = translated
    return {"ok": True, "translations": translations, "error": None}
