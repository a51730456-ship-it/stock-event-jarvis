"""자비스3 상승장용 미국 스윙 종목선정 엔진.

이 모듈은 화면·네트워크·DB와 분리된 순수 계산 계층이다.  계산 순서는
``HARD GATE -> SCORE``이며, 보조점수는 어떤 경우에도 핵심 통과조건을 우회하지
못한다. 가격은 호출자가 넘긴 동일 조정체계의 OHLCV를 그대로 사용한다.
"""

from __future__ import annotations

import copy
import math
import statistics
from datetime import date
from enum import Enum
from typing import Iterable, Mapping

import pandas as pd


MODULE_REVISION = 2026082160
SCORE_MODEL_VERSION = "US_SWING_V1"


class UniverseMode(str, Enum):
    LEGACY_RESEARCH_200 = "LEGACY_RESEARCH_200"
    LIVE_NASDAQ_COMMON = "LIVE_NASDAQ_COMMON"
    PIT_NASDAQ_TOP200 = "PIT_NASDAQ_TOP200"


class AssetType(str, Enum):
    COMMON_STOCK = "COMMON_STOCK"
    ADR = "ADR"
    ETF = "ETF"
    ETN = "ETN"
    PREFERRED = "PREFERRED"
    WARRANT = "WARRANT"
    FUND = "FUND"
    OTHER = "OTHER"


DEFAULT_CONFIG = {
    "universe": {
        "mode": UniverseMode.LIVE_NASDAQ_COMMON.value,
        "include_adr": False,
    },
    "market": {
        "correction_threshold": 0.10,
        "sma_days": 200,
    },
    "rs": {
        "rs60_days": 60,
        "rs120_days": 120,
        "rs60_min_percentile": 80.0,
        "rs120_min_percentile": 80.0,
        "min_cross_section": 30,
        "tiers": (
            (95.0, 25.0),
            (90.0, 23.0),
            (80.0, 20.0),
            (70.0, 12.0),
            (60.0, 6.0),
            (-math.inf, 0.0),
        ),
    },
    "breakout": {
        "lookback_days": 252,
        "price_basis": "close",
        "anchor_reset_on_new_high": True,
    },
    "entry": {
        "watch_start_day": 1,
        "watch_end_day": 3,
        "pullback_min": 0.03,
        "pullback_priority_start": 0.06,
        "pullback_max": 0.10,
        "pullback_watch_near": 0.015,
        "score_points": {
            "priority": 20.0,
            "valid": 16.0,
            "near": 6.0,
            "shallow": 2.0,
        },
    },
    "theme": {
        "lookback_days": 120,
        "min_other_members": 3,
        "min_themes_for_rank": 4,
        "trim_fraction": 0.10,
        # 여러 테마에 속한 종목은 유효 테마 중 percentile이 가장 높은 하나를 쓴다.
        "selection_mode": "BEST_VALID",
        "score_tiers": ((90.0, 10.0), (75.0, 7.0), (50.0, 3.0), (-math.inf, 0.0)),
    },
    "breadth": {
        "sma_days": 50,
        "min_other_members": 3,
        "score_tiers": ((70.0, 5.0), (50.0, 3.0), (30.0, 1.0), (-math.inf, 0.0)),
    },
    "volume": {
        "lookback_days": 20,
        "score_tiers": ((2.0, 8.0), (1.5, 6.0), (1.2, 3.0), (-math.inf, 0.0)),
    },
    "rebound": {
        "score_points": {
            "PRIOR_DAY_HIGH_RECLAIM": 7.0,
            "FIRST_GREEN": 5.0,
            "PULLBACK_TOUCH": 3.0,
            "NONE": 0.0,
        },
    },
    "weights": {
        "rs60": 25.0,
        "rs120": 25.0,
        "pullback": 20.0,
        "theme": 10.0,
        "volume": 8.0,
        "breadth": 5.0,
        "rebound": 7.0,
    },
    "grade": {
        "S": 90.0,
        "A": 80.0,
        "B": 70.0,
        "C": 60.0,
        "D": 0.0,
    },
    "backtest": {
        "signal_mode": "NON_OVERLAP",
        "holding_days": 252,
    },
}


# 화면에 그대로 나가는 글이다. **설명해야 아는 말은 여기 쓰지 않는다.**
# 칸 이름은 그 칸이 던지는 질문 꼴로 적는다(급락 갈래와 같은 방식).
# `one_line`은 늘 보이고, `detail`은 「자세히」를 눌러야 열린다
# (2026-08-20 상하님 지시 — "각 배점 설명서 한줄평 화면에 뿌려라").
SCORE_EXPLANATIONS = {
    "market": {
        "title": "지금 사도 되는 장인가",
        "one_line": "지금이 강한 종목을 사도 되는 나스닥 상승환경인지 확인합니다.",
        "detail": (
            "좋은 종목도 시장 전체가 약하면 성공하기 어렵습니다. 나스닥이 큰 조정을 "
            "끝내고 이전 고점을 다시 회복한 상승환경인지 먼저 확인한 뒤, 그 안에서만 "
            "새로 살 후보를 찾습니다."
        ),
        "confidence": "HIGH",
    },
    "rs60": {
        "title": "최근 3개월, 시장보다 강했나",
        "one_line": "최근 3개월 동안 나스닥보다 얼마나 강하게 오른 종목인지 평가합니다.",
        "detail": (
            "최근 3개월 동안 이 종목이 오른 폭에서 같은 기간 나스닥이 오른 폭을 뺍니다. "
            "나스닥보다 훨씬 많이 오른 종목일수록 높은 점수를 받습니다. "
            "지금까지 여러 번 다시 재도 가장 잘 살아남은 조건입니다."
        ),
        "confidence": "HIGH",
    },
    "rs120": {
        "title": "최근 6개월, 꾸준히 강했나",
        "one_line": "최근 6개월 동안 꾸준히 나스닥보다 강했던 종목인지 평가합니다.",
        "detail": (
            "최근 6개월도 같은 방식으로 나스닥과 견줍니다. "
            "3개월과 6개월이 함께 높으면 잠깐 급등한 종목이 아니라 "
            "한동안 계속 앞서 온 종목일 가능성이 높다고 봅니다."
        ),
        "confidence": "HIGH",
    },
    "breakout": {
        "title": "지난 1년 최고가를 넘었나",
        "one_line": "지난 1년 최고가격을 다시 넘어선 강한 종목인지 확인합니다.",
        "detail": (
            "오늘 종가가 오늘을 뺀 지난 1년의 가장 높은 종가를 넘었는지 봅니다. "
            "1년 동안 막혀 있던 가격을 넘어섰다는 것은 사려는 힘이 세다는 신호로 씁니다. "
            "장중 고가가 아니라 종가로만 봅니다."
        ),
        "confidence": "MEDIUM_HIGH",
    },
    "pullback": {
        "title": "신고가 뒤 알맞게 쉬었나",
        "one_line": (
            "52주 신고가 후 너무 무너지지 않고 좋은 가격까지 정상적으로 눌렸는지 "
            "평가합니다."
        ),
        "detail": (
            "신고가를 넘은 날 바로 쫓아사지 않고 1~3거래일 안에 나오는 조정을 기다립니다. "
            "3~10% 내려온 자리를 정상으로 보고, 그중 6~10%를 조금 더 좋은 자리로 봅니다. "
            "10%보다 깊으면 정상 조정으로 보지 않습니다."
        ),
        "confidence": "MEDIUM",
    },
    "theme": {
        "title": "같은 테마 다른 종목도 강한가",
        "one_line": (
            "이 종목 혼자만 오르는 것이 아니라 같은 테마의 다른 종목들도 강한지 "
            "확인합니다."
        ),
        "detail": (
            "같은 테마 종목들이 함께 강하면 그 테마 전체로 돈이 들어오는 중일 수 있습니다. "
            "이 종목 자신의 상승이 제 테마 점수를 부풀리지 않도록 "
            "계산에서 자기 자신은 뺍니다."
        ),
        "confidence": "EXPERIMENTAL",
    },
    "volume": {
        "title": "신고가 뚫던 날 거래가 늘었나",
        "one_line": (
            "52주 신고가를 돌파할 때 평소보다 많은 거래와 매수 참여가 있었는지 "
            "확인합니다."
        ),
        "detail": (
            "신고가를 넘던 날의 거래량을 그 전 20거래일 평균과 견줍니다(그날은 평균에서 뺍니다). "
            "평소보다 거래가 많았다면 넘어설 때 사람이 더 많이 붙었다는 뜻일 수 있습니다. "
            "다만 앞의 두 항목보다 근거가 약해 보조로만 씁니다."
        ),
        "confidence": "EXPERIMENTAL",
    },
    "breadth": {
        "title": "같은 테마에서 여럿이 함께 오르나",
        "one_line": "같은 테마에서 여러 종목이 함께 강하게 움직이고 있는지 확인합니다.",
        "detail": (
            "같은 테마 종목 가운데 몇 %가 50일선 위에 있는지 셉니다. "
            "한 종목만 우연히 오른 것인지 테마가 통째로 움직이는 것인지를 가릅니다. "
            "아직 더 재 봐야 해서 낮은 몫만 줍니다."
        ),
        "confidence": "EXPERIMENTAL",
    },
    "rebound": {
        "title": "다시 위로 움직이기 시작했나",
        "one_line": "눌림이 끝나고 주가가 다시 위로 움직이기 시작했는지 확인합니다.",
        "detail": (
            "내려온 자리에서 바로 살 수도 있고, 다시 오르는 것을 보고 살 수도 있습니다. "
            "확인하고 사면 더 안전하지만 그만큼 비싸게 사게 됩니다. "
            "그래서 꼭 있어야 하는 조건이 아니라 있으면 더 주는 점수입니다."
        ),
        "confidence": "EXPERIMENTAL",
    },
}


