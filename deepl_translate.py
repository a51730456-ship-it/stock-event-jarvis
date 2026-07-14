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


def translate_market_title_locally(text):
    """키 없이도 안전하게 번역할 수 있는 반복 금융 이벤트 제목만 한국어화한다."""
    if not text:
        return None
    original = str(text).strip()

    fed_match = re.fullmatch(r"Fed Decision in ([A-Za-z]+)\??", original, re.IGNORECASE)
    if fed_match:
        month = _MONTH_KO.get(fed_match.group(1).lower())
        if month:
            return f"{month} 연준 금리 결정"

    wti_match = re.fullmatch(
        r"What will WTI Crude Oil \(WTI\) hit in ([A-Za-z]+) (\d{4})\?",
        original,
        re.IGNORECASE,
    )
    if wti_match:
        month = _MONTH_KO.get(wti_match.group(1).lower())
        if month:
            return f"{wti_match.group(2)}년 {month} WTI 원유 가격은 어디까지 오를까?"

    exact_titles = {
        "us cpi this year": "올해 미국 소비자물가지수(CPI)",
        "cpi inflation": "소비자물가지수(CPI) 인플레이션",
        "fed decision": "연준 금리 결정",
    }
    return exact_titles.get(original.lower())


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
