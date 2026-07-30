"""‘이 테마 기법에 대한 설명’ 단추와 그 내용.

자비스3(미국)·자비스4(한국)가 같이 쓴다. 한 곳만 고치면 두 화면이 함께 바뀐다.

여기 적힌 숫자는 지어낸 것이 아니라 2026-07-29에 실제로 잰 값이다.
2005-03 ~ 2026-06 지수 일봉(코스피 5,253일 · S&P500 5,357일)으로,
그날까지의 자료로만 신호를 만들고 20일 뒤 종가로 성적을 쟀다.
부트스트랩 1,500회로 우연인지도 확인했다. 숫자를 고칠 일이 생기면
반드시 다시 재고 나서 고친다.
"""

from __future__ import annotations

# 계산 결과나 문구를 바꾸면 이 숫자를 올리고, 페이지의 요구 리비전도 같이 올린다.
MODULE_REVISION = 2026073017

BUTTON_LABEL = "📘 이 테마 기법에 대한 설명"
CLOSE_HINT = "닫으려면 위 ‘📘 이 테마 기법에 대한 설명’ 단추를 다시 누르십시오."

# 단추는 눌림목 찾기 단추와 같은 옷을 입힌다(밝은 스카이 블루 바탕·주황 글씨).
# 다만 좌우로 늘리지 않고 글자 크기만큼만 차지하게 두고, 오른쪽 끝에 붙인다.
BUTTON_CSS = """
<style>
/* 오른쪽 끝으로 붙이기.
   스트림릿 컨테이너는 세로 방향 flex라 justify-content는 '세로'에 걸리고,
   align-items는 스트림릿이 start로 못박아 둬서 덮어써지지 않는다(2026-07-29 실측).
   그래서 자식에 margin-left:auto를 줘 밀어낸다 — 이건 정렬 규칙을 안 타고 확실히 먹는다. */
.st-key-jarvis_method_help { margin: .1rem 0 .35rem; }
.st-key-jarvis_method_help > div { margin-left: auto !important; width: auto !important; }
.st-key-jarvis_method_help [data-testid="stPopover"] { width: auto !important; }
div[class*="st-key-jarvis_method_help"] button {
    background: #cfe9ff !important;
    border: 1px solid #8ec9f5 !important;
    border-radius: .5rem !important;
    padding: .35rem .9rem !important;
    min-height: 0 !important;
    width: auto !important;
}
div[class*="st-key-jarvis_method_help"] button:hover {
    background: #b9dfff !important;
    border-color: #6db6ee !important;
}
div[class*="st-key-jarvis_method_help"] button p {
    color: #c15f3c !important;
    font-size: .95rem !important;
    font-weight: 800 !important;
    margin: 0 !important;
    white-space: nowrap !important;
}
/* 폰 전용 규칙은 여기 두지 않는다 — CLAUDE.md 12번 규칙에 따라 mobile_ui.py의
   폰 묶음 안에만 둔다. 밖으로 새면 태블릿·PC까지 바뀐다.
   (이 주석에 폰 미디어쿼리 문자열을 그대로 쓰면 '폰 규칙 묶음은 하나여야 한다'는
   테스트가 이 주석까지 세어 버린다 — 2026-07-29 실제로 걸렸다.) */

/* ── 화면 맨 위 빈 자리를 줄인다(2026-07-30 사용자 지시) ──────────────────
   제목을 뺐는데 그 자리가 그대로 비어 있었다. 실측(폰 412px) — 스트림릿 기본
   위 여백이 96px인데 도구막대(Stop·Fork·GitHub·⋮)는 60px밖에 안 된다.
   그래서 본문이 도구막대보다 한참 아래에서 시작했다.
   도구막대만 피하면 되므로 64px로 줄인다 — 도구막대는 그대로 눌러
   화면을 어둡게 바꿀 수 있어야 하므로 그 위로는 올리지 않는다.
   폰·태블릿·PC 모두 같은 문제라 폰 묶음이 아니라 여기 둔다(규칙 12는 폰 전용
   규칙에 대한 것이고, 이건 모든 화면에 걸리는 규칙이다). */
[data-testid="stMainBlockContainer"],
.block-container {
    padding-top: 4rem !important;
}

/* ── 설명 창은 본문을 따라 내려오지 않는다(2026-07-30 사용자 지시) ────────
   앞서 화면에 붙박아 뒀더니 굴릴 때마다 따라와 본문을 가려 불편하다고 했다.
   그래서 스트림릿 기본대로 단추 옆에 두고, 본문을 내리면 같이 위로 사라지게 둔다.
   내용을 두 쪽 분량으로 줄였으므로(아래 글) 단추가 화면에서 멀어질 일이 없다 —
   닫을 때는 같은 단추를 다시 누르면 된다.
   높이만 화면의 절반으로 묶어 둔다. 나머지 절반으로 실제 표를 봐야 하기 때문이다. */
[data-testid="stPopoverBody"] {
    width: min(680px, calc(100vw - 2rem)) !important;
    max-width: calc(100vw - 2rem) !important;
    max-height: 50vh !important;
    overflow-y: auto !important;
    box-shadow: 0 10px 40px rgba(0, 0, 0, .55) !important;
}

/* ── 글 색 구분(2026-07-30 사용자 지시) ──────────────────────────────
   큰 제목은 초록, 번호 항목(①②③)은 파랑, 강조는 붉은색.
   번호 항목만 파랑으로 뽑으려고 단계 제목은 h5(#####)로, 나머지 제목은
   h3(###)으로 통일했다. 이 규칙이 깨지면 색이 엉킨다.
   앱에 테마 설정 파일이 없어 화면이 보는 사람의 밝기 설정을 따라간다.
   그래서 밝은 화면·어두운 화면 두 벌을 다 둔다. */
[data-testid="stPopoverBody"] {
    --j-title: #0f7a3d;
    --j-step: #0b5ed7;
    --j-mark: #c62828;
}
@media (prefers-color-scheme: dark) {
    [data-testid="stPopoverBody"] {
        --j-title: #44f0a1;
        --j-step: #4da6ff;
        --j-mark: #ff6b6b;
    }
}
[data-testid="stPopoverBody"] h3 { color: var(--j-title) !important; }
[data-testid="stPopoverBody"] h5 { color: var(--j-step) !important; font-size: 1.02rem !important; }
/* 붉은색은 '문단과 인용문의 굵은 글씨'에만 준다.
   표와 목록의 굵은 글씨까지 붉히면 화면이 온통 붉어져 강조가 강조가 아니게 된다
   (2026-07-30 사용자 지적: "붉은색이 너무 많다"). */
[data-testid="stPopoverBody"] p > strong,
[data-testid="stPopoverBody"] blockquote strong { color: var(--j-mark) !important; }
[data-testid="stPopoverBody"] td strong,
[data-testid="stPopoverBody"] th strong,
[data-testid="stPopoverBody"] li strong { color: inherit !important; }
</style>
"""