# 배점표 일곱 줄의 차례. 이름은 위 카탈로그 한 군데서만 읽는다 — 두 군데 적어 두면
# 한쪽만 고쳐 화면과 설명이 서로 다른 말을 하게 된다.
SCORE_PART_METRICS = ("rs60", "rs120", "pullback", "theme", "volume", "breadth", "rebound")


def score_part_titles() -> tuple:
    """배점표에 적을 일곱 줄 이름."""
    return tuple(SCORE_EXPLANATIONS[metric]["title"] for metric in SCORE_PART_METRICS)


STATUS_TEXT = {
    "INSUFFICIENT_DATA": "계산에 필요한 자료가 모자랍니다.",
    "MARKET_BLOCKED": "지금 나스닥이 새로 살 만한 상승환경이 아닙니다.",
    "RS60_WEAK": "최근 3개월에 시장보다 강한 상위 20%에 못 듭니다.",
    "RS120_WEAK": "최근 6개월에 시장보다 강한 상위 20%에 못 듭니다.",
    "RS_BOTH_WEAK": "최근 3개월도 6개월도 시장보다 강한 편이 아닙니다.",
    "BREAKOUT_WAIT": "아직 종가로 지난 1년 최고가를 넘지 못했습니다.",
    "ENTRY_WINDOW_NOT_STARTED": "오늘 최고가를 넘었습니다 — 바로 쫓아사지 않고 다음 거래일부터 봅니다.",
    "PULLBACK_WAIT": "강한 종목이지만 아직 3%까지 내려오지 않았습니다.",
    "TOO_DEEP": "강한 종목이지만 10%보다 깊게 내려와 정상 조정으로 보지 않습니다.",
    "ENTRY_WINDOW_EXPIRED": "최고가를 넘은 지 3거래일이 지나 이번 자리는 지났습니다.",
    "PRIMARY_CANDIDATE": "여섯 가지 통과조건을 모두 넘은 신규매수 관찰후보입니다.",
}


# 화면에 나가는 상태 이름을 **사람 말로** 바꾼다 (2026-08-20 상하님 지시 —
# "rs60 뭐 이런거 용어 쓰지말고 일반인이 알기 쉽게 해라").
# 저장하는 값은 영문 상태코드 그대로 두고, **보여줄 때만** 이 표를 거친다 —
# 나중에 다시 재려면 저장된 코드가 그대로 있어야 한다.
PLAIN_STATE = {
    # 시장
    "MARKET_ON": "살 만한 상승환경",
    "MARKET_OFF": "큰 조정 중",
    "MARKET_RECOVERY": "조정에서 되돌아오는 중",
    "MARKET_RISK": "아직 확인하지 못함",
    # 신고가 뒤 눌림
    "NEW_HIGH": "오늘 새 최고가",
    "WAIT_SHALLOW": "아직 얕게 내려옴",
    "VALID_PULLBACK": "3~6% 내려옴",
    "PRIORITY_PULLBACK": "6~10% 내려옴 (더 좋은 자리)",
    "TOO_DEEP": "10%보다 깊게 내려옴",
    # 다시 오르기 시작했나
    "PRIOR_DAY_HIGH_RECLAIM": "어제 고가를 되찾음",
    "FIRST_GREEN": "오늘 처음 올랐음",
    "PULLBACK_TOUCH": "눌림 자리에 막 닿음",
    "NONE": "아직 위로 안 움직임",
    # 3개월·6개월 강함
    "ELITE": "3개월·6개월 모두 최상위",
    "STRONG": "3개월·6개월 모두 상위 20%",
    "MIXED": "한쪽만 강함",
    "WEAK": "3개월도 6개월도 약함",
    # 못 잰 까닭
    "OK": "잘 쟀음",
    "NO_THEME_MEMBERSHIP": "테마 명부에 아직 없는 종목",
    "THEME_DATA_INSUFFICIENT": "견줄 테마가 모자람",
    "THEME_MEMBER_DATA_INSUFFICIENT": "같은 테마 다른 종목이 모자람",
    "BREADTH_DATA_INSUFFICIENT": "같은 테마 다른 종목이 모자람",
    "VOLUME_DATA_INSUFFICIENT": "돌파일 앞 20일 거래량이 모자람",
    "INSUFFICIENT_DATA": "자료가 모자람",
    "INSUFFICIENT_INDEX_HISTORY": "나스닥 이력이 모자람",
    "RS_RANK_UNRELIABLE": "견줄 종목이 30개가 안 됨",
}


# 「얼마나 믿을 만한 항목인가」도 화면에는 사람 말로 적는다.
CONFIDENCE_TEXT = {
    "HIGH": "여러 번 다시 재도 살아남은 조건",
    "MEDIUM_HIGH": "꽤 여러 번 확인한 조건",
    "MEDIUM": "확인은 했지만 더 재 봐야 하는 조건",
    "EXPERIMENTAL": "아직 더 재 봐야 하는 조건",
}


# 표 칸에 넣을 **짧은 말**. 긴 설명(STATUS_TEXT)은 손을 올리면 뜬다.
# 칸에 긴 문장을 그대로 넣으면 옆 칸 글자를 덮는다(2026-08-21 상하님 지적).
SHORT_STATUS = {
    "INSUFFICIENT_DATA": "자료 부족",
    "MARKET_BLOCKED": "장이 아님",
    "RS60_WEAK": "3개월 약함",
    "RS120_WEAK": "6개월 약함",
    "RS_BOTH_WEAK": "3·6개월 약함",
    "BREAKOUT_WAIT": "최고가 못 넘음",
    "ENTRY_WINDOW_NOT_STARTED": "오늘 넘음",
    "PULLBACK_WAIT": "덜 내려옴",
    "TOO_DEEP": "너무 깊음",
    "ENTRY_WINDOW_EXPIRED": "때 지남",
    "PRIMARY_CANDIDATE": "정식 후보",
}


