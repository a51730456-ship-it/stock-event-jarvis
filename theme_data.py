"""테마 참고판 자동 조회 전용 모듈 (읽기 전용, DB 미저장).

한국장: 네이버 "테마별 시세" 페이지(finance.naver.com/sise/theme.naver)를 스크래핑해서
자비스 8개 테마별 평균 등락률/대표 종목/강함·보통·약함 판정을 만든다.
미국장: yfinance(price_data.get_snapshot_defaults)로 섹터 ETF 등락률을 조회한다.

이 모듈의 결과는 화면 참고용 표시 전용이며, 점수·판정·DB 저장에는 절대 반영하지 않는다
(JARVIS_CONTEXT.md 핵심 설계 원칙 3). 조회 실패 시 예외를 던지지 않고
{"ok": False, "error": "..."} 형태로 반환한다.
"""

import re

import requests

NAVER_THEME_LIST_URL = "https://finance.naver.com/sise/theme.naver"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 사용자 승인된 매핑안 (2026-07-12). 자비스 테마 -> 네이버 테마 ID 목록.
# 2개 이상이면 평균 등락률을 낸다. 근거는 대화 승인 내역 참고.
KR_THEME_NAVER_MAPPING = {
    "반도체/HBM": [536, 155],
    "방산": [144],
    "조선/해운": [30, 36],
    "자동차/부품": [159, 27],
    "2차전지": [64],
    "AI/로봇": [99, 505],
    "원전": [205],
    "정유/화학": [185, 180],
}

_THEME_ROW_PATTERN = re.compile(
    r'no=(\d+)">([^<]+)</a>.*?col_type2">\s*<span[^>]*>\s*([+-]?[\d.]+)%',
    re.S,
)
_TOP_STOCK_PATTERN = re.compile(
    r'col_type[56]">.*?<a href="/item/main\.naver\?code=\d+">([^<]+)</a>',
    re.S,
)


def _parse_naver_theme_list(html):
    """네이버 테마별 시세 페이지 HTML에서 {theme_id: {"name", "change_pct", "top_stocks"}} 추출."""
    rows = {}
    for m in _THEME_ROW_PATTERN.finditer(html):
        theme_id, name, pct = m.groups()
        window = html[m.end():m.end() + 700]
        top_stocks = _TOP_STOCK_PATTERN.findall(window)
        rows[int(theme_id)] = {
            "name": name,
            "change_pct": float(pct),
            "top_stocks": top_stocks[:2],
        }
    return rows


def _classify_kr_theme_verdict(avg_change_pct):
    if avg_change_pct >= 2.0:
        return "강함"
    if avg_change_pct <= -2.0:
        return "약함"
    return "보통"


def fetch_kr_theme_snapshot():
    """자비스 8개 테마의 네이버 매핑 기반 평균 등락률·대표종목·자동판정을 가져온다.

    반환: {"ok": bool, "error": str|None, "checked_at": str|None,
    "themes": {테마명: {"ok": bool, "change_pct": float, "verdict": str,
    "top_stock": str|None, "source_themes": [네이버 테마명, ...]}}}
    """
    from datetime import datetime

    # 네이버 테마별 시세는 여러 페이지에 나뉘어 있다. 매핑에 필요한 theme_id를
    # 전부 찾을 때까지(또는 최대 8페이지까지) 순회한다.
    needed_ids = {tid for ids in KR_THEME_NAVER_MAPPING.values() for tid in ids}
    parsed = {}
    try:
        for page in range(1, 9):
            url = NAVER_THEME_LIST_URL if page == 1 else f"{NAVER_THEME_LIST_URL}?page={page}"
            resp = requests.get(url, timeout=8, headers=NAVER_HEADERS)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
            parsed.update(_parse_naver_theme_list(resp.text))
            if needed_ids.issubset(parsed.keys()):
                break
    except Exception as e:
        return {"ok": False, "error": str(e), "checked_at": None, "themes": {}}

    if not parsed:
        return {"ok": False, "error": "테마 데이터를 찾지 못했습니다(페이지 구조 변경 가능성)", "checked_at": None, "themes": {}}

    themes = {}
    for jarvis_theme, naver_ids in KR_THEME_NAVER_MAPPING.items():
        matched = [parsed[i] for i in naver_ids if i in parsed]
        if not matched:
            themes[jarvis_theme] = {"ok": False}
            continue
        avg_pct = round(sum(m["change_pct"] for m in matched) / len(matched), 2)
        top_stock = None
        for m in matched:
            if m["top_stocks"]:
                top_stock = m["top_stocks"][0]
                break
        themes[jarvis_theme] = {
            "ok": True,
            "change_pct": avg_pct,
            "verdict": _classify_kr_theme_verdict(avg_pct),
            "top_stock": top_stock,
            "source_themes": [m["name"] for m in matched],
        }
    return {
        "ok": True,
        "error": None,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "themes": themes,
    }