_COMMON_TAIL = """
---

### 지금 할 일 — 테두리 색이 곧 답

'매수 심사 결과' 칸 맨 위 상자를 보십시오. 화면이 내린 판정을 그대로 옮긴 것입니다.

| | 뜨는 말 | 할 일 |
|---|---|---|
| 🟩 | 이 기법이 말하는 진입 자리입니다 | 기준가를 넘으면 사고, 허용 상단까지만. 무효화 가격이 깨지면 판단이 틀린 것 |
| 🟨 | 오늘은 새로 사지 않습니다 | 시장 점수가 문턱에 못 미치는 날 |
| 🟨 | 가격 자리는 맞지만 아직 아닙니다 | 뭐가 모자란지 상자에 적혀 있음 |
| 🟨 | 사지 않고 지켜봅니다 | 아직 자리가 아님 |
| 🟥 | 손대지 않습니다 · 후보에서 뺍니다 | 추격 자리. **점수가 높아도 예외 없음** |

---

### 점수를 잘못 읽는 흔한 경우

| | |
|---|---|
| 90점 = "이 종목은 오른다" | ❌ **틀린 말** |
| 90점 = "지금 조건 여러 개에 걸려 있다" | ✅ 맞는 말 |
| 30점 = "이걸 사면 덜 번다" | ❌ **틀린 말** |
| 30점 = "이걸 사면 크게 깨질 수 있다" | ✅ 맞는 말 |

점수는 앞일을 맞히는 숫자가 아니라 **조건을 몇 개나 만족했는지 센 숫자**입니다.
값(현재가·거래대금·수급)은 원자료 그대로이고, 못 가져온 값은 **지어내지 않습니다**.

---

### 어디서 왔나 · 언제 파나

**한 편의 논문에서 나온 기법이 아닙니다.** 논문 세 갈래(Moskowitz & Grinblatt 1999 —
분야 모멘텀 / George & Hwang 2004 — 52주 신고가 / Moskowitz·Ooi·Pedersen 2012 — 추세)와
실무 세 갈래(Weinstein · O'Neil · Minervini)가 겹치는 자리입니다.

**파는 때는 아직 이 화면에 없습니다.** 살 때 찍는 '무효화 가격'과 '2R 목표'가 전부이고,
들고 있는 동안 알려주는 장치가 없습니다. 이 화면의 가장 큰 구멍입니다.
연구가 말하는 매도 규칙(−10% 손절, −7~8% 손절, +20~25% 부분 익절, 이동평균 이탈)은
**남의 자료로 잰 값**이라, 우리 자료로 재보기 전에는 점수에 넣지 않습니다.

*자세한 근거와 조사 원본: `docs/METHOD_ORIGINS.md`*
"""