def short_status(code) -> str:
    """상태코드 → 표 칸에 넣을 짧은 말."""
    text = str(code or "").strip()
    return SHORT_STATUS.get(text, text or "—")


def plain_confidence(code) -> str:
    """연구 신뢰도 코드 → 화면에 적을 말."""
    return CONFIDENCE_TEXT.get(str(code or "").strip(), "")


def plain_state(code) -> str:
    """상태코드 → 화면에 적을 말. 모르는 코드는 그대로 돌려준다."""
    text = str(code or "").strip()
    return PLAIN_STATE.get(text, text)


GRADE_TEXT = {
    "S": "핵심조건과 보조조건이 모두 매우 강한 최우선 관찰후보",
    "A": "핵심조건이 강하고 여러 보조조건도 좋은 우수 후보",
    "B": "핵심조건은 통과했으나 일부 보조조건이 부족한 후보",
    "C": "기본조건은 충족했지만 우선순위가 낮은 후보",
    "D": "현재 점수상 신규매수 우선순위가 낮음",
}


def merged_config(overrides: Mapping | None = None) -> dict:
    """기본 설정 복사본에 중첩 override를 합치고 검증한다."""

    config = copy.deepcopy(DEFAULT_CONFIG)

    def merge(target: dict, source: Mapping) -> None:
        for key, value in source.items():
            if isinstance(value, Mapping) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = copy.deepcopy(value)

    if overrides:
        merge(config, overrides)
    validate_config(config)
    return config


def validate_config(config: Mapping) -> None:
    weights = config.get("weights") or {}
    expected = {"rs60", "rs120", "pullback", "theme", "volume", "breadth", "rebound"}
    if set(weights) != expected:
        raise ValueError(f"weights 항목은 {sorted(expected)}여야 합니다")
    if not math.isclose(sum(float(value) for value in weights.values()), 100.0, abs_tol=1e-9):
        raise ValueError("미국 스윙 배점 합계는 정확히 100이어야 합니다")
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in weights.values()):
        raise ValueError("미국 스윙 항목별 배점은 0 이상의 유한한 숫자여야 합니다")
    entry = config.get("entry") or {}
    if not (
        0 <= float(entry.get("pullback_watch_near", -1))
        <= float(entry.get("pullback_min", -1))
        <= float(entry.get("pullback_priority_start", -1))
        <= float(entry.get("pullback_max", -1))
    ):
        raise ValueError("눌림 설정은 watch_near <= min <= priority <= max 순서여야 합니다")
    if int(entry.get("watch_start_day", 0)) > int(entry.get("watch_end_day", -1)):
        raise ValueError("진입 관찰 시작일은 종료일보다 늦을 수 없습니다")


validate_config(DEFAULT_CONFIG)


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _boundary_number(value, digits: int = 10) -> float | None:
    """가격 나눗셈의 2.99999999999999 같은 표현오차만 정규화한다."""

    number = _finite(value)
    return None if number is None else round(number, int(digits))


def _as_timestamp(value) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_localize(None)
    return stamp.normalize()


def _clean_frame(frame: pd.DataFrame | None, as_of=None) -> pd.DataFrame:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(-1)
    out.columns = [str(column).title() for column in out.columns]
    if "Close" not in out.columns:
        return pd.DataFrame()
    index = pd.DatetimeIndex(out.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    out.index = index.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["Close"])
    target = _as_timestamp(as_of)
    if target is not None:
        out = out[out.index <= target]
    return out


def relative_strength_raw(stock_close: Iterable, index_close: Iterable, days: int) -> float | None:
    """종목 N일 수익률 - IXIC N일 수익률을 소수 단위로 반환한다."""

    stock = pd.Series(stock_close, dtype="float64").dropna()
    index = pd.Series(index_close, dtype="float64").dropna()
    days = int(days)
    if days <= 0 or len(stock) <= days or len(index) <= days:
        return None
    # 날짜 index가 있으면 Nasdaq의 t와 t-N 날짜를 기준으로 양쪽 끝점을 정확히
    # 맞춘다. 종목에 중간 결측일이 있다고 각 Series의 ``-N`` 위치를 따로 쓰면
    # 서로 다른 기간 수익률을 빼는 오류가 생긴다.
    if isinstance(stock.index, pd.DatetimeIndex) and isinstance(index.index, pd.DatetimeIndex):
        now_date = index.index[-1]
        then_date = index.index[-days - 1]
        if now_date not in stock.index or then_date not in stock.index:
            return None
        stock_now, stock_then = _finite(stock.loc[now_date]), _finite(stock.loc[then_date])
        index_now, index_then = _finite(index.loc[now_date]), _finite(index.loc[then_date])
    else:
        stock_now, stock_then = _finite(stock.iloc[-1]), _finite(stock.iloc[-days - 1])
        index_now, index_then = _finite(index.iloc[-1]), _finite(index.iloc[-days - 1])
    if not stock_now or not stock_then or not index_now or not index_then:
        return None
    return (stock_now / stock_then - 1.0) - (index_now / index_then - 1.0)


def percentile_ranks(values: Mapping[str, float | None]) -> dict[str, float]:
    """내림차순 average-rank percentile. 가장 강함 100, 가장 약함 0."""

    valid = [(str(key), _finite(value)) for key, value in values.items()]
    valid = [(key, value) for key, value in valid if value is not None]
    if not valid:
        return {}
    if len(valid) == 1:
        return {valid[0][0]: 100.0}
    valid.sort(key=lambda item: (-item[1], item[0]))
    result: dict[str, float] = {}
    cursor = 0
    count = len(valid)
    while cursor < count:
        end = cursor + 1
        while end < count and math.isclose(valid[end][1], valid[cursor][1], rel_tol=0, abs_tol=1e-12):
            end += 1
        # 위치는 1부터 시작하며 동률은 차지한 위치의 평균 rank를 쓴다.
        average_rank = ((cursor + 1) + end) / 2.0
        percentile = 100.0 * (count - average_rank) / (count - 1)
        for key, _value in valid[cursor:end]:
            result[key] = percentile
        cursor = end
    return result


def rank_positions(values: Mapping[str, float | None]) -> dict[str, int]:
    """내림차순 등수. 가장 강한 것이 1등, 동률은 같은 등수 (2026-08-21).

    상하님 — *"3개월 상위, 6개월 상위라고 해놓으니 무슨 말인지 모르겠다."*
    「상위 1.0%」보다 「2등 / 199」가 한눈에 읽힌다. percentile은 점수 계산에
    그대로 쓰고, **화면에 적을 때만** 이 등수를 쓴다.
    """
    valid = [(str(key), _finite(value)) for key, value in values.items()]
    valid = [(key, value) for key, value in valid if value is not None]
    if not valid:
        return {}
    valid.sort(key=lambda item: (-item[1], item[0]))
    result: dict[str, int] = {}
    cursor = 0
    count = len(valid)
    while cursor < count:
        end = cursor + 1
        while end < count and math.isclose(valid[end][1], valid[cursor][1], rel_tol=0, abs_tol=1e-12):
            end += 1
        for key, _value in valid[cursor:end]:
            result[key] = cursor + 1
        cursor = end
    return result


