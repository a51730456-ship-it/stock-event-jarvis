"""
P0 검증 2 — 네이버 테마 스크래핑 현황 보고 + 구성종목 상세 파싱 가능성 조사
기존 코드 수정 없음. 조사·출력만.
"""
import re
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
from pprint import pformat

NAVER_THEME_LIST_URL = "https://finance.naver.com/sise/theme.naver"
NAVER_THEME_DETAIL_URL = "https://finance.naver.com/sise/theme.naver?code={code}"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 검증용 테마 ID 몇 개만 사용 (실제 KR_THEME_NAVER_MAPPING 일부)
SAMPLE_THEME_IDS = [144, 30, 42]  # 방산, 조선, 게임 (페이지1에서 발견 가능한 것 위주)


def _fetch_page(page=1):
    url = NAVER_THEME_LIST_URL if page == 1 else f"{NAVER_THEME_LIST_URL}?page={page}"
    resp = requests.get(url, timeout=10, headers=NAVER_HEADERS)
    resp.raise_for_status()
    resp.encoding = "euc-kr"
    return resp.text


def _parse_theme_list(html):
    """테마 목록 페이지에서 가져올 수 있는 필드 파악."""
    THEME_ROW_PATTERN = re.compile(
        r'no=(\d+)">([^<]+)</a>.*?col_type2">\s*<span[^>]*>\s*([+-]?[\d.]+)%',
        re.S,
    )
    TOP_STOCK_PATTERN = re.compile(
        r'col_type[56]">.*?<a href="/item/main\.naver\?code=(\d+)">([^<]+)</a>',
        re.S,
    )
    results = {}
    for m in THEME_ROW_PATTERN.finditer(html):
        theme_id, name, pct = m.groups()
        window = html[m.end():m.end() + 700]
        top_stocks = TOP_STOCK_PATTERN.findall(window)
        results[int(theme_id)] = {
            "name": name.strip(),
            "change_pct": float(pct),
            "top_stocks": top_stocks[:4],  # (code, truncated_name)
        }
    return results


def report_list_page_fields(parsed, sample_ids):
    """테마 목록 페이지에서 현재 가져오는 필드 표 출력."""
    print("=" * 70)
    print("[검증 2-A] 테마 목록 페이지에서 현재 수집 가능한 데이터 필드")
    print("=" * 70)
    fields = {
        "테마명": "있음",
        "테마 등락률": "있음",
        "구성종목명(최대4개, 축약)": "있음",
        "종목별 등락률": "없음 (테마 목록 페이지에는 없음)",
        "종목별 거래대금": "없음 (테마 목록 페이지에는 없음)",
        "현재가": "없음 (테마 목록 페이지에는 없음)",
    }
    for k, v in fields.items():
        print(f"  {k:<30} → {v}")

    print("\n샘플 (테마 목록 페이지 파싱 결과):")
    for tid in sample_ids:
        row = parsed.get(tid)
        if row:
            stocks_str = ", ".join(f"{name}({code})" for code, name in row["top_stocks"])
            print(f"  [{tid}] {row['name']} | 등락률: {row['change_pct']:+.2f}% | 대표종목: {stocks_str}")
        else:
            print(f"  [{tid}] 미발견 (다른 페이지에 있을 수 있음)")


def probe_theme_detail_page(theme_id, theme_name):
    """테마 상세 페이지(themeStockList)에서 추가 파싱 가능 여부 조사."""
    url = NAVER_THEME_DETAIL_URL.format(code=theme_id)
    try:
        resp = requests.get(url, timeout=10, headers=NAVER_HEADERS)
        resp.raise_for_status()
        resp.encoding = "euc-kr"
        html = resp.text
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # 종목별 현재가
    price_pattern = re.compile(r'<td class="number">([\d,]+)</td>', re.S)
    prices = price_pattern.findall(html)

    # 등락률 패턴
    chg_pattern = re.compile(r'<span[^>]*>([-+]?[\d.]+)%</span>', re.S)
    changes = chg_pattern.findall(html)

    # 종목명
    name_pattern = re.compile(r'/item/main\.naver\?code=(\d{6})">([^<]+)</a>', re.S)
    names = name_pattern.findall(html)

    # 거래대금 — "백만" 단위 td나 숫자열에서 찾기
    vol_pattern = re.compile(r'<td[^>]*class="[^"]*number[^"]*"[^>]*>([\d,]+)</td>', re.S)
    all_nums = vol_pattern.findall(html)

    return {
        "ok": True,
        "url": url,
        "종목명_샘플": names[:5],
        "현재가_샘플": prices[:5],
        "등락률_샘플": changes[:10],
        "숫자열(거래대금후보)_샘플": all_nums[:10],
        "raw_html_len": len(html),
    }


def report_detail_page(parsed_list, sample_ids):
    print("\n" + "=" * 70)
    print("[검증 2-B] 테마 상세 페이지(themeStockList) 추가 파싱 가능성 조사")
    print("  (구현 금지 — 가능 여부만 확인)")
    print("=" * 70)

    for tid in sample_ids[:2]:  # 2개만 조사
        row = parsed_list.get(tid, {})
        name = row.get("name", f"테마{tid}")
        print(f"\n  ▶ 테마 [{tid}] {name}")
        result = probe_theme_detail_page(tid, name)
        if not result["ok"]:
            print(f"    FAIL 상세 페이지 접근 실패: {result['error']}")
            continue

        print(f"    URL: {result['url']}")
        print(f"    HTML 길이: {result['raw_html_len']} bytes")
        print(f"    종목명 매칭 샘플: {result['종목명_샘플']}")
        print(f"    현재가 샘플: {result['현재가_샘플']}")
        print(f"    등락률 샘플: {result['등락률_샘플']}")
        print(f"    숫자열(거래대금 후보) 샘플: {result['숫자열(거래대금후보)_샘플']}")

        # 판단
        has_names = len(result["종목명_샘플"]) > 0
        has_prices = len(result["현재가_샘플"]) > 0
        has_changes = len(result["등락률_샘플"]) > 0
        has_vol_candidates = len(result["숫자열(거래대금후보)_샘플"]) > 0

        print(f"\n    → 종목명 파싱 가능: {'OK' if has_names else 'FAIL'}")
        print(f"    → 현재가 파싱 가능: {'OK' if has_prices else 'FAIL'}")
        print(f"    → 등락률 파싱 가능: {'OK' if has_changes else 'FAIL'}")
        print(f"    → 거래대금 파싱 후보 존재: {'OK' if has_vol_candidates else 'FAIL'} (정렬/레이블 추가 분석 필요)")


if __name__ == "__main__":
    from datetime import datetime
    print("시작:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 페이지 1~4 로드해 샘플 ID 찾기
    parsed_all = {}
    for page in range(1, 5):
        try:
            html = _fetch_page(page)
            parsed_all.update(_parse_theme_list(html))
            found = [tid for tid in SAMPLE_THEME_IDS if tid in parsed_all]
            if set(SAMPLE_THEME_IDS).issubset(parsed_all.keys()):
                print(f"  페이지 {page}까지 로드 — 샘플 ID 모두 발견")
                break
        except Exception as e:
            print(f"  페이지 {page} 로드 실패: {e}")

    report_list_page_fields(parsed_all, SAMPLE_THEME_IDS)
    report_detail_page(parsed_all, SAMPLE_THEME_IDS)

    print("\n완료:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
