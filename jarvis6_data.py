"""자비스6 종가 관찰 — 15:18 기준 후보 계산.

자비스4·자비스5가 이미 모아 둔 것을 쓰고, 새로 조회하지 않는다.
- 종목 가격·거래대금·고가·저가·시총 : 자비스5 수집기(3분마다)
- 전고점·기간조정·일봉 차트         : 자비스4 get_daily_frame
- 외국인·기관 수급                  : 자비스4 get_stock_flow (어제까지)
- 테마 구성·동반 상승               : 자비스5 스냅샷

기준 숫자는 일봉 되돌아보기(2026-07-27)에서 나온 값이다. 개발 8년과
숨겨 둔 2년에서 모두 살아남은 조건만 기본값으로 쓴다. 그래도 **상한선**이라
실제 15:18에는 이보다 나쁘다. 화면에 그렇게 밝힌다.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

MODULE_REVISION = 2026072702

_SEOUL = ZoneInfo("Asia/Seoul")

# 되돌아보기에서 나온 기본 기준 (docs/JARVIS6_SPEC.md)
# 전고점 -3% 이내 · 거래대금 2배 이상 · 윗꼬리 30% 이하
DEFAULTS = {
    "from_high_pct": -3.0,
    "value_ratio": 2.0,
    "upper_wick": 0.30,
    "min_value": 5_000_000_000,   # 하루 거래대금 50억 하한
    "min_price": 1_000,
    "big_cap": 1_000_000_000_000, # 시총 1조 — 이 위는 외인·기관 수급을 무겁게 본다
}

# 판단을 끊는 시각. 15:20이 지나면 종가가 정해지므로 그 뒤 자료는 쓰지 않는다.
# 화면·설명·명세가 모두 "15:18에 끊는다"인데 코드만 15:19까지 열려 있었다
# (2026-07-26). 같은 화면에서 '판단 마감 15:18'과 '관찰 구간 ~15:19'가 함께
# 보였다. 글로 밝힌 쪽에 코드를 맞춘다.
CUTOFF = dt_time(15, 18)
WATCH_FROM = dt_time(14, 30)
OPEN = dt_time(9, 0)


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def market_phase(now: datetime | None = None) -> dict:
    """지금이 하루 중 어느 단계인지.

    돌려주는 두 깃발은 뜻이 다르다. 섞어 쓰면 안 된다.

    - ``watching`` : 후보를 굳히는 구간 (평일 14:30~15:19)
    - ``live``     : 실시간 시세를 써도 되는 구간 (평일 09:00~15:19)

    오전에도 체결은 정상이라 실시간 값이 일봉보다 정확하다. 이 둘을 같은
    것으로 보고 ``watching``으로 실시간을 껐더니 09:00~14:29 내내 어제
    고가·저가를 오늘 것처럼 보여 줬다(2026-07-26). 반대로 15:20부터는 종가
    단일가라 실시간 쪽에 NXT가 섞여 시가·저가가 일봉과 어긋난다.
    """
    stamp = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    # 초를 버리고 **분으로** 견준다. 초까지 두고 `clock <= 15:18`을 하면
    # 15:18:00 정각까지만 통과해 15:18:30에는 이미 꺼진다. "15:18까지 본다"는
    # 말과 다르다(2026-07-26 테스트가 잡음).
    clock = stamp.time().replace(second=0, microsecond=0)
    weekday = stamp.weekday() < 5

    if not weekday:
        label = "주말 휴장"
    elif clock < OPEN:
        label = "장 전"
    elif clock < WATCH_FROM:
        label = "장중 (관찰 전)"
    elif clock <= CUTOFF:
        label = "관찰 구간"
    elif clock < dt_time(15, 30):
        label = "종가 단일가 (판단 마감)"
    elif clock < dt_time(20, 0):
        label = "시간외"
    else:
        label = "장 마감"

    return {
        "label": label,
        "watching": label == "관찰 구간",
        "live": weekday and OPEN <= clock <= CUTOFF,
    }


def intraday_location(price, low, high):
    """당일 가격범위에서 어디쯤인가. 0=저가, 1=고가. 못 재면 None."""
    price, low, high = _finite(price), _finite(low), _finite(high)
    if None in (price, low, high) or high <= low:
        return None
    return max(0.0, min(1.0, (price - low) / (high - low)))


def upper_wick_ratio(price, low, high):
    """윗꼬리 비율. 고가에서 얼마나 밀렸나."""
    location = intraday_location(price, low, high)
    return None if location is None else 1.0 - location


def evaluate(stock: dict, daily_metrics: dict, flow: dict | None,
             theme: dict | None, config: dict | None = None) -> dict:
    """한 종목의 조건을 재서 재료·자리·힘 세 덩어리로 돌려준다.

    점수를 만들지 않는다. **조건 몇 개를 채웠나**만 센다. 배점을 매기려면
    어떤 조건이 얼마나 중요한지 알아야 하는데 그건 자료가 더 쌓여야 안다.
    """
    cfg = {**DEFAULTS, **(config or {})}
    price = _finite(stock.get("price"))
    high, low = _finite(stock.get("day_high")), _finite(stock.get("day_low"))
    value = _finite(stock.get("trading_value"))
    cap = _finite(stock.get("market_cap"))

    from_high = _finite(daily_metrics.get("from_high_pct"))
    days_since = daily_metrics.get("high52_days_ago")
    avg_value = _finite(daily_metrics.get("avg_trading_value"))
    value_ratio = (value / avg_value) if (value and avg_value) else None
    wick = upper_wick_ratio(price, low, high)
    location = intraday_location(price, low, high)

    # --- 자리: 차트가 답하는 것
    place = [
        ("전고점 근접", from_high is not None and from_high >= cfg["from_high_pct"],
         f"{from_high:+.1f}%" if from_high is not None else "—"),
        ("윗꼬리 짧음", wick is not None and wick <= cfg["upper_wick"],
         f"{wick*100:.0f}%" if wick is not None else "—"),
        ("기간조정 지남", isinstance(days_since, (int, float)) and days_since >= 20,
         f"{int(days_since)}일" if isinstance(days_since, (int, float)) else "—"),
    ]

    # --- 힘: 오늘 돈이 몰리는가
    both_buy = (flow or {}).get("both_buy_days5") or 0
    theme_up = (theme or {}).get("advancers") or 0
    strength = [
        ("거래대금 증가", value_ratio is not None and value_ratio >= cfg["value_ratio"],
         f"{value_ratio:.1f}배" if value_ratio is not None else "—"),
        ("고가 부근 마감", location is not None and location >= 0.7,
         f"{location*100:.0f}%" if location is not None else "—"),
        ("테마 동반 상승", theme_up >= 3, f"{theme_up}개"),
        # 시총 1조 위에서만 무겁게 본다. 중소형은 개인이 주도하는 경우가 많다.
        ("외인·기관 동반", both_buy >= 3 if (cap or 0) >= cfg["big_cap"] else both_buy >= 2,
         f"{both_buy}일/5일"),
    ]

    # --- 재료: 사람만 채운다
    material = [
        ("오르는 이유", bool((stock.get("reason") or "").strip()), ""),
        ("내일까지 갈 근거", bool((stock.get("continuation") or "").strip()), ""),
    ]

    blocked = []
    if _finite(daily_metrics.get("change_pct")) is not None and daily_metrics["change_pct"] >= 20:
        blocked.append("오늘 +20% 넘게 올랐습니다")
    if _finite(daily_metrics.get("ret5")) is not None and daily_metrics["ret5"] >= 25:
        blocked.append("5일간 +25% 넘게 올랐습니다")
    if value is not None and value < cfg["min_value"]:
        blocked.append("거래대금이 50억에 못 미칩니다")
    if price is not None and price < cfg["min_price"]:
        blocked.append("주가가 1,000원 미만입니다")

    passed = sum(1 for _n, ok, _v in place + strength if ok)
    return {
        "material": material,
        "place": place,
        "strength": strength,
        "passed": passed,
        "total": len(place) + len(strength),
        "warnings": blocked,          # 막지 않는다. 보여주고 기록만 한다.
        "from_high": from_high,
        "value_ratio": value_ratio,
        "upper_wick": wick,
        "location": location,
        "market_cap": cap,
        "both_buy_days5": both_buy,
    }


def rank(rows: list[dict]) -> list[dict]:
    """볼 만한 것부터 위로 올린다. 점수를 만들지 않는다.

    2026-07-26: 채운 조건 수만으로 세우니 전고점 -62%짜리가 2등에 올라왔다.
    이 매매의 전제는 '전고점 가까운 자리'다. 그게 아닌 종목은 조건을 몇 개
    채웠든 살 자리가 아니므로 아래로 내린다. 되돌아보기에서도 전고점 거리가
    가장 또렷하게 갈렸다(가까울수록 단조롭게 좋아짐).
    """
    def key(row):
        e = row["eval"]
        near = (e["from_high"] or -99) >= -10      # 전고점 10% 밖은 자리가 아니다
        clean = (e["upper_wick"] or 1.0) <= 0.5    # 반 넘게 밀린 날은 뒤로
        return (
            1 if (near and clean and not e["warnings"]) else 0,
            e["passed"],
            e["from_high"] or -99,
        )

    return sorted(rows, key=key, reverse=True)
