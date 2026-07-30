"""'그래서 지금 뭘 하라는 건가' 한 줄. 자비스3(미국)·자비스4(한국)가 같이 쓴다.

2026-07-30 사용자 지적 — 점수와 상태는 있는데 **지침이 없어서 뭘 하라는 건지
알 수 없다.** 여기서 만드는 문장은 이미 정해진 판정(`_entry_plan`)을 사람 말로
다시 쓴 것이고, **새 판정을 만들지 않는다.** 값도 전부 그 판정이 정한 것만 쓴다.
그래서 화면의 점수·상태와 지침이 어긋날 수 없다.

돈 단위가 나라마다 다르므로 숫자를 글자로 바꾸는 일은 부르는 쪽이 넘겨 준다
(`money=_won` 또는 `money=_price`).
"""

from __future__ import annotations

# 계산 결과나 문구를 바꾸면 이 숫자를 올리고, 페이지의 요구 리비전도 같이 올린다.
MODULE_REVISION = 2026073010

GO, WAIT, STOP = "go", "wait", "stop"

# 등급별 색 — 매수 심사 결과 칸 위에 얹는 지침 상자에 쓴다.
LEVEL_STYLE = {
    GO: ("#1f7a4d", "#44f0a1"),
    WAIT: ("#7a6a1f", "#ffd166"),
    STOP: ("#7a2626", "#ff6b6b"),
}

MARKET_GATE = 50.0


def build(plan: dict | None, *, money, market_score=None) -> dict:
    """지침 한 벌 — {'level', 'headline', 'detail'}.

    headline은 '지금 무엇을 하라'는 한 마디, detail은 '왜'와 숫자다.
    """
    plan = plan or {}
    state = str(plan.get("state") or "")
    recommendation = str(plan.get("recommendation") or "")
    reason = str(plan.get("buy_reason") or "").strip()

    if state in ("", "자료 부족"):
        return {
            "level": WAIT,
            "headline": "판단할 자료가 모자랍니다",
            "detail": "시세나 이력을 다 못 받아 왔습니다. 이 종목은 이 화면으로 판단하지 마십시오.",
        }

    if state == "추격 금지":
        return {
            "level": STOP,
            "headline": "손대지 않습니다",
            "detail": reason or "이미 급하게 올라 추격 자리입니다. 점수가 높아도 예외가 없습니다.",
        }

    if state == "제외":
        return {
            "level": STOP,
            "headline": "후보에서 뺍니다",
            "detail": reason or "가격 자리도 아니고 종목 점수도 문턱에 못 미칩니다.",
        }

    if recommendation == "조건부 후보":
        steps = []
        if plan.get("trigger") is not None:
            steps.append(f"<b>{money(plan['trigger'])}를 넘으면</b> 진입")
        if plan.get("zone_high") is not None:
            steps.append(f"<b>{money(plan['zone_high'])}까지만</b> — 더 비싸면 사지 않음")
        if plan.get("invalidation") is not None:
            steps.append(f"<b>{money(plan['invalidation'])}가 깨지면</b> 판단이 틀린 것")
        if plan.get("target") is not None:
            steps.append(f"참고 목표 <b>{money(plan['target'])}</b>")
        return {
            "level": GO,
            "headline": f"이 기법이 말하는 진입 자리입니다 ({state})",
            "detail": " · ".join(steps) if steps else reason,
        }

    # 여기부터는 '아직 아니다'. 왜 아닌지를 숫자로 짚어 준다.
    try:
        score_value = float(market_score) if market_score is not None else None
    except (TypeError, ValueError):
        score_value = None

    if score_value is not None and score_value < MARKET_GATE:
        return {
            "level": WAIT,
            "headline": "오늘은 새로 사지 않습니다",
            "detail": (
                f"시장 점수 <b>{score_value:.0f}점</b> — 문턱 {MARKET_GATE:.0f}점에 못 미칩니다. "
                "종목이 좋아도 이 기법은 이런 날 새로 들어가지 않습니다."
            ),
        }

    if state in ("돌파 확인", "눌림목 대기"):
        return {
            "level": WAIT,
            "headline": "가격 자리는 맞지만 아직 아닙니다",
            "detail": reason or "시장이나 분야 점수가 문턱에 못 미칩니다.",
        }

    return {
        "level": WAIT,
        "headline": "사지 않고 지켜봅니다",
        "detail": reason or "아직 가격 자리가 만들어지지 않았습니다.",
    }


def html(guide: dict, *, css_class: str) -> str:
    """지침 상자 한 덩이. css_class는 페이지마다 다른 접두사(j3-/j4-)를 받는다."""
    border, text = LEVEL_STYLE.get(guide.get("level", WAIT), LEVEL_STYLE[WAIT])
    headline = guide.get("headline", "")
    detail = guide.get("detail", "")
    return (
        f"<div class='{css_class}' style='border-color:{border}'>"
        f"<span class='{css_class}-tag' style='color:{text}'>지금 할 일</span>"
        f"<span class='{css_class}-head' style='color:{text}'>{headline}</span>"
        f"<div class='{css_class}-body'>{detail}</div></div>"
    )
