"""테마 참고판 자동 조회 전용 모듈 (읽기 전용, DB 미저장).

한국장: 네이버 "테마별 시세" 페이지(finance.naver.com/sise/theme.naver)를 스크래핑해서
자비스 8개 테마별 평균 등락률/대표 종목/강함·보통·약함 판정을 만든다.
미국장: yfinance(price_data.get_snapshot_defaults)로 섹터 ETF 등락률을 조회한다.

이 모듈의 결과는 화면 참고용 표시 전용이며, 점수·판정·DB 저장에는 절대 반영하지 않는다
(JARVIS_CONTEXT.md 핵심 설계 원칙 3). 조회 실패 시 예외를 던지지 않고
{"ok": False, "error": "..."} 형태로 반환한다.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

_KR_STOCK_MAPS_CACHE_TTL_SECONDS = 24 * 60 * 60
_kr_stock_maps_cache = {"at": 0.0, "value": ({}, {})}

NAVER_THEME_LIST_URL = "https://finance.naver.com/sise/theme.naver"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 사용자 승인된 매핑안 (2026-07-12). 자비스 테마 -> 네이버 테마 ID 목록.
# 2개 이상이면 평균 등락률을 낸다. 근거는 대화 승인 내역 참고.
# 2026-07-13: 테마 수가 너무 적다는 지적으로 8개 -> 20개로 확장. 네이버 테마별 시세
# 전체 목록(약 260여 개)에서 널리 쓰이는 대표 테마 12개를 추가로 선정했다(임의 선정,
# 다르게 바꾸고 싶으면 알려주면 됨).
KR_THEME_NAVER_MAPPING = {
    "반도체/HBM": [536, 155],
    "방산": [144],
    "조선/해운": [30, 36],
    "자동차/부품": [159, 27],
    "2차전지": [64],
    "AI/로봇": [99, 505],
    "원전": [205],
    "정유/화학": [185, 180],
    "게임": [42],
    "엔터테인먼트": [128],
    "바이오": [172, 241],
    "화장품": [110],
    "전력기기/전력망": [123, 229],
    "태양광": [191],
    "수소에너지": [386],
    "우주항공": [200],
    "5G/통신장비": [373],
    "사이버보안": [55],
    "의료기기": [175],
    "은행": [165],
}

_THEME_ROW_PATTERN = re.compile(
    r'no=(\d+)">([^<]+)</a>.*?col_type2">\s*<span[^>]*>\s*([+-]?[\d.]+)%',
    re.S,
)
_TOP_STOCK_PATTERN = re.compile(
    r'col_type[56]">.*?<a href="/item/main\.naver\?code=(\d+)">([^<]+)</a>',
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
            "top_stocks": top_stocks[:4],
        }
    return rows


def _classify_kr_theme_verdict(avg_change_pct):
    if avg_change_pct >= 2.0:
        return "강함"
    if avg_change_pct <= -2.0:
        return "약함"
    return "보통"


def _get_kr_stock_maps():
    """FinanceDataReader의 KRX 전체 종목 목록에서 {코드: 정식 종목명}과 {코드: 시장} 매핑을
    함께 만든다. 실패하면 빈 dict 2개를 반환한다(예외 없이 안전하게 대체).

    KRX 전체 종목(약 2500개) 조회는 몇 초씩 걸리는데 하루 안에는 거의 안 바뀌는 정적
    데이터라, 캐시 없이 테마 참고판 새로고침마다 매번 다시 받고 있었다(2026-07-15
    실측 발견 — 수동 새로고침이 느린 원인 중 하나였다). 24시간 캐시로 재사용한다.
    """
    now = time.time()
    if now - _kr_stock_maps_cache["at"] < _KR_STOCK_MAPS_CACHE_TTL_SECONDS:
        return _kr_stock_maps_cache["value"]
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KRX")
    except Exception:
        return _kr_stock_maps_cache["value"] if _kr_stock_maps_cache["at"] else ({}, {})
    if df is None or df.empty or not {"Code", "Name", "Market"}.issubset(df.columns):
        return _kr_stock_maps_cache["value"] if _kr_stock_maps_cache["at"] else ({}, {})
    code_to_name = {str(code).strip(): str(name).strip() for code, name in zip(df["Code"], df["Name"])}
    code_to_market = {str(code).strip(): str(market).strip() for code, market in zip(df["Code"], df["Market"])}
    _kr_stock_maps_cache["at"] = now
    _kr_stock_maps_cache["value"] = (code_to_name, code_to_market)
    return code_to_name, code_to_market


def _get_kr_stock_code_to_name_map():
    """FinanceDataReader의 KRX 전체 종목 목록에서 {6자리 코드: 정식 종목명} 매핑을 만든다.

    네이버 테마별 시세 페이지가 대표 종목명을 셀 안에서 줄여서 주는 문제(예:
    "피에스케이.." — 네이버 원본 HTML 자체가 이미 줄인 상태라 정규식으로는 복구
    불가)를 해결하기 위해, 같은 셀에 있는 6자리 종목코드로 정식 이름을 다시 찾는다
    (2026-07-13, 사용자가 이전에도 지적한 문제). 실패하면 빈 dict를 반환하고,
    호출부는 그러면 네이버가 준 축약 이름을 그대로 쓴다(예외 없이 안전하게 대체).
    """
    code_to_name, _ = _get_kr_stock_maps()
    return code_to_name


def _fetch_theme_pages_in_parallel(pages):
    """네이버 테마별 시세 페이지 여러 개를 동시에 조회한다.

    반환: {page: (parsed_dict, error_str_or_None)}
    """
    pages = list(pages)

    def _fetch_page(page):
        url = NAVER_THEME_LIST_URL if page == 1 else f"{NAVER_THEME_LIST_URL}?page={page}"
        try:
            resp = requests.get(url, timeout=8, headers=NAVER_HEADERS)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
            return page, _parse_naver_theme_list(resp.text), None
        except Exception as e:
            return page, {}, str(e)

    results = {}
    with ThreadPoolExecutor(max_workers=len(pages)) as executor:
        futures = [executor.submit(_fetch_page, page) for page in pages]
        for future in as_completed(futures):
            page, page_parsed, err = future.result()
            results[page] = (page_parsed, err)
    return results


def fetch_kr_theme_snapshot():
    """자비스 8개 테마의 네이버 매핑 기반 평균 등락률·대표종목·자동판정을 가져온다.

    반환: {"ok": bool, "error": str|None, "checked_at": str|None,
    "themes": {테마명: {"ok": bool, "change_pct": float, "verdict": str,
    "top_stock": str|None, "source_themes": [네이버 테마명, ...]}}}
    """
    from datetime import datetime

    # 네이버 테마별 시세는 여러 페이지에 나뉘어 있다. 순차 조회는 페이지당 약
    # 0.8~0.9초씩 누적돼 8페이지면 4~5초가 걸린다(2026-07-15 실측). 필요한
    # theme_id가 어느 페이지에 있는지 미리 알 수 없으므로 8페이지를 동시에
    # 조회해 병목을 없앤다.
    needed_ids = {tid for ids in KR_THEME_NAVER_MAPPING.values() for tid in ids}
    parsed = {}
    last_error = None
    page_results = _fetch_theme_pages_in_parallel(range(1, 9))
    for page in range(1, 9):
        page_parsed, err = page_results.get(page, ({}, None))
        if err:
            # 한 페이지 실패로 이미 파싱한 다른 페이지 결과까지 버리지 않는다 —
            # fetch_us_sector_snapshot/fetch_us_theme_indicators와 동일하게 개별
            # 실패는 건너뛰고 이어간다(2026-07-13 전체 코드검사에서 발견/수정).
            last_error = err
            continue
        parsed.update(page_parsed)
        if needed_ids.issubset(parsed.keys()):
            break

    if not parsed:
        return {
            "ok": False,
            "error": last_error or "테마 데이터를 찾지 못했습니다(페이지 구조 변경 가능성)",
            "checked_at": None,
            "themes": {},
        }

    code_to_name = _get_kr_stock_code_to_name_map()

    themes = {}
    for jarvis_theme, naver_ids in KR_THEME_NAVER_MAPPING.items():
        matched = [parsed[i] for i in naver_ids if i in parsed]
        if not matched:
            themes[jarvis_theme] = {"ok": False}
            continue
        avg_pct = round(sum(m["change_pct"] for m in matched) / len(matched), 2)
        # 예전엔 첫 번째로 매칭된 네이버 서브테마의 첫 종목 1개만 썼다 — 매칭되는 서브테마가
        # 여러 개면 나머지 종목 정보가 버려졌다. 매칭된 모든 서브테마의 대표 종목을 중복
        # 없이 모아 최대 4개까지 콤마로 합친다(2026-07-13, 사용자 요청: 대표 종목이 너무
        # 적다는 지적 반영). 종목명은 code_to_name으로 정식 이름을 우선 쓰고, 매핑에 없으면
        # 네이버가 준 축약 이름을 그대로 쓴다.
        top_stocks_all = []
        for m in matched:
            for code, truncated_name in m["top_stocks"]:
                resolved_name = code_to_name.get(code, truncated_name)
                if resolved_name and resolved_name not in top_stocks_all:
                    top_stocks_all.append(resolved_name)
        top_stock = ", ".join(top_stocks_all[:4]) if top_stocks_all else None
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


def fetch_kr_theme_stock_detail(theme_name):
    """선택된 테마 1개의 대표 종목별 등락률을 개별 조회해서 대장주/후발주/추격주의를
    자동 산정한다(2026-07-13 추가).

    fetch_kr_theme_snapshot()은 20개 테마 전체를 한 번에 훑으며 종목 "이름"만 모아
    보여줄 뿐 개별 등락률은 조회하지 않는다 — 테마당 최대 4종목을 20개 테마 전부에
    개별 조회하면 네트워크 호출이 너무 많아진다. 이 함수는 "선택 테마 세부 입력"에서
    버튼을 눌렀을 때만 그 테마 1개에 대해서만 개별 종목 등락률을 조회해 순위를 매긴다.
    CLAUDE.md 5번 기준(3등주부터 기대값 급감, 대장주가 -7~10% 꺾이면 후발주 청산)을
    참고해 1등=대장주, 2·3등(양전)=후발주, 4등 이하=추격주의로 분류한다. 점수·판정·
    DB에는 반영하지 않는 참고용 계산이다.
    """
    import price_data

    naver_ids = KR_THEME_NAVER_MAPPING.get(theme_name)
    if not naver_ids:
        return {"ok": False, "error": "등록되지 않은 테마입니다"}

    parsed = {}
    last_error = None
    page_results = _fetch_theme_pages_in_parallel(range(1, 9))
    for page in range(1, 9):
        page_parsed, err = page_results.get(page, ({}, None))
        if err:
            last_error = err
            continue
        parsed.update(page_parsed)
        if set(naver_ids).issubset(parsed.keys()):
            break

    matched = [parsed[i] for i in naver_ids if i in parsed]
    if not matched:
        return {"ok": False, "error": last_error or "테마 데이터를 찾지 못했습니다"}

    code_to_name, code_to_market = _get_kr_stock_maps()

    candidates = []
    seen_codes = set()
    for m in matched:
        for code, truncated_name in m["top_stocks"]:
            if code in seen_codes:
                continue
            seen_codes.add(code)
            name = code_to_name.get(code, truncated_name)
            market = code_to_market.get(code)
            suffix = ".KQ" if market == "KOSDAQ" else ".KS"
            try:
                snap = price_data.get_snapshot_defaults(f"{code}{suffix}")
            except Exception:
                snap = {"ok": False}
            change_pct = None
            if snap.get("ok") and snap.get("current") and snap.get("prev_close"):
                change_pct = round(
                    (snap["current"] - snap["prev_close"]) / snap["prev_close"] * 100, 2
                )
            candidates.append({"code": code, "name": name, "change_pct": change_pct})

    ranked = sorted(
        (c for c in candidates if c["change_pct"] is not None),
        key=lambda c: c["change_pct"],
        reverse=True,
    )
    failed_names = [c["name"] for c in candidates if c["change_pct"] is None]

    if not ranked:
        return {
            "ok": False,
            "error": "종목 시세를 하나도 조회하지 못했습니다",
            "price_fetch_failed": failed_names,
        }

    leader = ranked[0]
    laggards = [c["name"] for c in ranked[1:3] if c["change_pct"] > 0]
    chase_warning = [c["name"] for c in ranked[3:]]

    return {
        "ok": True,
        "error": None,
        "대장주": leader["name"],
        "후발주": ", ".join(laggards) if laggards else None,
        "추격주의": ", ".join(chase_warning) if chase_warning else None,
        "candidates": candidates,
        "price_fetch_failed": failed_names,
    }


def _fetch_tickers_in_parallel(fetch_fn, tickers):
    """티커별 조회 함수를 동시에 실행한다(price_data.py는 읽기 전용으로만 호출).

    yfinance 건당 응답이 0.8~1초 안팎이라 섹터 ETF(5개)/테마 지표(약 18개)를 순차
    조회하면 2~4초가 누적된다(2026-07-15 실측). 개별 실패는 격리해 나머지는 계속
    진행한다.
    """
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
        future_to_ticker = {executor.submit(fetch_fn, ticker): ticker for ticker in tickers}
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ok": False}
    return results


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

    tickers = [ticker for ticker, _label in US_SECTOR_ETFS]
    results = _fetch_tickers_in_parallel(price_data.get_snapshot_defaults, tickers)

    sectors = []
    any_ok = False
    for ticker, label in US_SECTOR_ETFS:
        result = results.get(ticker) or {"ok": False}
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
    results = _fetch_tickers_in_parallel(price_data.get_snapshot_defaults, all_tickers)

    values = {}
    any_ok = False
    for ticker in all_tickers:
        result = results.get(ticker) or {"ok": False}
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