US_SECTOR_ETFS = [
    ("SOXX", "반도체"),
    ("SMH", "반도체"),
    ("XLK", "기술"),
    ("XLE", "에너지"),
    ("XLF", "금융"),
]


def fetch_us_sector_snapshot():
    """미국 섹터 ETF(SOXX/SMH/XLK/XLE/XLF) 등락률을 yfinance 기반으로 조회한다.

    price_data.py는 변경하지 않고 기존 get_snapshot_defaults()를 읽기 전용으로 재사용한다.
    반환: {"ok": bool, "checked_at": str|None, "sectors": [{"ticker","label","change_pct","ok"}, ...]}
    """
    from datetime import datetime

    import price_data

    sectors = []
    any_ok = False
    for ticker, label in US_SECTOR_ETFS:
        try:
            result = price_data.get_snapshot_defaults(ticker)
        except Exception:
            result = {"ok": False}
        if result.get("ok") and result.get("current") and result.get("prev_close"):
            change_pct = round(
                (result["current"] - result["prev_close"]) / result["prev_close"] * 100, 2
            )
            sectors.append({"ticker": ticker, "label": label, "change_pct": change_pct, "ok": True})
            any_ok = True
        else:
            sectors.append({"ticker": ticker, "label": label, "change_pct": None, "ok": False})

    return {
        "ok": any_ok,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if any_ok else None,
        "sectors": sectors,
    }


# 미국장 테마 레이더 "참고 지표" 컬럼에 이미 적힌 티커들. yfinance에서 그대로 조회 안 되는
# 것은 확인 후 동작하는 대체 티커로 치환했다(둘 다 실제로 조회해서 확인함, 2026-07-12):
# "VIX" -> "^VIX", "DXY" -> "DX-Y.NYB"(DXY 자체는 delisted). "미국 10년물"은 "^TNX"로
# 정상 조회되어 포함했다(사용자가 예외 처리하라고 한 것과 달리 실제로는 조회 가능했음).
US_THEME_INDICATOR_MAPPING = {
    "AI/반도체": ["SOXX", "SMH", "XLK"],
    "에너지/유가": ["XLE"],
    "금리/성장주": ["QQQ", "^VIX", "DX-Y.NYB", "^TNX"],
    "전력망/원전": ["XLU", "GRID", "URA"],
    "방산/전쟁": ["ITA", "XAR", "LMT", "NOC"],
    "자동차/전기차": ["TSLA", "LIT"],
    "바이오": ["XBI", "IBB"],
}


def fetch_us_theme_indicators():
    """미국장 테마 레이더 7개 테마 전부에 필요한 지표 티커를 한 번에 조회한다.

    US_THEME_INDICATOR_MAPPING에 등장하는 모든 티커(중복 제거)를 순회 조회하며,
    개별 실패는 건너뛰고 나머지로 계속 진행한다(예외를 던지지 않음).
    반환: {"ok": bool, "checked_at": str|None, "values": {티커: 등락률(%) 또는 None}}
    """
    from datetime import datetime

    import price_data

    all_tickers = sorted({t for tickers in US_THEME_INDICATOR_MAPPING.values() for t in tickers})
    values = {}
    any_ok = False
    for ticker in all_tickers:
        try:
            result = price_data.get_snapshot_defaults(ticker)
        except Exception:
            result = {"ok": False}
        if result.get("ok") and result.get("current") and result.get("prev_close"):
            values[ticker] = round(
                (result["current"] - result["prev_close"]) / result["prev_close"] * 100, 2
            )
            any_ok = True
        else:
            values[ticker] = None

    return {
        "ok": any_ok,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if any_ok else None,
        "values": values,
    }