def rs_points(percentile, *, max_points: float = 25.0, config: Mapping | None = None) -> float:
    value = _finite(percentile)
    if value is None:
        return 0.0
    cfg = config or DEFAULT_CONFIG
    for lower, base_points in cfg["rs"]["tiers"]:
        if value >= float(lower):
            return round(float(base_points) * float(max_points) / 25.0, 6)
    return 0.0


def pullback_state(pullback_pct, config: Mapping | None = None) -> str:
    value = _boundary_number(pullback_pct)
    if value is None:
        return "INSUFFICIENT_DATA"
    cfg = config or DEFAULT_CONFIG
    entry = cfg["entry"]
    low = float(entry["pullback_min"]) * 100.0
    priority = float(entry["pullback_priority_start"]) * 100.0
    high = float(entry["pullback_max"]) * 100.0
    if value < 0:
        return "NEW_HIGH"
    if value < low:
        return "WAIT_SHALLOW"
    if value < priority:
        return "VALID_PULLBACK"
    if value <= high:
        return "PRIORITY_PULLBACK"
    return "TOO_DEEP"


def pullback_points(pullback_pct, *, max_points: float = 20.0, config: Mapping | None = None) -> float:
    value = _boundary_number(pullback_pct)
    if value is None or value < 0:
        return 0.0
    cfg = config or DEFAULT_CONFIG
    entry = cfg["entry"]
    near = float(entry["pullback_watch_near"]) * 100.0
    low = float(entry["pullback_min"]) * 100.0
    priority = float(entry["pullback_priority_start"]) * 100.0
    high = float(entry["pullback_max"]) * 100.0
    points = entry["score_points"]
    if priority <= value <= high:
        base = float(points["priority"])
    elif low <= value < priority:
        base = float(points["valid"])
    elif near <= value < low:
        base = float(points["near"])
    elif 0 <= value < near:
        base = float(points["shallow"])
    else:
        base = 0.0
    return round(base * float(max_points) / 20.0, 6)


def theme_points(
    percentile, *, max_points: float = 10.0, config: Mapping | None = None,
) -> float:
    value = _finite(percentile)
    if value is None:
        return 0.0
    cfg = config or DEFAULT_CONFIG
    base = next(float(points) for lower, points in cfg["theme"]["score_tiers"] if value >= float(lower))
    return round(base * float(max_points) / 10.0, 6)


def breadth_points(
    percentile, *, max_points: float = 5.0, config: Mapping | None = None,
) -> float:
    value = _finite(percentile)
    if value is None:
        return 0.0
    cfg = config or DEFAULT_CONFIG
    base = next(float(points) for lower, points in cfg["breadth"]["score_tiers"] if value >= float(lower))
    return round(base * float(max_points) / 5.0, 6)


def volume_points(rvol, *, max_points: float = 8.0, config: Mapping | None = None) -> float:
    value = _finite(rvol)
    if value is None:
        return 0.0
    cfg = config or DEFAULT_CONFIG
    base = next(float(points) for lower, points in cfg["volume"]["score_tiers"] if value >= float(lower))
    return round(base * float(max_points) / 8.0, 6)


def rebound_points(
    status: str, *, max_points: float = 7.0, config: Mapping | None = None,
) -> float:
    cfg = config or DEFAULT_CONFIG
    base = float(cfg["rebound"]["score_points"].get(str(status or ""), 0.0))
    return round(base * float(max_points) / 7.0, 6)


def market_gate(frame: pd.DataFrame, *, as_of=None, config: Mapping | None = None) -> dict:
    """IXIC 종가 ATH → 설정 조정 → 이전 ATH 회복의 상태기를 계산한다."""

    cfg = config or DEFAULT_CONFIG
    clean = _clean_frame(frame, as_of)
    closes = clean.get("Close", pd.Series(dtype="float64")).dropna().astype(float)
    threshold = float(cfg["market"]["correction_threshold"])
    sma_days = int(cfg["market"]["sma_days"])
    if len(closes) < max(2, sma_days):
        return {
            "valid": False,
            "market_status": "MARKET_RISK",
            "reason": "INSUFFICIENT_INDEX_HISTORY",
            "correction_threshold": threshold,
        }

    running_peak = float(closes.iloc[0])
    recovery_ath = running_peak
    correction_active = False
    confirmed_on = False
    reclaim_position: int | None = None
    status = "MARKET_RISK"

    for position, close in enumerate(closes.astype(float)):
        if correction_active and close > recovery_ath:
            correction_active = False
            confirmed_on = True
            reclaim_position = position
        if close > running_peak:
            running_peak = close
        drawdown = round(close / running_peak - 1.0, 12)
        if drawdown <= -threshold:
            if not correction_active:
                recovery_ath = running_peak
            correction_active = True
            confirmed_on = False
            status = "MARKET_OFF"
        elif correction_active:
            status = "MARKET_RECOVERY"
        elif confirmed_on:
            status = "MARKET_ON"
        else:
            # 주어진 역사 안에서 '조정 뒤 회복'을 확인하지 못한 초기 구간.
            status = "MARKET_RISK"

    current = float(closes.iloc[-1])
    sma200 = float(closes.tail(sma_days).mean())
    drawdown = round(current / float(closes.cummax().iloc[-1]) - 1.0, 12)
    return {
        "valid": True,
        "date": closes.index[-1].date().isoformat(),
        "market_status": status,
        "ixic_close": current,
        "ixic_sma200": sma200,
        "ixic_above_sma200": current > sma200,
        "market_drawdown": drawdown,
        "distance_from_running_ath": drawdown,
        "days_since_market_reclaim": (
            len(closes) - 1 - reclaim_position if reclaim_position is not None else None
        ),
        "reclaim_ath": recovery_ath,
        "correction_threshold": threshold,
        "reason": status,
    }


def latest_breakout(
    frame: pd.DataFrame, *, as_of=None, config: Mapping | None = None,
    trading_index: Iterable | None = None,
) -> dict:
    """오늘을 제외한 직전 252종가 최고를 strict ``>``로 넘은 최신 anchor."""

    cfg = config or DEFAULT_CONFIG
    clean = _clean_frame(frame, as_of)
    lookback = int(cfg["breakout"]["lookback_days"])
    closes = clean.get("Close", pd.Series(dtype="float64")).dropna().astype(float)
    if len(closes) <= lookback:
        return {"valid": False, "reason": "INSUFFICIENT_BREAKOUT_HISTORY"}
    previous_high = closes.shift(1).rolling(lookback, min_periods=lookback).max()
    hits = (closes > previous_high) & previous_high.notna()
    positions = [index for index, matched in enumerate(hits.tolist()) if bool(matched)]
    if not positions:
        return {
            "valid": True,
            "has_breakout": False,
            "previous_252_high_close": _finite(previous_high.iloc[-1]),
        }
    if bool(cfg["breakout"]["anchor_reset_on_new_high"]):
        anchor_position = positions[-1]
    else:
        # 최신 연속 신고가 묶음의 첫날을 anchor로 둔다.
        anchor_position = positions[-1]
        while anchor_position - 1 in positions:
            anchor_position -= 1
    anchor_date = closes.index[anchor_position]
    anchor_close = float(closes.iloc[anchor_position])
    current_close = float(closes.iloc[-1])
    low = clean.get("Low")
    current_low = _finite(low.iloc[-1]) if low is not None and len(low) else None
    pullback_close = _boundary_number((anchor_close - current_close) / anchor_close * 100.0)
    pullback_low = (
        _boundary_number((anchor_close - current_low) / anchor_close * 100.0)
        if current_low is not None else None
    )
    prior = float(previous_high.iloc[anchor_position])

    volume = clean.get("Volume")
    breakout_volume = None
    volume_avg20 = None
    breakout_rvol = None
    volume_lookback = int(cfg["volume"]["lookback_days"])
    if volume is not None and anchor_position >= volume_lookback:
        volume_window = pd.to_numeric(
            volume.iloc[anchor_position - volume_lookback:anchor_position], errors="coerce"
        )
        breakout_volume = _finite(volume.iloc[anchor_position])
        if len(volume_window) == volume_lookback and volume_window.notna().all():
            volume_avg20 = _finite(volume_window.mean())
        if breakout_volume is not None and volume_avg20 and volume_avg20 > 0:
            breakout_rvol = breakout_volume / volume_avg20

    if trading_index is None:
        days_since_anchor = len(closes) - 1 - anchor_position
    else:
        market_days = pd.DatetimeIndex(trading_index)
        if market_days.tz is not None:
            market_days = market_days.tz_localize(None)
        market_days = market_days.normalize().unique().sort_values()
        days_since_anchor = int(
            ((market_days > anchor_date) & (market_days <= closes.index[-1])).sum()
        )

    return {
        "valid": True,
        "has_breakout": True,
        "breakout_date": anchor_date.date().isoformat(),
        "breakout_close": anchor_close,
        "previous_252_high_close": prior,
        "breakout_pct_above_prior_high": _boundary_number((anchor_close / prior - 1.0) * 100.0),
        "anchor_date": anchor_date.date().isoformat(),
        "anchor_close": anchor_close,
        "days_since_anchor": days_since_anchor,
        "pullback_pct_close": pullback_close,
        "pullback_pct_low": pullback_low,
        "breakout_volume": breakout_volume,
        "volume_avg20": volume_avg20,
        "breakout_rvol": breakout_rvol,
        "volume_valid": breakout_rvol is not None,
    }


