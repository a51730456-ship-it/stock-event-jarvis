"""한국장·미국장 시장 신호의 공통 계층.

공통화하는 것은 딱 네 가지다.
- 신호 상태값 (긍정/중립/부정/확인 필요)
- 신호 시점 (선행/확인/늦음/가짜)
- 신호 세기 (직접/대체/간접)
- 데이터 신선도와 출처 보관

공통화하지 않는 것:
- 판정 기준, 임계치, 결론 문구, 최종 판정명.
  한국장은 기관 수급 중심이고 미국장은 선물·ETF·금리·변동성 중심이라 성격이 다르다.
  두 시장 조건을 한 함수 안에서 if로 처리하지 않는다.

이 모듈은 네트워크도 Streamlit도 쓰지 않는다.

주의: 이 카드들은 종목을 고르라는 물건이 아니다. 지금 시장이 어떤 상태이고
무엇이 앞서 움직이는지를 읽어서, 사용자가 스스로 판단할 재료를 주는 것이 목적이다.
그래서 결론 문구에 매수·매도 지시를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketCode(str, Enum):
    KR = "KR"
    US = "US"


class SignalStatus(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class SignalTiming(str, Enum):
    LEADING = "leading"
    CONFIRMING = "confirming"
    LATE = "late"
    FAKE = "fake"
    UNKNOWN = "unknown"


class SignalStrength(str, Enum):
    DIRECT = "direct"
    PROXY = "proxy"
    INDIRECT = "indirect"


STATUS_COLOR = {
    SignalStatus.POSITIVE: "#22c55e",
    SignalStatus.NEUTRAL: "#eab308",
    SignalStatus.NEGATIVE: "#ef4444",
    SignalStatus.UNKNOWN: "#9ca3af",
}

STATUS_MARK = {
    SignalStatus.POSITIVE: "⭕",
    SignalStatus.NEUTRAL: "🟡",
    SignalStatus.NEGATIVE: "❌",
    SignalStatus.UNKNOWN: "⚪",
}

# 이 칸은 '본장보다 먼저 움직이는 지표냐, 결과로 따라오는 지표냐'를 말한다.
# 선행·확인이라는 말을 일반인이 알아듣지 못한다는 지적을 받아 풀어 썼다
# (2026-07-29 사용자 지시: "저런 말은 일반인인 내가 알아 먹겠냐").
TIMING_LABEL = {
    SignalTiming.LEADING: "먼저 움직임",
    SignalTiming.CONFIRMING: "뒤따라옴",
    SignalTiming.LATE: "이미 늦음",
    SignalTiming.FAKE: "가짜",
    SignalTiming.UNKNOWN: "모름",
}

# 직접/대체 → 그대로/대신 → 원본/대신 씀 순으로 두 번 고쳤는데 전부 "그게 무슨
# 말이냐"는 답을 받았다(2026-07-29). 뜻을 설명해야 알 수 있는 말은 화면에 쓰지
# 않는다. 이 칸에는 값을 어디서 가져왔는지 **기관 이름을 그대로** 적는다.
STRENGTH_LABEL = {
    SignalStrength.DIRECT: "원본",
    SignalStrength.PROXY: "대신 씀",
    SignalStrength.INDIRECT: "참고",
}

# 화면에 실제로 나가는 것은 이쪽이다. source 문자열에서 기관 이름만 뽑는다.
_SOURCE_WORDS = (
    ("네이버", "네이버"),
    ("HTS", "HTS 입력"),
    ("KIS", "증권사"),
    ("가격 스냅샷", "네이버 시세"),
    ("시세 조회", "시세"),
    ("^VIX", "시세"),
    ("시장 이벤트", "뉴스"),
    ("미연결", "없음"),
)


def source_word(signal) -> str:
    """이 값을 어디서 가져왔는지 한 마디로. 설명이 필요한 말은 쓰지 않는다."""
    text = str(getattr(signal, "source", "") or "")
    for needle, word in _SOURCE_WORDS:
        if needle in text:
            return word
    return text.strip() or "없음"

# 데이터 신선도(초)
FRESHNESS_OK_SECONDS = 120
FRESHNESS_DELAYED_SECONDS = 300


@dataclass
class MarketSignal:
    """시장 신호 하나. 첫 세 인자 순서(key, label, status)는 바꾸지 않는다."""

    key: str
    label: str
    status: SignalStatus
    value: float | int | str | None = None
    display_value: str = "-"
    reason: str = ""
    source: str = "-"
    as_of: datetime | None = None
    freshness_seconds: int | None = None
    strength: SignalStrength = SignalStrength.DIRECT
    timing: SignalTiming = SignalTiming.UNKNOWN
    market: MarketCode | None = None
    # 개수 세기('켜진 신호 N개')에 넣을 신호인지. 기본은 넣는다.
    # False로 두는 것은 두 종류다 (2026-07-29 사용자 지시, 5번 '가'안):
    #  1) 상위 항목의 하위 내역 — 금융투자·투신·사모·기금은 전부 기관계의 부분이다.
    #     넷을 따로 세면 기관 순매수 한 건이 네 번 켜진 것처럼 보인다.
    #  2) 반대 주체 — 개인은 기관·외국인의 거울상이라 같은 눈금으로 세면 안 된다.
    # 표에는 그대로 보여준다. 세지 않을 뿐 숨기지 않는다.
    counts_toward_totals: bool = True

    @property
    def is_positive(self) -> bool:
        return self.status is SignalStatus.POSITIVE

    @property
    def is_negative(self) -> bool:
        return self.status is SignalStatus.NEGATIVE

    @property
    def is_unknown(self) -> bool:
        return self.status is SignalStatus.UNKNOWN

    @property
    def is_direct(self) -> bool:
        return self.strength is SignalStrength.DIRECT


@dataclass
class MarketSignalResult:
    """시장별 판정 결과. verdict 값 자체는 시장별 엔진이 정의한다."""

    market: MarketCode
    verdict: str
    verdict_label: str
    headline: str
    signals: list
    positive_reasons: list
    missing_reasons: list
    warning_reasons: list
    data_status: str = ""
    as_of: datetime | None = None

    def signal(self, key: str):
        return next((s for s in self.signals if s.key == key), None)

    def by_timing(self, timing: SignalTiming):
        return [s for s in self.signals if s.timing is timing]


def freshness_text(freshness_seconds: int | None) -> str:
    """자료가 몇 분 된 것인지 그대로 적는다.

    예전에는 정상·지연·오래됨이라는 등급을 만들어 붙였는데, 등급 이름만 봐서는
    무슨 뜻인지 알 수 없다는 지적을 받았다(2026-07-29). 몇 분 전인지 적으면
    설명이 필요 없다. 색은 그대로 freshness_label 기준으로 칠한다.
    """
    if freshness_seconds is None:
        return "모름"
    if freshness_seconds < 60:
        return "방금"
    minutes = int(freshness_seconds // 60)
    if minutes < 60:
        return f"{minutes}분 전"
    return f"{minutes // 60}시간 전"


def freshness_label(freshness_seconds: int | None) -> str:
    if freshness_seconds is None:
        return "확인 필요"
    if freshness_seconds <= FRESHNESS_OK_SECONDS:
        return "정상"
    if freshness_seconds <= FRESHNESS_DELAYED_SECONDS:
        return "지연"
    return "오래됨"


def is_stale(signal) -> bool:
    return (
        signal.freshness_seconds is not None
        and signal.freshness_seconds > FRESHNESS_DELAYED_SECONDS
    )


def counted_signals(signals):
    """개수 표시에 넣을 신호만 고른다. 하위 내역·반대 주체는 빠진다."""
    return [s for s in (signals or []) if getattr(s, "counts_toward_totals", True)]


def data_status_text(signals) -> str:
    # '자동 확인 / 확인 필요'는 무엇이 확인됐다는 건지 알 수 없다는 지적을 받아
    # 읽었나 못 읽었나로 바꿨다(2026-07-29).
    counted = counted_signals(signals)
    known = [s for s in counted if not s.is_unknown]
    unknown = [s for s in counted if s.is_unknown]
    return f"읽은 항목 {len(known)}개 · 못 읽은 항목 {len(unknown)}개"


def flow_reading(signals) -> str:
    """무엇이 앞서고 무엇이 뒤따르는지 한 줄로 요약한다.

    이게 이 카드의 핵심이다. 판정 하나보다 '지금 선행신호가 켜졌는데 확인신호가
    아직 없다'는 서술이 사용자가 다른 자비스와 대조할 때 훨씬 쓸모 있다.

    개수는 counted_signals 기준이다. 기관계를 쪼갠 하위 항목까지 세면 '확인 신호
    3개'처럼 부풀려진다 — 실은 기관 순매수 한 건이다(2026-07-29 사용자 지적).
    """
    signals = counted_signals(signals)
    leading_on = [s for s in signals if s.timing is SignalTiming.LEADING and s.is_positive]
    confirming_on = [s for s in signals if s.timing is SignalTiming.CONFIRMING and s.is_positive]
    late_on = [s for s in signals if s.timing is SignalTiming.LATE]

    if late_on and not leading_on:
        return "이미 지나간 신호만 켜져 있습니다 — 늦었을 수 있습니다."
    if leading_on and confirming_on:
        return (f"먼저 움직이는 신호 {len(leading_on)}개가 켜졌고, "
                f"뒤따라오는 신호 {len(confirming_on)}개가 따라붙었습니다.")
    if leading_on and not confirming_on:
        return (f"먼저 움직이는 신호 {len(leading_on)}개만 켜졌고, "
                "뒤따라오는 신호는 아직 없습니다.")
    if confirming_on and not leading_on:
        return ("먼저 움직이는 신호 없이 뒤따라오는 신호만 켜졌습니다 — "
                "뒤늦은 반응일 수 있습니다.")
    return "먼저 움직이는 신호도, 뒤따라오는 신호도 아직 없습니다."


def pct_status(change_pct, *, positive_at=0.3, inverted=False):
    """등락률 기준 공통 3분류. inverted면 상승이 부정(VIX·금리·달러).

    임계치는 기존 0단계 시장 분위기 판정(±0.3%)과 맞춘다.
    """
    if change_pct is None:
        return SignalStatus.UNKNOWN
    try:
        value = float(change_pct)
    except (TypeError, ValueError):
        return SignalStatus.UNKNOWN
    if value != value:
        return SignalStatus.UNKNOWN
    if inverted:
        value = -value
    if value >= positive_at:
        return SignalStatus.POSITIVE
    if value <= -positive_at:
        return SignalStatus.NEGATIVE
    return SignalStatus.NEUTRAL


def fmt_signed_pct(value) -> str:
    if value is None:
        return "확인 필요"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "확인 필요"
