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

TIMING_LABEL = {
    SignalTiming.LEADING: "선행",
    SignalTiming.CONFIRMING: "확인",
    SignalTiming.LATE: "늦음",
    SignalTiming.FAKE: "가짜",
    SignalTiming.UNKNOWN: "확인 필요",
}

# 이 칸은 '이 숫자를 얼마나 믿을 수 있나'를 말한다.
# 예전 이름은 직접·대체·간접이었는데 "대체가 뭘 대체한다는 건지 모르겠다"는
# 지적을 받아 뜻이 그대로 읽히는 말로 바꿨다(2026-07-29 사용자 지시).
# 무엇을 무엇으로 대신했는지는 각 줄의 '설명' 칸에 적는다.
STRENGTH_LABEL = {
    SignalStrength.DIRECT: "그대로",
    SignalStrength.PROXY: "대신",
    SignalStrength.INDIRECT: "참고",
}

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
    counted = counted_signals(signals)
    known = [s for s in counted if not s.is_unknown]
    unknown = [s for s in counted if s.is_unknown]
    return f"자동 확인 {len(known)}개 · 확인 필요 {len(unknown)}개"


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
        return "늦은 신호만 켜져 있습니다 — 이미 지나간 흐름일 수 있습니다."
    if leading_on and confirming_on:
        return f"선행 {len(leading_on)}개가 켜졌고 확인 신호 {len(confirming_on)}개가 뒤따르고 있습니다."
    if leading_on and not confirming_on:
        return f"선행 신호 {len(leading_on)}개만 켜졌고 확인 신호는 아직 없습니다."
    if confirming_on and not leading_on:
        return "선행 신호 없이 확인 신호만 켜졌습니다 — 뒤늦은 반응일 수 있습니다."
    return "선행·확인 신호 모두 아직 켜지지 않았습니다."


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