def _trimmed_mean(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    trim = int(len(ordered) * max(0.0, min(float(fraction), 0.49)))
    kept = ordered[trim:len(ordered) - trim] if trim else ordered
    return statistics.fmean(kept) if kept else None


def _theme_metrics_for_ticker(
    ticker: str,
    memberships: Mapping[str, Iterable[str]],
    rs120: Mapping[str, float | None],
    above_sma50: Mapping[str, bool | None],
    config: Mapping,
) -> dict:
    own_themes = list(dict.fromkeys(str(name) for name in memberships.get(ticker, ()) if name))
    if not own_themes:
        return {
            "theme_id": None,
            "theme_valid": False,
            "theme_reason": "NO_THEME_MEMBERSHIP",
            "breadth_valid": False,
            "breadth_reason": "NO_THEME_MEMBERSHIP",
        }
    theme_members: dict[str, list[str]] = {}
    for member, names in memberships.items():
        for name in names or ():
            theme_members.setdefault(str(name), []).append(str(member))

    min_members = int(config["theme"]["min_other_members"])
    trim_fraction = float(config["theme"]["trim_fraction"])
    theme_stats: dict[str, dict] = {}
    for name, members in theme_members.items():
        others = [member for member in members if member != ticker]
        values = [float(rs120[member]) for member in others if _finite(rs120.get(member)) is not None]
        if len(values) < min_members:
            continue
        theme_stats[name] = {
            "raw": statistics.fmean(values),
            "median": statistics.median(values),
            "trimmed_mean": _trimmed_mean(values, trim_fraction),
            "members": others,
        }
    if len(theme_stats) < int(config["theme"]["min_themes_for_rank"]):
        return {
            "theme_id": own_themes[0],
            "theme_valid": False,
            "theme_reason": "THEME_DATA_INSUFFICIENT",
            "valid_theme_count": len(theme_stats),
            "breadth_valid": False,
            "breadth_reason": "THEME_DATA_INSUFFICIENT",
        }
    percentiles = percentile_ranks({name: stats["raw"] for name, stats in theme_stats.items()})
    available = [name for name in own_themes if name in theme_stats and name in percentiles]
    if not available:
        return {
            "theme_id": own_themes[0],
            "theme_valid": False,
            "theme_reason": "THEME_MEMBER_DATA_INSUFFICIENT",
            "valid_theme_count": len(theme_stats),
            "breadth_valid": False,
            "breadth_reason": "THEME_MEMBER_DATA_INSUFFICIENT",
        }
    chosen = sorted(
        available,
        key=lambda name: (-percentiles[name], -theme_stats[name]["raw"], name),
    )[0]
    chosen_stats = theme_stats[chosen]
    breadth_values = [above_sma50.get(member) for member in chosen_stats["members"]]
    breadth_values = [bool(value) for value in breadth_values if value is not None]
    breadth_min = int(config["breadth"]["min_other_members"])
    breadth_valid = len(breadth_values) >= breadth_min
    breadth_pct = (
        100.0 * sum(1 for value in breadth_values if value) / len(breadth_values)
        if breadth_valid else None
    )
    return {
        "theme_id": chosen,
        "theme_strength_raw": chosen_stats["raw"],
        "theme_strength_median": chosen_stats["median"],
        "theme_strength_trimmed_mean": chosen_stats["trimmed_mean"],
        "theme_percentile": percentiles[chosen],
        "theme_valid": True,
        "theme_reason": "OK",
        "valid_theme_count": len(theme_stats),
        "breadth_pct": breadth_pct,
        "breadth_valid": breadth_valid,
        "breadth_reason": "OK" if breadth_valid else "BREADTH_DATA_INSUFFICIENT",
    }


def _rebound_status(
    frame: pd.DataFrame, pullback_status: str, anchor_close, config: Mapping | None = None,
) -> str:
    if pullback_status not in {"VALID_PULLBACK", "PRIORITY_PULLBACK"}:
        return "NONE"
    clean = _clean_frame(frame)
    if len(clean) < 2:
        return "PULLBACK_TOUCH"
    close = _finite(clean["Close"].iloc[-1])
    previous_close = _finite(clean["Close"].iloc[-2])
    previous_high = _finite(clean["High"].iloc[-2]) if "High" in clean.columns else None
    if close is not None and previous_high is not None and close > previous_high:
        return "PRIOR_DAY_HIGH_RECLAIM"
    if close is not None and previous_close is not None and close > previous_close:
        return "FIRST_GREEN"
    anchor = _finite(anchor_close)
    if anchor and previous_close is not None:
        previous_pullback = (anchor - previous_close) / anchor * 100.0
        if pullback_state(previous_pullback, config) not in {"VALID_PULLBACK", "PRIORITY_PULLBACK"}:
            return "PULLBACK_TOUCH"
    return "NONE"


def _rs_core_status(rs60, rs120) -> str:
    left, right = _finite(rs60), _finite(rs120)
    if left is None or right is None:
        return "UNAVAILABLE"
    if left >= 90 and right >= 90:
        return "ELITE"
    if left >= 80 and right >= 80:
        return "STRONG"
    if left >= 80 or right >= 80:
        return "MIXED"
    return "WEAK"


def _candidate_status(row: Mapping, config: Mapping) -> tuple[str, bool]:
    if not row.get("core_data_valid"):
        return "INSUFFICIENT_DATA", False
    if row.get("market_status") != "MARKET_ON":
        return "MARKET_BLOCKED", False
    weak60 = float(row["rs60_percentile"]) < float(config["rs"]["rs60_min_percentile"])
    weak120 = float(row["rs120_percentile"]) < float(config["rs"]["rs120_min_percentile"])
    if weak60 and weak120:
        return "RS_BOTH_WEAK", False
    if weak60:
        return "RS60_WEAK", False
    if weak120:
        return "RS120_WEAK", False
    if not row.get("has_valid_52w_breakout"):
        return "BREAKOUT_WAIT", False
    days = int(row.get("days_since_anchor") or 0)
    if days < int(config["entry"]["watch_start_day"]):
        return "ENTRY_WINDOW_NOT_STARTED", False
    state = row.get("pullback_status")
    if state == "TOO_DEEP":
        return "TOO_DEEP", False
    if days > int(config["entry"]["watch_end_day"]):
        return "ENTRY_WINDOW_EXPIRED", False
    if state not in {"VALID_PULLBACK", "PRIORITY_PULLBACK"}:
        return "PULLBACK_WAIT", False
    return "PRIMARY_CANDIDATE", True


def grade_for(total_score, eligible: bool, config: Mapping | None = None) -> str | None:
    if not eligible:
        return None
    value = float(total_score or 0.0)
    cfg = config or DEFAULT_CONFIG
    for grade in ("S", "A", "B", "C", "D"):
        if value >= float(cfg["grade"][grade]):
            return grade
    return "D"


def candidate_sort_key(row: Mapping) -> tuple:
    def descending(name: str) -> float:
        value = _finite(row.get(name))
        return -(value if value is not None else -math.inf)

    return (
        0 if row.get("eligible_primary") else 1,
        descending("total_score"),
        descending("core_score"),
        descending("rs120_percentile"),
        descending("rs60_percentile"),
        descending("pullback_score"),
        descending("avg_dollar_volume_20"),
        str(row.get("ticker") or ""),
    )


def _display_value(metric: str, row: Mapping) -> str:
    if metric == "market":
        return plain_state(row.get("market_status")) or "자료부족"
    if metric in {"rs60", "rs120"}:
        # **「상위 몇 %」 대신 「몇 등」이다**(2026-08-21 상하님 — "무슨 말인지
        # 모르겠다"). 명부 몇 개 중 몇 등인지가 한눈에 읽힌다.
        rank = row.get(f"{metric}_rank")
        total = row.get("rs_ranked_count")
        if rank and total:
            return f"{int(rank)}등 / {int(total)}"
        value = _finite(row.get(f"{metric}_percentile"))
        if value is None:
            return "자료부족"
        return f"상위 {max(0.0, 100.0 - value):.1f}%"
    if metric == "breakout":
        return str(row.get("breakout_date") or "신고가 대기")
    if metric == "pullback":
        value = _finite(row.get("pullback_pct_close"))
        return "자료부족" if value is None else f"-{value:.1f}%"
    if metric == "theme":
        value = _finite(row.get("theme_percentile"))
        if value is None:
            return "자료부족"
        name = row.get("theme_id") or "테마"
        top = max(0.0, 100.0 - value)
        return f"{name} 테마가 가장 강함" if top < 0.05 else f"{name} 상위 {top:.1f}%"
    if metric == "volume":
        value = _finite(row.get("breakout_rvol"))
        return "자료부족" if value is None else f"평균의 {value:.2f}배"
    if metric == "breadth":
        value = _finite(row.get("breadth_pct"))
        return "자료부족" if value is None else f"{value:.1f}%"
    if metric == "rebound":
        return plain_state(row.get("rebound_status") or "NONE")
    return "—"


def explanation_payload(row: Mapping, config: Mapping | None = None) -> dict[str, dict]:
    score_fields = {
        "rs60": "rs60_score",
        "rs120": "rs120_score",
        "pullback": "pullback_score",
        "theme": "theme_score",
        "volume": "volume_score",
        "breadth": "breadth_score",
        "rebound": "rebound_score",
    }
    max_scores = {
        "market": 0.0,
        "breakout": 0.0,
        **{key: float((config or DEFAULT_CONFIG)["weights"][key]) for key in score_fields},
    }
    payload = {}
    for metric in ("market", "rs60", "rs120", "breakout", "pullback", "theme", "volume", "breadth", "rebound"):
        source = SCORE_EXPLANATIONS[metric]
        payload[metric] = {
            "metric": metric,
            "title": source["title"],
            "score": float(row.get(score_fields.get(metric), 0.0) or 0.0),
            "max_score": max_scores[metric],
            "current_value": row.get({
                "market": "market_status", "rs60": "rs60_percentile", "rs120": "rs120_percentile",
                "breakout": "breakout_date", "pullback": "pullback_pct_close",
                "theme": "theme_percentile", "volume": "breakout_rvol",
                "breadth": "breadth_pct", "rebound": "rebound_status",
            }[metric]),
            "display_value": _display_value(metric, row),
            "one_line_explanation": source["one_line"],
            "detail_explanation": source["detail"],
            # 저장은 영문 코드로 하고 **보여줄 때만** 사람 말로 바꾼다.
            "status": plain_state(row.get({
                "market": "market_status", "breakout": "primary_status", "pullback": "pullback_status",
                "theme": "theme_reason", "volume": "volume_reason", "breadth": "breadth_reason",
                "rebound": "rebound_status", "rs60": "rs_core_status", "rs120": "rs_core_status",
            }[metric]) if metric != "breakout" else
            STATUS_TEXT.get(str(row.get("primary_status") or ""), row.get("primary_status"))),
            "status_code": row.get({
                "market": "market_status", "breakout": "primary_status", "pullback": "pullback_status",
                "theme": "theme_reason", "volume": "volume_reason", "breadth": "breadth_reason",
                "rebound": "rebound_status", "rs60": "rs_core_status", "rs120": "rs_core_status",
            }[metric]),
            "confidence": source["confidence"],
        }
    return payload


def _accepted_asset(asset_type: str, config: Mapping) -> bool:
    if asset_type == AssetType.COMMON_STOCK.value:
        return True
    return bool(config["universe"].get("include_adr")) and asset_type == AssetType.ADR.value


def _failed_gates(row: Mapping, config: Mapping) -> list[str]:
    """대표 상태와 별개로 실패한 HARD GATE를 모두 보존한다."""

    failed: list[str] = []
    if not row.get("market_valid"):
        failed.append(str(row.get("market_reason") or "MARKET_DATA_INSUFFICIENT"))
    elif row.get("market_status") != "MARKET_ON":
        failed.append("MARKET_BLOCKED")
    if not row.get("rs60_valid"):
        failed.append(str(row.get("rs60_reason") or "RS60_DATA_INSUFFICIENT"))
    elif float(row.get("rs60_percentile")) < float(config["rs"]["rs60_min_percentile"]):
        failed.append("RS60_WEAK")
    if not row.get("rs120_valid"):
        failed.append(str(row.get("rs120_reason") or "RS120_DATA_INSUFFICIENT"))
    elif float(row.get("rs120_percentile")) < float(config["rs"]["rs120_min_percentile"]):
        failed.append("RS120_WEAK")
    if not row.get("breakout_data_valid"):
        failed.append(str(row.get("breakout_reason") or "BREAKOUT_DATA_INSUFFICIENT"))
    elif not row.get("has_valid_52w_breakout"):
        failed.append("BREAKOUT_WAIT")
    else:
        days = int(row.get("days_since_anchor") or 0)
        if days < int(config["entry"]["watch_start_day"]):
            failed.append("ENTRY_WINDOW_NOT_STARTED")
        elif days > int(config["entry"]["watch_end_day"]):
            failed.append("ENTRY_WINDOW_EXPIRED")
        pullback = _finite(row.get("pullback_pct_close"))
        if pullback is None:
            failed.append("PULLBACK_DATA_INSUFFICIENT")
        elif pullback < float(config["entry"]["pullback_min"]) * 100.0:
            failed.append("PULLBACK_WAIT")
        elif pullback > float(config["entry"]["pullback_max"]) * 100.0:
            failed.append("TOO_DEEP")
    return list(dict.fromkeys(failed))


def scan_eod(
    prices: Mapping[str, pd.DataFrame],
    ixic: pd.DataFrame,
    memberships: Mapping[str, Iterable[str]],
    *,
    universe_records: Iterable[Mapping] | None = None,
    universe_mode: str | UniverseMode | None = None,
    as_of=None,
    config: Mapping | None = None,
) -> dict:
    """한 거래일 EOD 후보·관찰목록 전체를 계산한다."""

    cfg = merged_config(config) if config is not None else merged_config()
    mode = (
        universe_mode.value if isinstance(universe_mode, UniverseMode)
        else str(universe_mode or cfg["universe"]["mode"])
    )
    allowed_modes = {item.value for item in UniverseMode}
    if mode not in allowed_modes:
        return {"ok": False, "error": f"지원하지 않는 universe_mode입니다: {mode}", "rows": [], "watch_rows": []}
    index_frame = _clean_frame(ixic, as_of)
    if index_frame.empty:
        return {"ok": False, "error": "Nasdaq Composite 일봉이 없습니다", "rows": [], "watch_rows": []}
    # as_of가 휴일·미래일이어도 실제 마지막 IXIC 거래일을 EOD 기준일로 쓴다.
    # 요청 날짜를 그대로 종목 index와 비교하면 모든 종목이 자료부족으로 바뀐다.
    target = index_frame.index[-1]
    market = market_gate(index_frame, as_of=target, config=cfg)

    if universe_records is None:
        records = [
            {"ticker": ticker, "name": ticker, "asset_type": AssetType.COMMON_STOCK.value}
            for ticker in prices
            if str(ticker).upper() not in {"^IXIC", "IXIC"}
        ]
    else:
        records = [dict(record) for record in universe_records]
    normalized_records = []
    seen = set()
    for record in records:
        ticker = str(record.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        raw_asset_type = record.get("asset_type") or AssetType.OTHER.value
        asset_type = (
            raw_asset_type.value if isinstance(raw_asset_type, AssetType)
            else str(raw_asset_type).upper()
        )
        if not _accepted_asset(asset_type, cfg):
            continue
        effective_from = _as_timestamp(record.get("effective_from"))
        effective_to = _as_timestamp(record.get("effective_to"))
        if mode == UniverseMode.PIT_NASDAQ_TOP200.value and effective_from is None:
            return {
                "ok": False,
                "error": "PIT_NASDAQ_TOP200에는 종목별 effective_from이 필요합니다",
                "rows": [], "watch_rows": [],
            }
        if effective_from is not None and target < effective_from:
            continue
        if effective_to is not None and target > effective_to:
            continue
        seen.add(ticker)
        normalized_records.append({**record, "ticker": ticker, "asset_type": asset_type})

    index_closes = index_frame["Close"].astype(float)
    frames: dict[str, pd.DataFrame] = {}
    raw60: dict[str, float | None] = {}
    raw120: dict[str, float | None] = {}
    above50: dict[str, bool | None] = {}
    avg_dollar: dict[str, float | None] = {}
    for record in normalized_records:
        ticker = record["ticker"]
        frame = _clean_frame(prices.get(ticker), target)
        frames[ticker] = frame
        closes = frame.get("Close", pd.Series(dtype="float64")).astype(float)
        exact_date = not frame.empty and frame.index[-1] == target
        if not exact_date:
            raw60[ticker] = None
            raw120[ticker] = None
            above50[ticker] = None
            avg_dollar[ticker] = None
            continue
        raw60[ticker] = relative_strength_raw(closes, index_closes, int(cfg["rs"]["rs60_days"]))
        raw120[ticker] = relative_strength_raw(closes, index_closes, int(cfg["rs"]["rs120_days"]))
        breadth_days = int(cfg["breadth"]["sma_days"])
        above50[ticker] = (
            bool(closes.iloc[-1] > closes.tail(breadth_days).mean())
            if len(closes) >= breadth_days else None
        )
        if "Volume" in frame.columns and len(frame) >= 21:
            dollar = (frame["Close"].astype(float) * frame["Volume"].astype(float)).iloc[-21:-1]
            avg_dollar[ticker] = (
                _finite(dollar.mean()) if len(dollar) == 20 and dollar.notna().all() else None
            )
        else:
            avg_dollar[ticker] = None

    percent60 = percentile_ranks(raw60)
    percent120 = percentile_ranks(raw120)
    # 화면에 적을 등수. 점수는 위 percentile로 그대로 매긴다(2026-08-21).
    rank60 = rank_positions(raw60)
    rank120 = rank_positions(raw120)
    cross60_ok = len(percent60) >= int(cfg["rs"]["min_cross_section"])
    cross120_ok = len(percent120) >= int(cfg["rs"]["min_cross_section"])

    rows = []
    weights = cfg["weights"]
    for record in normalized_records:
        ticker = record["ticker"]
        frame = frames[ticker]
        rs60_pct = percent60.get(ticker)
        rs120_pct = percent120.get(ticker)
        breakout = latest_breakout(
            frame, as_of=target, config=cfg, trading_index=index_frame.index,
        )
        pb_pct = breakout.get("pullback_pct_close")
        pb_status = pullback_state(pb_pct, cfg) if breakout.get("has_breakout") else "NOT_AVAILABLE"
        theme = _theme_metrics_for_ticker(ticker, memberships, raw120, above50, cfg)
        rebound_status = _rebound_status(frame, pb_status, breakout.get("anchor_close"), cfg)

        row = {
            "date": target.date().isoformat(),
            "ticker": ticker,
            "name": str(record.get("name") or ticker),
            "asset_type": record["asset_type"],
            "universe_mode": mode,
            "themes": list(dict.fromkeys(memberships.get(ticker, ()) or ())),
            **market,
            "rs60_raw": raw60.get(ticker),
            "rs60_percentile": rs60_pct,
            "rs60_rank": rank60.get(ticker),
            "rs120_rank": rank120.get(ticker),
            "rs_ranked_count": len(percent60),
            "rs60_valid": raw60.get(ticker) is not None and cross60_ok,
            "rs60_reason": (
                "OK" if raw60.get(ticker) is not None and cross60_ok
                else "RS_RANK_UNRELIABLE" if raw60.get(ticker) is not None
                else "INSUFFICIENT_HISTORY"
            ),
            "rs120_raw": raw120.get(ticker),
            "rs120_percentile": rs120_pct,
            "rs120_valid": raw120.get(ticker) is not None and cross120_ok,
            "rs120_reason": (
                "OK" if raw120.get(ticker) is not None and cross120_ok
                else "RS_RANK_UNRELIABLE" if raw120.get(ticker) is not None
                else "INSUFFICIENT_HISTORY"
            ),
            "rs_rank_status": "OK" if cross60_ok and cross120_ok else "RS_RANK_UNRELIABLE",
            "rs_core_status": _rs_core_status(rs60_pct, rs120_pct),
            "market_valid": bool(market.get("valid")),
            "market_reason": market.get("reason"),
            "breakout_data_valid": bool(breakout.get("valid")),
            "breakout_reason": breakout.get("reason") or "OK",
            "has_valid_52w_breakout": bool(breakout.get("valid") and breakout.get("has_breakout")),
            **{key: value for key, value in breakout.items() if key not in {"valid", "has_breakout"}},
            "pullback_status": pb_status,
            **theme,
            "rebound_status": rebound_status,
            "avg_dollar_volume_20": avg_dollar.get(ticker),
            "score_model_version": SCORE_MODEL_VERSION,
        }
        row["rs60_score"] = rs_points(rs60_pct, max_points=weights["rs60"], config=cfg)
        row["rs120_score"] = rs_points(rs120_pct, max_points=weights["rs120"], config=cfg)
        row["pullback_score"] = pullback_points(pb_pct, max_points=weights["pullback"], config=cfg)
        row["theme_score"] = (
            theme_points(row.get("theme_percentile"), max_points=weights["theme"], config=cfg)
            if row.get("theme_valid") else 0.0
        )
        row["breadth_score"] = (
            breadth_points(row.get("breadth_pct"), max_points=weights["breadth"], config=cfg)
            if row.get("breadth_valid") else 0.0
        )
        row["volume_score"] = (
            volume_points(row.get("breakout_rvol"), max_points=weights["volume"], config=cfg)
            if row.get("volume_valid") else 0.0
        )
        row["volume_reason"] = "OK" if row.get("volume_valid") else "VOLUME_DATA_INSUFFICIENT"
        row["rebound_score"] = rebound_points(
            rebound_status, max_points=weights["rebound"], config=cfg,
        )
        row["core_score"] = round(
            row["rs60_score"] + row["rs120_score"] + row["pullback_score"], 6
        )
        row["support_score"] = round(
            row["theme_score"] + row["volume_score"] + row["breadth_score"] + row["rebound_score"], 6
        )
        row["total_score"] = round(row["core_score"] + row["support_score"], 6)
        row["score"] = row["total_score"]
        row["core_data_valid"] = bool(
            market.get("valid")
            and row["rs60_valid"]
            and row["rs120_valid"]
            and breakout.get("valid")
        )
        status, eligible = _candidate_status(row, cfg)
        row["primary_status"] = status
        row["eligible_primary"] = eligible
        row["failed_gates"] = _failed_gates(row, cfg)
        row["grade"] = grade_for(row["total_score"], eligible, cfg)
        row["grade_text"] = GRADE_TEXT.get(row["grade"] or "")
        row["status_text"] = STATUS_TEXT.get(status, status)
        row["explanations"] = explanation_payload(row, cfg)
        titles = score_part_titles()
        row["score_parts"] = [
            (titles[0], row["rs60_score"], weights["rs60"], _display_value("rs60", row)),
            (titles[1], row["rs120_score"], weights["rs120"], _display_value("rs120", row)),
            (titles[2], row["pullback_score"], weights["pullback"], _display_value("pullback", row)),
            (titles[3], row["theme_score"], weights["theme"], _display_value("theme", row)),
            (titles[4], row["volume_score"], weights["volume"], _display_value("volume", row)),
            (titles[5], row["breadth_score"], weights["breadth"], _display_value("breadth", row)),
            (titles[6], row["rebound_score"], weights["rebound"], _display_value("rebound", row)),
        ]
        current = _finite(frame["Close"].iloc[-1]) if not frame.empty else None
        previous = _finite(frame["Close"].iloc[-2]) if len(frame) >= 2 else None
        row["metrics"] = {
            "ok": current is not None,
            "current": current,
            "prev_close": previous,
            "change_pct": ((current / previous - 1.0) * 100.0) if current and previous else None,
            "from_high_pct": -float(pb_pct) if pb_pct is not None else None,
            "high52": row.get("anchor_close"),
            "high52_days_ago": row.get("days_since_anchor"),
            "avg_dollar_volume": row.get("avg_dollar_volume_20"),
            "volume_ratio": row.get("breakout_rvol"),
            "ret60": (row.get("rs60_raw") or 0.0) * 100.0 if row.get("rs60_raw") is not None else None,
            "ret120": (row.get("rs120_raw") or 0.0) * 100.0 if row.get("rs120_raw") is not None else None,
            "day_open": _finite(frame["Open"].iloc[-1]) if not frame.empty and "Open" in frame else None,
            "day_high": _finite(frame["High"].iloc[-1]) if not frame.empty and "High" in frame else None,
            "day_low": _finite(frame["Low"].iloc[-1]) if not frame.empty and "Low" in frame else None,
            "day_close": current,
            "day_is_today": False,
        }
        row["pullback"] = {
            "score": row["pullback_score"],
            "high52_days_ago": row.get("days_since_anchor"),
            "from_high_pct": -float(pb_pct) if pb_pct is not None else None,
            "gap_pct": None,
            "parts": [row["pullback_score"]],
        }
        row["wait_days"] = row.get("days_since_anchor")
        rows.append(row)

    rows.sort(key=candidate_sort_key)
    for rank, row in enumerate(rows, 1):
        row["overall_rank"] = rank
    primary = [row for row in rows if row["eligible_primary"]]
    watch = [row for row in rows if not row["eligible_primary"]]
    for rank, row in enumerate(primary, 1):
        row["pullback_rank"] = rank
        row["primary_rank"] = rank
    return {
        "ok": True,
        "mode": "breakout",
        "date": target.date().isoformat(),
        "universe_mode": mode,
        "market": market,
        "rows": primary,
        "primary_rows": primary,
        "watch_rows": watch,
        "all_rows": rows,
        "primary_count": len(primary),
        "watch_count": len(watch),
        "universe_count": len(normalized_records),
        "data_count": sum(1 for frame in frames.values() if not frame.empty and frame.index[-1] == target),
        "rs_cross_section_60": len(percent60),
        "rs_cross_section_120": len(percent120),
        "score_weights": copy.deepcopy(weights),
        "score_model_version": SCORE_MODEL_VERSION,
        "config": copy.deepcopy(cfg),
        "explanation_catalog": copy.deepcopy(SCORE_EXPLANATIONS),
        "report": {
            "date": target.date().isoformat(),
            "market_status": market.get("market_status"),
            "primary_count": len(primary),
            "watch_count": len(watch),
            "score_model_version": SCORE_MODEL_VERSION,
        },
    }


def suppress_overlapping_signals(
    signals: Iterable[Mapping], *, holding_days: int = 252, mode: str = "NON_OVERLAP"
) -> list[dict]:
    """백테스트에서 같은 종목의 보유기간 중 반복 진입을 억제한다.

    거래일 정확도를 위해 입력의 ``signal_index``(종목별 거래일 번호)를 우선 사용한다.
    없으면 날짜의 평일 수를 사용한다.
    """

    ordered = sorted((dict(signal) for signal in signals), key=lambda row: (str(row.get("date")), str(row.get("ticker"))))
    if str(mode).upper() == "ALL_SIGNALS":
        return ordered
    kept = []
    last: dict[str, tuple[int | None, pd.Timestamp | None]] = {}
    for row in ordered:
        ticker = str(row.get("ticker") or "")
        position = int(row["signal_index"]) if row.get("signal_index") is not None else None
        stamp = _as_timestamp(row.get("date"))
        previous_position, previous_stamp = last.get(ticker, (None, None))
        if previous_position is not None and position is not None:
            overlap = position - previous_position < int(holding_days)
        elif previous_stamp is not None and stamp is not None:
            overlap = len(pd.bdate_range(previous_stamp, stamp)) - 1 < int(holding_days)
        else:
            overlap = False
        if overlap:
            continue
        kept.append(row)
        last[ticker] = (position, stamp)
    return kept


__all__ = [
    "AssetType",
    "DEFAULT_CONFIG",
    "GRADE_TEXT",
    "MODULE_REVISION",
    "SCORE_EXPLANATIONS",
    "SCORE_MODEL_VERSION",
    "STATUS_TEXT",
    "UniverseMode",
    "breadth_points",
    "candidate_sort_key",
    "explanation_payload",
    "grade_for",
    "latest_breakout",
    "market_gate",
    "merged_config",
    "percentile_ranks",
    "pullback_points",
    "pullback_state",
    "rebound_points",
    "relative_strength_raw",
    "rs_points",
    "scan_eod",
    "suppress_overlapping_signals",
    "theme_points",
    "validate_config",
    "volume_points",
]