US_TEXT = """
### 한눈에 — 이게 무슨 기법인가

| | |
|---|---|
| **무슨 기법** | 돈이 몰리는 **분야(테마)를** 먼저 고르고, 그 안에서 **제일 앞서 가는 종목**을 사는 방식 |
| **얼마나 검토** | S&P500 **21년치 5,357거래일**(2005-03 ~ 2026-06). 앞을 훔쳐보지 않고 20일 뒤 종가로 채점 |
| **언제 사나** | 시장 **50점**↑ · 분야 **70점**↑ · 종목 **75점**↑ 를 다 넘고, 상태가 **'돌파 확인'** 또는 **'눌림목 대기'일** 때 |
| **어디에 적나** | 실제로 샀을 때만 **'실제 매수 기록'에** 저장. 그때 조건이 함께 남아 나중에 검증합니다 |
| **언제 파나** | **아직 없습니다.** 아래를 보십시오 |

> **"이걸 사라"고 찍어 주는 화면이 아닙니다.
> "지금 사면 얼마나 위험한가"를 재 주는 화면입니다.**

**이 기법의 값어치는 '더 버는 것'이 아니라 '크게 깨지지 않는 것'입니다.**
미국에서는 잘 듣습니다 — 50일선 위에서는 20일 안에 10% 넘게 깨질 확률이
**3.5% → 1.1%로** 줄었습니다. 다만 더 벌지는 않았습니다(+0.65% vs +1.12%).
""" + _COMMON_TAIL

KR_TEXT = """
### 한눈에 — 이게 무슨 기법인가

| | |
|---|---|
| **무슨 기법** | 돈이 몰리는 **분야(테마)를** 먼저 고르고, 그 안에서 **제일 앞서 가는 종목**을 사는 방식 |
| **얼마나 검토** | 코스피 **21년치 5,253거래일**(2005-03 ~ 2026-06). 앞을 훔쳐보지 않고 20일 뒤 종가로 채점 |
| **언제 사나** | 시장 **50점**↑ · 분야 **60점**↑(종목 85점↑면 면제) · 종목 **70점**↑ 를 다 넘고, 상태가 **'돌파 확인'** 또는 **'눌림목 대기'일** 때 |
| **어디에 적나** | 실제로 샀을 때만 **'실제 매수 기록'에** 저장. 그때 조건이 함께 남아 나중에 검증합니다 |
| **언제 파나** | **아직 없습니다.** 아래를 보십시오 |

> **"이걸 사라"고 찍어 주는 화면이 아닙니다.
> "지금 사면 얼마나 위험한가"를 재 주는 화면입니다.**

**한국은 미국과 결론이 다릅니다 — 이것이 이 화면의 핵심입니다.**
코스피 21년치로 재보니 **시장 점수가 미국만큼 듣지 않았습니다.**
50일선 위든 아래든 10% 넘게 깨질 확률이 **2.9% vs 3.6%로** 거의 같았습니다
(미국은 1.1% vs 3.5%로 3배 차이).

**그래서 이렇게 보강했습니다** — **외국인·기관 수급**을 종목 점수 100점 중 **20점**으로
넣었습니다(미국 화면에는 없는 자료). 분야 문턱은 60점으로 낮추고 종목이 85점을 넘으면
분야를 안 봅니다. 추격 금지도 국내용으로 따로 뒀습니다(하루 30%까지 오르는 시장이라).

→ **시장 점수는 참고로만, 수급과 종목 점수를 무겁게.**
""" + _COMMON_TAIL


def render(st, market: str) -> None:
    """최상단 오른쪽에 설명 단추를 놓는다. market은 'US' 또는 'KR'."""
    st.markdown(BUTTON_CSS, unsafe_allow_html=True)
    box = st.container(key="jarvis_method_help")
    with box:
        with st.popover(BUTTON_LABEL):
            # 창 안에 닫기 단추를 두는 방법은 안 통한다 — 눌러도 팝오버가 열린 채
            # 남는다(2026-07-30 실측). 여는 단추를 다시 누르는 것이 닫는 길이라
            # 그 방법을 맨 위에 적어 준다.
            st.caption(CLOSE_HINT)
            st.markdown(US_TEXT if str(market).upper() == "US" else KR_TEXT)
