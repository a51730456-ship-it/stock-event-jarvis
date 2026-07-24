"""자비스 주식 기록장 (Streamlit 앱): 오늘 요약 / 새 기록 입력 / 오늘 주가 확인 / 지난 기록 보기 / 결과 확인 / 추가 기능."""

import base64
import math
import functools
import html
import logging
import re
import sqlite3
from urllib.parse import urlparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

# 로그인 화면 지구(WebGL). streamlit 외에 무거운 것을 끌어오지 않으므로
# 인증 게이트 앞에서 불러도 첫 화면이 늦어지지 않는다.
import login_globe

_reference_panel_logger = logging.getLogger("jarvis.reference_panels")


def _reference_panel_guard(panel_name, required_callables, failure_message):
    """Keep optional reference-panel failures from interrupting the rest of the app."""
    def decorator(func):
        @functools.wraps(func)
        def guarded(*args, **kwargs):
            missing = [
                f"{module_name}.{function_name}"
                for module_name, function_name in required_callables
                if not callable(getattr(globals().get(module_name), function_name, None))
            ]
            if missing:
                _reference_panel_logger.error(
                    "reference panel unavailable panel=%s missing=%s",
                    panel_name,
                    ",".join(missing),
                )
                st.warning(
                    "코드가 변경됐지만 실행 중인 앱에 반영되지 않았습니다. "
                    "Streamlit을 완전히 종료한 뒤 다시 실행하세요."
                )
                return None
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                _reference_panel_logger.exception(
                    "reference panel failed panel=%s error_type=%s",
                    panel_name,
                    type(exc).__name__,
                )
                st.warning(failure_message)
                return None

        return guarded
    return decorator

_SECTION_HEADER_RE = re.compile(r"^\[(.+?)\]\s*$")

# 간편 입력에서 자주 쓰는 표현을 판정 5종 내부값으로 정규화한다.
# 내부값/DB 저장값은 그대로 두고, 화면 표시는 아래쪽에 정의된 _display_verdict_name()으로 보여준다.
VERDICT_NORMALIZE = {
    "보류": "보류(선반영)",
    "보류(선반영)": "보류(선반영)",
    "관심 후보": "추천 후보",
    "관심종목": "추천 후보",
    "관심 종목": "추천 후보",
    "추천 후보": "추천 후보",
    "감시": "감시",
    "확인 필요": "확인 필요",
    "제외": "제외",
}


def _parse_optional_score(text):
    """빈 문자열이면 None, 숫자면 float로 변환, 숫자로 해석 안 되면 None을 반환한다."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_quick_text(text):
    """"간편 저장용 텍스트"([기본]/[오늘의 결론]/[종목] 구역)를 파싱한다.

    구분자는 '/'. 각 종목 줄은 세 형식을 지원한다.
    - 6개 필드(기존 형식): 종목명 / 티커 / market / 판정 / 신호 분류 / 이벤트명
      (trade_mode는 자동으로 '공통')
    - 7개 필드(신규 형식): 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명
    - 13개 필드(확장 형식, 판단 설명 포함): 위 7개 필드 +
      score / score_reason / top_candidate_reason / penalty_reason / buy_confirmed / buy_confirm_condition
    선택지에 없는 값은 안전한 기본값으로 대체하고 warnings에 기록한다.
    "시점 구분"은 timing_class가 저장 시각 기준 자동 분류라는 기존 규칙 때문에 파싱만 하고
    적용하지 않는다(경고만 남김).
    """
    warnings = []
    sections = {}
    current = None
    buffer = []
    for line in text.splitlines():
        m = _SECTION_HEADER_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = m.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()

    result = {
        "market_scope": None,
        "briefing_stage": None,
        "default_signal_type": None,
        "day_conclusion": sections.get("오늘의 결론", "").strip(),
        "items": [],
        "warnings": warnings,
    }

    for line in sections.get("기본", "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "시장 범위":
            if value in db.MARKET_SCOPE_CHOICES:
                result["market_scope"] = value
            else:
                warnings.append(f"시장 범위 '{value}'를 인식하지 못했습니다 (KR/US/MIXED 중 하나여야 함).")
        elif key == "브리핑 단계":
            if value in db.BRIEFING_STAGE_CHOICES:
                result["briefing_stage"] = value
            else:
                warnings.append(f"브리핑 단계 '{value}'가 선택지에 없어 '기타'로 대체됩니다.")
                result["briefing_stage"] = "기타"
        elif key == "신호 분류":
            if value in db.SIGNAL_TYPE_CHOICES:
                result["default_signal_type"] = value
            else:
                warnings.append(f"기본 신호 분류 '{value}'를 인식하지 못했습니다.")
        elif key == "시점 구분":
            warnings.append("시점 구분은 저장 시각 기준으로 자동 분류되어 이 값은 사용되지 않습니다.")

    for line in sections.get("종목", "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 4:
            warnings.append(f"종목 줄을 해석하지 못했습니다(구분자 '/' 필드 부족): {line}")
            continue

        stock_name, ticker, market = parts[0], parts[1], parts[2]

        if len(parts) >= 13:
            # 확장 형식: 7개 기존 필드 + 6개 판단 설명 필드
            # 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명 /
            # score / score_reason / top_candidate_reason / penalty_reason / buy_confirmed / buy_confirm_condition
            trade_mode = parts[3]
            verdict = parts[4]
            signal_type = parts[5] if parts[5] else (result["default_signal_type"] or "")
            event_title = parts[6]
            score = _parse_optional_score(parts[7])
            score_reason = parts[8] or None
            top_candidate_reason = parts[9] or None
            penalty_reason = parts[10] or None
            buy_confirmed = parts[11] if parts[11] else "미확정"
            buy_confirm_condition = parts[12] if parts[12] else "확인 필요"
        elif len(parts) == 7:
            # 신규 형식(판단 설명 없음): 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명
            trade_mode = parts[3]
            verdict = parts[4]
            signal_type = parts[5] if parts[5] else (result["default_signal_type"] or "")
            event_title = parts[6]
            score = None
            score_reason = None
            top_candidate_reason = None
            penalty_reason = None
            buy_confirmed = "미확정"
            buy_confirm_condition = "확인 필요"
        elif 8 <= len(parts) <= 12:
            # 6/7/13개 필드 형식 중 어디에도 안 맞는 애매한 개수(필드 하나 누락/추가 등).
            # 예전엔 이 구간이 "6개 이하" 분기로 조용히 흘러들어가 verdict/신호분류/이벤트명
            # 자리가 밀려서 저장됐다(2026-07-13 전체 코드검사에서 발견) — 대신 명확히
            # 건너뛰고 경고한다.
            warnings.append(
                f"종목 줄 필드 개수({len(parts)}개)가 지원 형식(6개 이하/7개/13개)과 "
                f"맞지 않아 건너뜁니다: {line}"
            )
            continue
        else:
            # 기존 형식(6개 이하): 종목명 / 티커 / market / 판정 / 신호 분류 / 이벤트명
            trade_mode = "공통"
            verdict = parts[3]
            signal_type = parts[4] if len(parts) > 4 and parts[4] else (result["default_signal_type"] or "")
            event_title = parts[5] if len(parts) > 5 else ""
            score = None
            score_reason = None
            top_candidate_reason = None
            penalty_reason = None
            buy_confirmed = "미확정"
            buy_confirm_condition = "확인 필요"

        if market not in db.ITEM_MARKET_CHOICES:
            warnings.append(f"'{stock_name}' market 값 '{market}'을 인식 못해 'KR'로 대체합니다.")
            market = "KR"
        if trade_mode not in db.TRADE_MODE_CHOICES:
            warnings.append(f"'{stock_name}' 매매유형 값 '{trade_mode}'을 인식 못해 '공통'으로 대체합니다.")
            trade_mode = "공통"
        verdict = VERDICT_NORMALIZE.get(verdict, verdict)
        if verdict not in db.VERDICT_CHOICES:
            warnings.append(f"'{stock_name}' 판정 값 '{verdict}'을 인식 못해 '확인 필요'로 대체합니다.")
            verdict = "확인 필요"
        if signal_type not in db.SIGNAL_TYPE_CHOICES:
            warnings.append(f"'{stock_name}' 신호 분류 값 '{signal_type}'을 인식 못해 '미분류'로 대체합니다.")
            signal_type = "미분류"

        result["items"].append(
            {
                "stock_name": stock_name,
                "ticker": ticker,
                "market": market,
                "trade_mode": trade_mode,
                "verdict": verdict,
                "signal_type": signal_type,
                "event_title": event_title,
                "score": score,
                "score_reason": score_reason,
                "top_candidate_reason": top_candidate_reason,
                "penalty_reason": penalty_reason,
                "buy_confirmed": buy_confirmed,
                "buy_confirm_condition": buy_confirm_condition,
            }
        )

    return result


def create_daily_db_backup_once():
    """하루 1회, db/jarvis.sqlite3를 backups/jarvis_YYYYMMDD.sqlite3로 백업한다.

    sqlite3 내장 backup API를 사용한다(단순 파일 복사가 아님 — 연결이 열려 있는 상태에서도
    안전하게 백업할 수 있다). 같은 날짜 백업이 이미 있으면 건너뛰고 덮어쓰지 않는다.
    백업 실패는 앱을 죽이지 않고 경고만 표시한다. 원본 DB는 읽기만 하며 절대 수정하지 않는다.
    """
    try:
        # Streamlit Cloud에서는 운영 원본이 Turso에 있고 로컬 파일은 임시이므로,
        # 기존 SQLite 파일 백업을 시도하지 않는다. Turso의 서버 측 복구를 사용한다.
        if db.is_remote_database():
            return
        db_path = db.DB_PATH
        if not db_path.exists():
            return
        backups_dir = db_path.parent.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backups_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.sqlite3"
        if backup_path.exists():
            return
        source_conn = sqlite3.connect(db_path)
        try:
            dest_conn = sqlite3.connect(backup_path)
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            source_conn.close()
    except Exception as e:
        st.warning(f"일일 DB 백업을 만들지 못했습니다(앱은 정상 동작합니다): {e}")


st.set_page_config(page_title="자비스 주식 기록장", layout="wide")

# 사이드바 페이지 목록(app/자비스2/자비스3) 글자를 키우고 색을 넣어 눈에 띄게 한다.
st.markdown(
    """
    <style>
    /* 왼쪽 메뉴는 좁게, 오른쪽 본문은 넓게 (2026-07-24 사용자 지시). j-narrow-sidebar */
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"] {
        width: 10rem !important; min-width: 10rem !important; max-width: 10rem !important;
    }
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] > div {
        width: 10rem !important; min-width: 10rem !important;
    }
    /* 메뉴 글자가 만드는 자동 최소폭 때문에 사이드바가 안 좁아지는 것을 막는다 */
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNav"] ul,
    [data-testid="stSidebarNav"] li,
    [data-testid="stSidebarNav"] a { min-width: 0 !important; max-width: 100% !important; }
    [data-testid="stSidebarNav"] a p { overflow-wrap: anywhere; }
    [data-testid="stSidebarNav"] li { margin: 0 !important; }
    [data-testid="stSidebarNav"] a {
        padding: 0.45rem 0.6rem !important;
    }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] a:hover,
    [data-testid="stSidebarNav"] a:hover * {
        color: #ffcf6b !important;
    }
    /* 첫 항목 'app' 라벨을 '자비스1'로 표시 (app.py는 배포 진입 파일이라 파일명 변경 불가) */
    [data-testid="stSidebarNav"] li:first-child a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:first-child a:hover p::before {
        color: #ffcf6b;
    }
    /* 사이드바 순서: 시장판단 → 자비스1 → 자비스2 → 미국테마 (2026-07-22 사용자 지시).
       파일명은 그대로 두고 flex order로만 표시 순서를 바꾼다. */
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(5) { order: 5; }
    [data-testid="stSidebarNav"] li:nth-child(6) { order: 6; }
    /* 네 번째 항목 '자비스3' 라벨을 '미국테마'로 표시 (파일명 변경 없이 CSS로) */
    [data-testid="stSidebarNav"] li:nth-child(4) a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before {
        content: "미국테마";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a:hover p::before {
        color: #ffcf6b;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before {
        content: "한국테마";
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(5) a:hover p::before {
        color: #ffcf6b;
    }
    [data-testid="stSidebarNav"] li:nth-child(6) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before {
        content: "한국테마\\A(선행감지)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    /* 자비스1 상단 고정 탭바가 사이드바 메뉴를 가리지 않도록 아래로 내림 */
    [data-testid="stSidebarNav"] {
        padding-top: 3.4rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    _jarvis_earth_bytes = (Path(__file__).parent / "assets" / "jarvis_earth.webp").read_bytes()
    _jarvis_earth_src = "data:image/webp;base64," + base64.b64encode(_jarvis_earth_bytes).decode("ascii")
    _jarvis_earth_markup = (
        '<div class="jarvis-earth-visual">'
        '<div class="jarvis-earth-disc">'
        f'<div class="jarvis-earth-surface" role="img" aria-label="한국과 동아시아가 보이는 회전 지구" '
        f'style="--jarvis-earth-texture:url({_jarvis_earth_src})"></div>'
        "</div></div>"
    )
except OSError:
    _jarvis_earth_src = ""
    _jarvis_earth_markup = '<div class="jarvis-earth-fallback" aria-hidden="true"></div>'

# 로그인 화면 지구는 login_globe.py가 WebGL로 그린다(2026-07-23 사용자 지시).
# 전환 연출과 같은 NASA 텍스처를 그대로 넘기므로 파일을 두 번 읽지 않는다.

# 비밀번호 게이트: 인증 전에는 DB 초기화/자동 백업/앱 본문이 전혀 실행되지 않는다.
# 비밀번호는 .streamlit/secrets.toml의 APP_PASSWORD에서만 읽으며 코드에 직접 쓰지 않는다.
try:
    _app_password = st.secrets.get("APP_PASSWORD")
except Exception:
    _app_password = None

if not _app_password:
    st.warning("비밀번호 설정이 필요합니다. .streamlit/secrets.toml에 APP_PASSWORD를 설정하세요.")
    st.stop()

if not st.session_state.get("authenticated"):
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: #01030a !important;
            overflow-x: hidden !important;
        }
        [data-testid="stHeader"] { background: transparent !important; }
        [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
        [data-testid="stMainBlockContainer"] {
            max-width: 1280px !important;
            min-height: 100vh;
            padding: 2.5rem 3rem 2rem !important;
            display: flex;
            align-items: center;
        }
        [data-testid="stAppViewContainer"]::before,
        [data-testid="stAppViewContainer"]::after {
            content: "";
            position: fixed;
            inset: -12%;
            pointer-events: none;
            z-index: 0;
            background-image:
                radial-gradient(circle at 12% 18%, rgba(196, 225, 255, .8) 0 1px, transparent 1.5px),
                radial-gradient(circle at 72% 24%, rgba(120, 180, 255, .62) 0 1px, transparent 1.4px),
                radial-gradient(circle at 38% 76%, rgba(221, 238, 255, .68) 0 1px, transparent 1.5px),
                radial-gradient(circle at 89% 68%, rgba(88, 151, 231, .48) 0 1px, transparent 1.3px);
            background-size: 230px 210px, 310px 280px, 370px 330px, 430px 390px;
            animation: jarvis-star-drift 120s linear infinite;
        }
        [data-testid="stAppViewContainer"]::after {
            opacity: .38;
            transform: rotate(21deg) scale(1.12);
            animation-duration: 180s;
            animation-direction: reverse;
        }
        [data-testid="stMainBlockContainer"] > div { position: relative; z-index: 1; width: 100%; }
        div[data-testid="stHorizontalBlock"]:has(.jarvis-earth-stage) {
            align-items: center !important;
            gap: clamp(2rem, 6vw, 6rem) !important;
            min-height: min(720px, calc(100vh - 5rem));
        }
        div[data-testid="stColumn"]:has(.jarvis-earth-stage) { min-width: 0; }
        div[data-testid="stColumn"]:has(.jarvis-login-panel-heading) {
            min-width: 360px;
            padding: clamp(1.6rem, 3vw, 2.75rem) !important;
            border: 1px solid rgba(85, 151, 236, .3);
            border-radius: 24px;
            background: linear-gradient(145deg, rgba(15, 31, 56, .72), rgba(3, 10, 24, .84));
            box-shadow: 0 30px 90px rgba(0, 0, 0, .48), inset 0 1px rgba(179, 220, 255, .1);
            backdrop-filter: blur(22px) saturate(130%);
            -webkit-backdrop-filter: blur(22px) saturate(130%);
        }
        /* 지구 자리 표식. 실제 그림은 아래 iframe(WebGL 캔버스)이 그리지만,
           바깥 열 배치가 이 클래스의 :has() 선택자에 걸려 있으므로 남겨둔다. */
        .jarvis-earth-stage { width: 100%; height: 0; }
        /* data-testid가 iframe 자체에 붙는 버전과 감싸는 div에 붙는 버전이 모두
           있어 둘 다 잡는다(로컬 1.58 ↔ 온라인 1.59 DOM 차이). */
        iframe[data-testid="stIFrame"],
        div[data-testid="stIFrame"] iframe {
            background: transparent !important;
            border: 0 !important;
            width: 100% !important;
            height: 660px !important;
            display: block;
        }
        /* Streamlit은 컴포넌트를 감싼 칸을 flex: 0 0 <height>px로 못박는다.
           그래서 iframe 높이만 CSS로 줄이면 칸은 그대로 남아 아래에 빈 공간이
           생긴다(2026-07-23 모바일 실측). flex-basis를 풀어 칸이 iframe을
           그대로 감싸게 한다. */
        div[data-testid="stElementContainer"]:has(iframe[data-testid="stIFrame"]) {
            flex: 0 0 auto !important;
            height: auto !important;
        }
        .jarvis-earth-fallback {
            width: min(58vw, 500px);
            aspect-ratio: 1;
            margin: auto;
            border-radius: 50%;
            background: radial-gradient(circle at 34% 30%, #1474c8, #062856 62%, #010611 78%);
            box-shadow: 0 0 38px rgba(55, 173, 255, .48);
        }
        .jarvis-login-panel-heading { margin: 0 0 1.8rem; }
        .jarvis-login-kicker {
            color: #6abaff;
            font: 700 .72rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .22em;
            text-transform: uppercase;
        }
        .jarvis-login-panel-heading h1 {
            margin: .65rem 0 .45rem !important;
            color: #f2f8ff !important;
            font-size: clamp(2rem, 4vw, 3.25rem) !important;
            line-height: 1.04 !important;
            letter-spacing: -.04em;
            text-shadow: 0 0 32px rgba(61, 148, 255, .28);
        }
        .jarvis-login-subtitle { color: #9badc5; font-size: .96rem; line-height: 1.65; }
        .jarvis-login-status {
            display: flex;
            align-items: center;
            gap: .55rem;
            margin-top: 1.25rem;
            color: #7fa5cf;
            font: 600 .72rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .08em;
        }
        .jarvis-login-status::before {
            content: "";
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #3f9cff;
            box-shadow: 0 0 14px #3f9cff;
        }
        .st-key-login_password_input label p { color: #d9e8fa !important; font-weight: 650 !important; }
        .st-key-login_password_input input {
            width: 100% !important;
            min-height: 50px !important;
            color: #f5f9ff !important;
            background: rgba(2, 9, 22, .72) !important;
            border: 1px solid rgba(92, 157, 234, .34) !important;
            border-radius: 12px !important;
            box-shadow: inset 0 1px 8px rgba(0, 0, 0, .35) !important;
        }
        .st-key-login_password_input input:focus {
            border-color: #368ff2 !important;
            box-shadow: 0 0 0 2px rgba(54, 143, 242, .18), 0 0 26px rgba(27, 107, 208, .16) !important;
        }
        .st-key-login_submit button {
            width: 100% !important;
            min-height: 50px !important;
            margin-top: .45rem !important;
            color: #f7fbff !important;
            background: linear-gradient(100deg, #0f58bd, #167ee6 58%, #37a8ff) !important;
            border: 1px solid rgba(125, 202, 255, .54) !important;
            border-radius: 12px !important;
            font-size: 1rem !important;
            font-weight: 800 !important;
            letter-spacing: .08em;
            box-shadow: 0 12px 34px rgba(11, 94, 201, .3), inset 0 1px rgba(255, 255, 255, .18) !important;
        }
        .st-key-login_submit button:hover {
            border-color: #a8ddff !important;
            box-shadow: 0 15px 42px rgba(14, 112, 235, .42), inset 0 1px rgba(255, 255, 255, .24) !important;
        }
        [data-testid="stAlert"] { border-radius: 12px !important; background: rgba(65, 17, 24, .58) !important; }
        @keyframes jarvis-star-drift { to { transform: translate3d(90px, 55px, 0); } }
        @media (max-width: 1100px) {
            [data-testid="stMainBlockContainer"] { padding: 1.25rem 2rem 2rem !important; align-items: flex-start; }
            div[data-testid="stHorizontalBlock"]:has(.jarvis-earth-stage) {
                flex-direction: column !important;
                gap: .35rem !important;
                min-height: auto;
            }
            div[data-testid="stHorizontalBlock"]:has(.jarvis-earth-stage) > div[data-testid="stColumn"] {
                width: 100% !important;
                flex: 1 1 auto !important;
                min-width: 0 !important;
            }
            iframe[data-testid="stIFrame"],
            div[data-testid="stIFrame"] iframe { height: 420px !important; }
            div[data-testid="stColumn"]:has(.jarvis-login-panel-heading) { max-width: 640px; margin-inline: auto; }
        }
        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] { padding: .5rem 1rem 1.25rem !important; }
            iframe[data-testid="stIFrame"],
            div[data-testid="stIFrame"] iframe { height: 340px !important; }
            div[data-testid="stColumn"]:has(.jarvis-login-panel-heading) {
                min-width: 0;
                padding: 1.35rem !important;
                border-radius: 18px;
            }
            .jarvis-login-panel-heading { margin-bottom: 1.15rem; }
            .jarvis-login-panel-heading h1 { font-size: clamp(1.85rem, 10vw, 2.5rem) !important; }
        }
        @media (prefers-reduced-motion: reduce) {
            [data-testid="stAppViewContainer"]::before,
            [data-testid="stAppViewContainer"]::after { animation: none !important; }
            /* 지구 자전은 캔버스 안에서 prefers-reduced-motion을 직접 본다 */
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _login_earth_col, _login_panel_col = st.columns([1.25, 1], gap="large", vertical_alignment="center")
    with _login_earth_col:
        st.markdown('<div class="jarvis-earth-stage" aria-hidden="true"></div>', unsafe_allow_html=True)
        login_globe.render_login_globe(st, _jarvis_earth_src)
    with _login_panel_col:
        st.markdown(
            """
            <div class="jarvis-login-panel-heading">
                <div class="jarvis-login-kicker">SECURE MARKET INTELLIGENCE</div>
                <h1>Stock Event Jarvis</h1>
                <div class="jarvis-login-subtitle">자비스 주식 기록장 · 승인된 사용자만 접근할 수 있습니다.</div>
                <div class="jarvis-login-status">ENCRYPTED SESSION / STANDBY</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # 위에서 아래로 순서대로 입력하고 마지막에 누르는 흐름이 되도록
        # '이동할 곳 → 비밀번호 → 로그인' 순으로 둔다(2026-07-23 사용자 지시).
        # 자비스2/3 선택 시 자비스1 로딩을 건너뛰고 바로 진입해 대기 시간을 없앤다.
        _login_dest = st.radio(
            "로그인 후 이동",
            [
                "시장 판단",
                "자비스1 (기록장)",
                "자비스2 (순환매 플레이북)",
                "미국테마 (자비스3)",
                "한국테마 (자비스4)",
                "한국테마 선행감지 (자비스5·실험)",
            ],
            index=2,  # 기존 자비스2 기본 이동을 그대로 유지한다
            horizontal=True,
            key="login_dest_choice",
        )
        _login_password_input = st.text_input("비밀번호", type="password", key="login_password_input")
        if st.button("로그인", key="login_submit", use_container_width=True):
            if _login_password_input == _app_password:
                st.session_state["authenticated"] = True
                if str(_login_dest).startswith("시장 판단"):
                    st.switch_page("pages/0_시장판단.py")
                if str(_login_dest).startswith("자비스2"):
                    st.switch_page("pages/1_자비스2.py")
                if str(_login_dest).startswith("미국테마"):
                    st.switch_page("pages/2_자비스3.py")
                # '한국테마 선행감지'가 '한국테마'로 먼저 잡혀 자비스4로 새면 안 된다 —
                # 더 긴 이름을 먼저 검사한다(2026-07-24 이름 변경).
                if str(_login_dest).startswith("한국테마 선행감지"):
                    st.switch_page("pages/4_자비스5.py")
                if str(_login_dest).startswith("한국테마"):
                    st.switch_page("pages/3_자비스4.py")
                st.session_state["login_transition_pending"] = True
                # 로그인할 때마다 한국장 3단계 자동 조회를 새로 시작한다. 이전 인증
                # 세션의 완료 플래그가 남아 버튼을 직접 눌러야 했던 회귀를 막는다.
                for _kr_auto_key in (
                    "kr_auto_run_version",
                    "kr_auto_run_stage1_done",
                    "kr_auto_run_stage2_done",
                    "kr_theme_auto_fetch_pending",
                    "kr_bookmaker_auto_fetch_pending",
                    "us_auto_run_version",
                    "us_auto_run_stage1_done",
                    "parallel_warmup_done",
                ):
                    st.session_state.pop(_kr_auto_key, None)
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# 로그인 화면에는 Streamlit과 정적 이미지밖에 필요하지 않다. 시세·뉴스·DB 모듈은
# 인증 뒤에 불러와 무료 서버의 첫 비밀번호 화면을 최대한 빨리 표시한다.
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import database as db
import disclosure_data
import login_visual
import news_data
import performance
import bookmaker_data
import deepl_translate
import theme_data
import theme_history
import price_data
import kis_market_data
import naver_market_data

_login_transition_pending = bool(st.session_state.get("login_transition_pending"))
_login_transition_rendered_early = False
if _login_transition_pending:
    # 본문보다 먼저 고정 오버레이를 보내 자비스 화면이 순간 노출되는 플래시를 막는다.
    st.session_state.pop("login_transition_pending", None)
    login_visual.render_login_transition(st, _jarvis_earth_markup)
    _login_transition_rendered_early = True


@st.cache_resource(show_spinner=False)
def _initialize_database_once():
    """원격 DB의 스키마 확인을 서버 프로세스마다 한 번만 수행한다."""
    db.init_db()
    return True


_initialize_database_once()
create_daily_db_backup_once()

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif;
        font-size: 17px;
    }
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0f1117 !important;
    }
    h1 {
        font-size: 1.9rem !important;
    }
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: #CBD5E1 !important;
        font-size: 16px !important;
        line-height: 1.5 !important;
    }
    .stMarkdown p,
    [data-testid="stText"],
    [data-testid="stAlert"] p,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stRadio"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,
    [data-testid="stTextInput"] label,
    [data-testid="stTextArea"] label {
        color: #eef2f7 !important;
        font-size: 17px !important;
        line-height: 1.5 !important;
    }
    button,
    button p {
        font-size: 17px !important;
        font-weight: 700 !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {
        color: #f3f4f6 !important;
        font-size: 17px !important;
        font-weight: 700 !important;
        line-height: 1.5 !important;
    }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
        color: #e5e7eb !important;
        font-size: 17px !important;
        line-height: 1.55 !important;
    }
    [data-testid="stExpander"] {
        background-color: rgba(23, 26, 33, 0.92);
        border: 1px solid #303642;
        border-radius: 10px;
        margin-bottom: 8px;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] > div,
    [data-testid="stMultiSelect"] > div,
    [data-testid="stDateInput"] input {
        background-color: #20232b !important;
        border-radius: 6px !important;
        border: 1px solid #303642 !important;
    }
    /* 표(데이터프레임) 가독성: 배경과 확실히 구분되는 어두운 카드톤 + 또렷한 글자 */
    [data-testid="stDataFrame"] {
        background-color: rgba(15, 18, 26, 0.96) !important;
        border: 1px solid #303642;
        border-radius: 10px;
        padding: 2px;
    }
    [data-testid="stDataFrame"] [role="row"] {
        min-height: 38px;
    }
    [data-testid="stDataFrame"] [role="columnheader"],
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataEditor"] [role="columnheader"],
    [data-testid="stDataEditor"] [role="gridcell"] {
        font-size: 15px !important;
        line-height: 1.5 !important;
    }
    [data-testid="stDataFrame"] * {
        color: #e8ebf0 !important;
    }
    [data-testid="stMetric"] {
        background-color: rgba(23, 26, 33, 0.92);
        border: 1px solid #303642;
        border-radius: 10px;
        padding: 10px 14px;
    }
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"] p {
        font-size: 16px !important;
        color: #CBD5E1 !important;
    }
    .st-key-kr_market_overview_load button,
    .st-key-us_market_overview_load button {
        background: #2563EB !important;
        color: #FFFFFF !important;
        border: 1px solid #60A5FA !important;
        border-radius: 8px !important;
        font-size: 18px !important;
        font-weight: 800 !important;
        padding: 0.65rem 1.25rem !important;
        min-height: 3rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        line-height: 1.2 !important;
    }
    /* 라벨-드롭박스/입력창 간격 좁히기 (공통) */
    [data-testid="stWidgetLabel"] {
        margin-bottom: 2px !important;
        padding-bottom: 0 !important;
    }
    [data-testid="stWidgetLabel"] p {
        margin-bottom: 0 !important;
    }
    .st-key-kr_market_overview_load button:hover,
    .st-key-us_market_overview_load button:hover {
        background: #1D4ED8 !important;
        border-color: #93C5FD !important;
    }
    .st-key-snap_mood_auto_check button,
    .st-key-snap_auto_fill button {
        background-color: #475569 !important;
        border-color: #64748B !important;
        color: #F8FAFC !important;
    }
    button[kind="primary"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
    }
    /* v1.1 UX: 한국장/미국장 핵심 실행 버튼 강조 (조회/계산=주황, 저장=파랑).
       글자를 크고 굵게, 버튼 높이/클릭 영역도 키운다. */
    .st-key-snap_auto_fill button,
    .st-key-us_stock_auto_fill button,
    .st-key-kr_quick_save button,
    .st-key-kr_quick_confirm_save button,
    .st-key-us_swing_quick_save button,
    .st-key-us_final_save button,
    .st-key-snap_mood_auto_check button {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        padding: 14px 22px !important;
        min-height: 52px !important;
    }
    .st-key-snap_auto_fill button p,
    .st-key-us_stock_auto_fill button p,
    .st-key-kr_quick_save button p,
    .st-key-kr_quick_confirm_save button p,
    .st-key-us_swing_quick_save button p,
    .st-key-us_final_save button p,
    .st-key-snap_mood_auto_check button p {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
    }
    .st-key-snap_auto_fill button,
    .st-key-us_stock_auto_fill button {
        background-color: #F97316 !important;
        border-color: #F97316 !important;
        color: #1a1a1a !important;
    }
    .st-key-kr_quick_save button,
    .st-key-kr_quick_confirm_save button,
    .st-key-us_swing_quick_save button,
    .st-key-us_final_save button {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        color: #ffffff !important;
    }
    .st-key-snap_mood_auto_check button {
        background-color: #0047AB !important;
        border-color: #0047AB !important;
        color: #ffffff !important;
    }
    .st-key-kr_auto_preview_run button {
        background-color: #FACC15 !important;
        border-color: #EAB308 !important;
        color: #1a1a1a !important;
        font-size: 1.22rem !important;
        font-weight: 900 !important;
        padding: 16px 24px !important;
        min-height: 58px !important;
    }
    .st-key-kr_auto_preview_run button p {
        font-size: 1.22rem !important;
        font-weight: 900 !important;
    }
    /* 핵심 실행·저장 버튼만 강조한다. 일반 버튼/탭/expander/필터는 대상에서 제외한다.
       snap_auto_fill/snap_mood_auto_check/us_stock_auto_fill("조회/계산" 성격의 버튼)는
       이 노란색 강조에서 제외한다 — 대표 버튼(kr_auto_preview_run)과 색이 같아서 구분이
       안 된다는 지적(2026-07-12 스크린샷) 반영. us_stock_auto_fill은 전체 코드검사(2026-07-13
       울트라 리뷰)에서 같은 문제가 미국장 쪽에도 남아있는 걸 발견해 같이 제외했다. 원래
       지정색(주황/진파랑, 위쪽 규칙)이 다시 적용된다. */
    .st-key-kr_dart_check_button button,
    .st-key-kr_naver_news_check_button button,
    .st-key-us_naver_news_check_button button,
    [class*="st-key-kr_retry_failed_auto_fetch"] button,
    [class*="st-key-us_retry_failed_auto_fetch"] button,
    .st-key-kr_quick_save button,
    .st-key-kr_quick_confirm_save button,
    .st-key-us_swing_quick_save button,
    .st-key-us_final_save button,
    [class*="st-key-tab3_"] button,
    [class*="st-key-tab4_"] button {
        background-color: #facc15 !important;
        border: 1px solid #ca8a04 !important;
        color: #111827 !important;
        min-height: 44px !important;
        font-size: 17px !important;
        font-weight: 800 !important;
    }
    .st-key-kr_dart_check_button button p,
    .st-key-kr_naver_news_check_button button p,
    .st-key-us_naver_news_check_button button p,
    [class*="st-key-kr_retry_failed_auto_fetch"] button p,
    [class*="st-key-us_retry_failed_auto_fetch"] button p,
    .st-key-kr_quick_save button p,
    .st-key-kr_quick_confirm_save button p,
    .st-key-us_swing_quick_save button p,
    .st-key-us_final_save button p,
    [class*="st-key-tab3_"] button p,
    [class*="st-key-tab4_"] button p {
        color: #111827 !important;
        font-size: 17px !important;
        font-weight: 800 !important;
    }
    .st-key-kr_dart_check_button button:hover,
    .st-key-kr_naver_news_check_button button:hover,
    .st-key-us_naver_news_check_button button:hover,
    [class*="st-key-kr_retry_failed_auto_fetch"] button:hover,
    [class*="st-key-us_retry_failed_auto_fetch"] button:hover,
    .st-key-kr_quick_save button:hover,
    .st-key-kr_quick_confirm_save button:hover,
    .st-key-us_swing_quick_save button:hover,
    .st-key-us_final_save button:hover,
    [class*="st-key-tab3_"] button:hover,
    [class*="st-key-tab4_"] button:hover {
        background-color: #fde047 !important;
        color: #111827 !important;
    }
    .st-key-kr_dart_check_button button:disabled,
    .st-key-kr_naver_news_check_button button:disabled,
    .st-key-us_naver_news_check_button button:disabled,
    [class*="st-key-kr_retry_failed_auto_fetch"] button:disabled,
    [class*="st-key-us_retry_failed_auto_fetch"] button:disabled,
    .st-key-kr_quick_save button:disabled,
    .st-key-kr_quick_confirm_save button:disabled,
    .st-key-us_swing_quick_save button:disabled,
    .st-key-us_final_save button:disabled,
    [class*="st-key-tab3_"] button:disabled,
    [class*="st-key-tab4_"] button:disabled {
        background-color: #4b5563 !important;
        border-color: #6b7280 !important;
        color: #d1d5db !important;
    }
    /* 상단 메뉴(탭) 확대 + 실제 고정(fixed) + 현재 선택 강조.
       주의: 이 구조에서 position:sticky는 조상 컨테이닝 블록 제약 때문에 실제로 고정되지
       않는다(브라우저에서 직접 확인, scrollTop 이동 시 sticky는 함께 스크롤되어 사라짐).
       position:fixed로 뷰포트 기준 고정하고, 바로 아래 탭 내용에 그만큼 padding-top을 더해
       가려지지 않게 한다. */
    [data-testid="stTabs"] [data-baseweb="tab-list"],
    [data-testid="stTabs"] [role="tablist"] {
        position: fixed !important;
        top: 60px;
        left: 0;
        right: 0;
        width: 100%;
        z-index: 999999;
        background-color: rgba(2, 6, 23, 0.98);
        border-bottom: 1px solid #303642;
        padding: 10px 24px 6px 24px !important;
        gap: 6px;
    }
    [data-testid="stTabs"] [data-baseweb="tab-panel"] {
        padding-top: 64px !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        padding: 14px 22px !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] p {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(37, 99, 235, 0.28);
        border-bottom: 4px solid #ff4b4b !important;
        border-radius: 6px 6px 0 0;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {
        color: #ffffff !important;
    }
    /* Readability pass: scoped text, controls, tables, and vertical rhythm. */
    .stMarkdown p,
    [data-testid="stText"],
    [data-testid="stAlert"] p {
        font-size: 19px !important;
        line-height: 1.75 !important;
        margin-bottom: 1.75rem !important;
    }
    /* 라벨류는 폰트 확대만 적용하고 margin-bottom은 적용하지 않는다 — 라벨-드롭박스
       간격 좁히기 규칙([data-testid="stWidgetLabel"], 위쪽)과 충돌해서 간격이 다시
       벌어지는 걸 막기 위함(2026-07-13, 7/12 스크린샷 지적 항목 수정). */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stRadio"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,
    [data-testid="stTextInput"] label,
    [data-testid="stTextArea"] label {
        font-size: 19px !important;
        line-height: 1.75 !important;
    }
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: #CBD5E1 !important;
        font-size: 18px !important;
        line-height: 1.7 !important;
        margin-bottom: 1.75rem !important;
    }
    button, button p {
        font-size: 19px !important;
        line-height: 1.5 !important;
        font-weight: 700 !important;
        min-height: 3rem;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {
        font-size: 19px !important;
        line-height: 1.65 !important;
        margin-bottom: 0 !important;
    }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
        font-size: 19px !important;
        line-height: 1.7 !important;
        margin-bottom: 1.75rem !important;
    }
    [data-testid="stDataFrame"] [role="columnheader"],
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataEditor"] [role="columnheader"],
    [data-testid="stDataEditor"] [role="gridcell"] {
        font-size: 17px !important;
        line-height: 1.65 !important;
        padding-top: 8px !important;
        padding-bottom: 8px !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"] p {
        font-size: 18px !important;
        line-height: 1.5 !important;
    }
    html body [data-testid="stTabs"] [data-baseweb="tab"],
    html body [data-testid="stTabs"] [data-baseweb="tab"] p,
    html body [data-testid="stTabs"] [role="tab"],
    html body [data-testid="stTabs"] [role="tab"] p,
    html body [data-testid="stTabs"] [role="tab"] div {
        font-size: 28px !important;
        font-weight: 800 !important;
        line-height: 1.5 !important;
    }
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 {
        margin-top: 2.5rem !important;
        margin-bottom: 1rem !important;
        line-height: 1.4 !important;
    }
    @media (max-width: 1200px) {
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            flex: 0 0 auto !important;
            white-space: nowrap !important;
        }
        .st-key-market_overview_cards_kr [data-testid="stHorizontalBlock"],
        .st-key-market_overview_cards_us [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 14px !important;
        }
        .st-key-market_overview_cards_kr [data-testid="stHorizontalBlock"] > div,
        .st-key-market_overview_cards_us [data-testid="stHorizontalBlock"] > div {
            width: auto !important;
            flex: none !important;
            min-width: 0 !important;
        }
        [data-testid="stHorizontalBlock"]:has([class*="st-key-mockup1_candidate_"]) {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 12px !important;
        }
        [data-testid="stHorizontalBlock"]:has([class*="st-key-mockup1_candidate_"]) > div {
            width: auto !important;
            flex: none !important;
            min-width: 0 !important;
        }
        .st-key-kr_theme_reference [data-testid="stHorizontalBlock"] {
            grid-template-columns: minmax(0, 1fr) !important;
        }
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            max-width: 100% !important;
            overflow-x: auto !important;
        }
    }
    @media (max-width: 680px) {
        .st-key-market_overview_cards_kr [data-testid="stHorizontalBlock"],
        .st-key-market_overview_cards_us [data-testid="stHorizontalBlock"] {
            grid-template-columns: minmax(0, 1fr) !important;
        }
        [data-testid="stHorizontalBlock"]:has([class*="st-key-mockup1_candidate_"]) {
            grid-template-columns: minmax(0, 1fr) !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div style="height:76px;"></div>', unsafe_allow_html=True)  # 고정 상단 메뉴에 가리지 않도록 여백 확보
# 한국장/미국장 사용 순서 안내는 각 화면(🇰🇷 한국장 먼저 확인 / 🇺🇸 미국장 스윙 확인) 상단의
# 짧은 안내문으로만 표시한다(예: "① ... → ② ... → ③ ..."). 여기(상단 공통 영역)에는
# 별도 카드를 두지 않아 본문보다 커 보이지 않게 한다.

VERDICT_ORDER = [
    "추천 후보",
    "감시",
    "확인 필요",
    "보류(선반영)",
    "제외",
]

# 화면 표시용 이름/색상 매핑. 내부 저장값(VERDICT_CHOICES/SIGNAL_TYPE_CHOICES/TRADE_MODE_CHOICES)은 그대로 둔다.
VERDICT_DISPLAY = {
    "추천 후보": "1순위 후보",
    "감시": "관찰 후보",
    "확인 필요": "재확인",
    "보류(선반영)": "보류",
    "제외": "제외",
}
REVERSE_VERDICT_DISPLAY = {v: k for k, v in VERDICT_DISPLAY.items()}

# 결과 확인 화면 / 장중 스냅샷 전용 "후보 점수". 실제 상승확률이 아니라 가격 위치·고점 대비
# 밀림·거래대금·판정을 기준으로 만든 화면 표시용 상대 우선순위 숫자다. DB 컬럼이 아니라
# 표를 그릴 때만 계산하며, 100점이 자동으로 나오지 않도록 항상 상한을 둔다.
CANDIDATE_BASE_SCORE = {
    "추천 후보": 85,
    "1순위 후보": 85,
    "감시": 65,
    "관찰 후보": 65,
    "확인 필요": 50,
    "재확인": 50,
    "보류(선반영)": 25,
    "보류": 25,
    "제외": 0,
}

_BASIS_PATTERNS = {
    "change_pct": r"전일대비\s*([+-]?\d+(?:\.\d+)?)%",
    "open_pos_pct": r"시가대비\s*([+-]?\d+(?:\.\d+)?)%",
    "high_drop_pct": r"고점대비\s*([+-]?\d+(?:\.\d+)?)%",
    "turnover_ratio_pct": r"시총대비\s*거래대금\s*([+-]?\d+(?:\.\d+)?)%",
}


def extract_score_basis_from_text(*texts):
    """report_item의 텍스트 필드들에서 전일대비/시가대비/고점대비/시총대비 거래대금 값을 뽑는다.

    장중 스냅샷의 "브리핑 입력용 문장 만들기"가 만드는 형식과 호환된다. 못 찾은 값은 None —
    이 경우 compute_candidate_score()는 판정 기본점수만 사용한다(자유 서술형 텍스트도 정상
    지원해야 하므로, 숫자 근거가 없다고 오류를 내지 않는다).
    """
    combined = " ".join(t for t in texts if t)
    basis = {}
    for key, pattern in _BASIS_PATTERNS.items():
        m = re.search(pattern, combined)
        basis[key] = float(m.group(1)) if m else None
    return basis


def compute_candidate_score(verdict, trade_mode, basis):
    """0~100 사이 "후보 점수"를 계산한다 (실제 상승확률 아님, 화면 표시 전용).

    판정 기본점수에서 시작해 시가대비/고점대비/시총대비 거래대금으로 가감하고,
    "단타+보류"는 강제로 낮게, 그 외 모든 경우도 100점이 자동으로 나오지 않도록 상한을 둔다.
    """
    score = float(CANDIDATE_BASE_SCORE.get(verdict, 50))

    open_pos = basis.get("open_pos_pct")
    high_drop = basis.get("high_drop_pct")
    turnover_ratio = basis.get("turnover_ratio_pct")

    if open_pos is not None:
        score += max(min(open_pos, 5.0), -5.0)

    if high_drop is not None:
        if high_drop <= -5:
            score -= 15
        elif high_drop <= -3:
            score -= 7
        elif high_drop <= -1:
            score -= 2
        else:
            score += 3

    if turnover_ratio is not None:
        if turnover_ratio >= 3:
            score += 5
        elif turnover_ratio >= 1:
            score += 2

    if trade_mode == "단타" and verdict in ("보류(선반영)", "보류"):
        score = min(score, 35)

    return round(max(0.0, min(score, 97.0)), 1)


def compute_snapshot_reference_score(
    mode, change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct
):
    """장중 스냅샷에서 판정이 정해지기 전, 계산된 지표만으로 만드는 참고용 점수.

    자동매수 추천이 아니라 장중 후보 비교용 참고 점수다. 이 점수는 오늘 주가에서 계산된
    지표(change_pct/open_pos_pct/high_drop_pct/turnover_ratio_pct)로만 산출하며, 시장
    분위기(시황) 등 다른 참고값은 반영하지 않는다. 최고점은 88점으로 제한한다.
    """
    if mode == "단타":
        score = 45.0
        if open_pos_pct is not None:
            if open_pos_pct < 0:
                score -= 12
            elif open_pos_pct >= 3:
                score += 15
            elif open_pos_pct >= 1:
                score += 8
        if high_drop_pct is not None:
            if high_drop_pct >= -1.5:
                score += 15
            elif high_drop_pct >= -3:
                score += 8
            elif high_drop_pct <= -6:
                score -= 25
            elif high_drop_pct <= -5:
                score -= 20
        if turnover_ratio_pct is not None and turnover_ratio_pct >= 1:
            score += 10
        if change_pct is not None:
            if change_pct < 0:
                score -= 10
            elif change_pct >= 5:
                score += 5
        # 고점 대비 밀림이 -5% 이하면, 다른 지표가 아무리 좋아도 단타 생존력은
        # 이미 훼손된 것으로 보고 상한을 45점으로 눌러 다른 가산점이 이를
        # 덮어쓰지 못하게 한다.
        if high_drop_pct is not None and high_drop_pct <= -5:
            score = min(score, 45.0)
    else:  # 스윙
        score = 50.0
        if change_pct is not None:
            if change_pct < 0:
                score -= 10
            elif change_pct >= 5:
                score += 12
            elif change_pct >= 3:
                score += 8
            elif change_pct >= 1:
                score += 4
        if open_pos_pct is not None:
            if open_pos_pct < 0:
                score -= 8
            elif open_pos_pct >= 3:
                score += 12
            elif open_pos_pct >= 1:
                score += 7
            elif open_pos_pct >= 0:
                score += 3
        if high_drop_pct is not None:
            if high_drop_pct >= -1.5:
                score += 10
            elif high_drop_pct >= -3:
                score += 5
            elif high_drop_pct <= -6:
                score -= 20
            elif high_drop_pct <= -5:
                score -= 15
        if turnover_ratio_pct is not None:
            if turnover_ratio_pct >= 1:
                score += 8
            elif turnover_ratio_pct >= 0.4:
                score += 4

    return round(max(0.0, min(score, 88.0)), 1)


def _kr_danta_verdict(danta_score):
    """단기 관심 점수 기준 국내장 단타 판단(국내장 기록 바로 저장 전용).

    65점 이상 -> 감시, 45점 미만 -> 보류(선반영), 그 사이 -> 확인 필요(재확인 표시).
    """
    if danta_score >= 65:
        return "감시"
    if danta_score < 45:
        return VERDICT_NORMALIZE["보류"]
    return "확인 필요"


def _kr_swing_verdict(swing_score):
    """며칠 관심 점수 기준 국내장 스윙 판단(국내장 기록 바로 저장 전용).

    75점 이상 -> 관심 후보(추천 후보), 55점 이상 -> 감시, 그 미만 -> 보류(선반영).
    """
    if swing_score >= 75:
        return VERDICT_NORMALIZE["관심 후보"]
    if swing_score >= 55:
        return "감시"
    return VERDICT_NORMALIZE["보류"]


def _kr_score_reason_text(change_pct, open_pos_pct, turnover_ratio_pct):
    """국내장 기록 바로 저장 전용 점수 근거 한 줄 요약(계산된 지표 기반, 자동매수 근거 아님)."""
    parts = []
    if open_pos_pct is not None:
        parts.append("시가 위 유지" if open_pos_pct >= 0 else "시가 대비 약세")
    if change_pct is not None and change_pct >= 3:
        parts.append("전일 대비 상승폭 큼")
    if turnover_ratio_pct is not None and turnover_ratio_pct >= 1:
        parts.append("거래대금 증가")
    return " + ".join(parts) if parts else "특이 사항 없음"


def _kr_penalty_reason_text(high_drop_pct, change_pct):
    """국내장 기록 바로 저장 전용 감점 이유 한 줄 요약."""
    parts = []
    if high_drop_pct is not None and high_drop_pct <= -3:
        parts.append("장중 고점 대비 밀림")
    if change_pct is not None and change_pct < 0:
        parts.append("전일 대비 하락")
    return ", ".join(parts) if parts else "특별한 감점 요인 없음"


def _kr_top_candidate_reason_text(trade_mode, score, verdict_display):
    """국내장 기록 바로 저장 전용 1순위 후보 근거 한 줄 요약. 실제로 1순위 조건을
    충족했을 때만 긍정적으로 서술하고, 그렇지 않으면 부족한 상태를 그대로 알린다."""
    if trade_mode == "단타" and score >= 65:
        return "관찰 종목 중 단기 생존력(시가 위치·고점 대비 밀림)이 상대적으로 강함"
    if trade_mode == "스윙" and score >= 75:
        return "관찰 종목 중 거래대금과 추세가 상대적으로 강함"
    return f"현재 {verdict_display} 단계로 1순위 조건에는 못 미침"


def _kr_preview_reasons(change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, trade_mode):
    """국내장 바로 저장의 "저장 전 자동계산 미리보기" 전용: 시가 위치/고점 대비 밀림/거래대금
    신호를 수치 기반 문구로 만든다. 자동 점수 계산(_auto_fill_item_display)의 신호 카테고리
    판단 함수(_resolve_signal_category)를 그대로 재사용해 문구 스타일을 통일하고, 같은 의미의
    신호가 중복 표시되지 않게 한다. 반환: (score_reason, penalty_reason).
    """
    drop_from_high_pct = -high_drop_pct if high_drop_pct is not None else None
    high_drop_pos_threshold = 2 if trade_mode == "단타" else 3
    high_drop_neg_threshold = 5 if trade_mode == "단타" else 7
    liquidity_pos_threshold = 0.3 if trade_mode == "단타" else 0.2

    price_direction, price_phrase = _resolve_signal_category(
        "",
        [],
        [],
        open_pos_pct,
        lambda v: v > 0,
        lambda v: v < 0,
        lambda v: f"시가 대비 {v:+.2f}%로 시가 위 유지",
        lambda v: f"시가 대비 {v:+.2f}%로 시가 아래",
    )
    high_drop_direction, high_drop_phrase = _resolve_signal_category(
        "",
        [],
        [],
        drop_from_high_pct,
        lambda v, t=high_drop_pos_threshold: v <= t,
        lambda v, t=high_drop_neg_threshold: v >= t,
        lambda v: f"고점 대비 밀림 {v:.2f}%로 장중 생존력 양호",
        lambda v: f"고점 대비 {v:.2f}% 밀림",
    )
    liquidity_direction, liquidity_phrase = _resolve_signal_category(
        "",
        [],
        [],
        turnover_ratio_pct,
        lambda v, t=liquidity_pos_threshold: v >= t,
        lambda v: v < 0.1,
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 양호",
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 부족",
    )

    gains = []
    penalties = []
    if change_pct is not None:
        if change_pct > 0:
            gains.append(f"전일 대비 {change_pct:+.2f}%로 상승")
        elif change_pct < 0:
            penalties.append(f"전일 대비 {change_pct:+.2f}%로 하락")
    if price_direction == "positive":
        gains.append(price_phrase)
    elif price_direction == "negative":
        penalties.append(price_phrase)
    if high_drop_direction == "positive":
        gains.append(high_drop_phrase)
    elif high_drop_direction == "negative":
        penalties.append(high_drop_phrase)
    if liquidity_direction == "positive":
        gains.append(liquidity_phrase)
    elif liquidity_direction == "negative":
        penalties.append(liquidity_phrase)

    score_reason = ", ".join(gains) if gains else "특이 사항 없음"
    penalty_reason = ", ".join(penalties) if penalties else "없음"
    return score_reason, penalty_reason


def build_kr_stage2_preview():
    """한국장 2단계(관심점수/단타·스윙 판단/1순위 근거/감점 이유) 미리보기 전용 함수.

    session_state에 있는 현재 입력값(0단계 시장 분위기 자동 확인 결과, 1단계 오늘 주가 자동
    채우기 결과가 반영돼 있으면 그 값)을 그대로 읽어서 계산만 한다. DB에는 아무 것도 저장하지
    않으며, "③ 국내장 기록 바로 저장" 버튼의 저장 로직은 호출하지도, 그 결과에 영향을 주지도
    않는다 — 이 함수는 미리보기 전용이고 저장 버튼의 내부 로직과는 완전히 분리되어 있다.
    """
    stage0_reflected = bool(st.session_state.get("kr_mood_auto_results"))
    stage1_reflected = bool(st.session_state.get("snap_auto_fill_results"))

    rows = []
    for s in SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)

        danta_score = compute_snapshot_reference_score(
            "단타", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct
        )
        swing_score = compute_snapshot_reference_score(
            "스윙", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct
        )
        danta_verdict = _kr_danta_verdict(danta_score)
        swing_verdict = _kr_swing_verdict(swing_score)
        danta_score_reason, danta_penalty_reason = _kr_preview_reasons(
            change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, "단타"
        )
        swing_score_reason, swing_penalty_reason = _kr_preview_reasons(
            change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, "스윙"
        )
        row_validation_errors = _validate_snapshot_price_inputs(
            s["name"], current, open_price, high, low,
            _get_snapshot_value(ticker, "volume"), turnover,
        )

        rows.append(
            {
                "name": s["name"],
                "ticker": ticker,
                "danta_score": danta_score,
                "swing_score": swing_score,
                "danta_verdict": danta_verdict,
                "swing_verdict": swing_verdict,
                "change_pct": change_pct,
                "open_pos_pct": open_pos_pct,
                "high_drop_pct": high_drop_pct,
                "turnover_ratio_pct": turnover_ratio_pct,
                "turnover": turnover,
                "danta_score_reason": danta_score_reason,
                "danta_penalty_reason": danta_penalty_reason,
                "swing_score_reason": swing_score_reason,
                "swing_penalty_reason": swing_penalty_reason,
                "danta_top_candidate_reason": _kr_top_candidate_reason_text(
                    "단타", danta_score, _display_verdict_name(danta_verdict)
                ),
                "swing_top_candidate_reason": _kr_top_candidate_reason_text(
                    "스윙", swing_score, _display_verdict_name(swing_verdict)
                ),
                "risk_fields": _collect_risk_fields(ticker),
                "danta_buy_confirm_condition": _auto_buy_confirm_condition("단타", "KR", turnover_ratio_pct),
                "swing_buy_confirm_condition": _auto_buy_confirm_condition("스윙", "KR", turnover_ratio_pct),
                "needs_confirmation": (danta_verdict == "확인 필요") or bool(row_validation_errors),
                "validation_errors": row_validation_errors,
            }
        )

    return {
        "rows": rows,
        "stage0_reflected": stage0_reflected,
        "stage1_reflected": stage1_reflected,
    }


def _memoized_kr_stage2_preview():
    """build_kr_stage2_preview()를 세션 안에서 짧게 메모이즈한다.

    2026-07-15: st.rerun(scope="fragment")를 시도했다가 Streamlit 공식 문서에
    "fragment가 이미 앱 전체 재실행의 일부로 실행 중이면 fragment-scope rerun은
    허용되지 않는다"는 제약이 있어(실제 소스 확인) 되돌렸다 — 종목 카드 하나 클릭할
    때마다 여전히 전체 rerun이 일어난다. 대신 실제 계산량을 줄인다: build_kr_stage2_preview()는
    12종목마다 단타·스윙 점수·근거 문장을 전부 새로 만드는데, 입력값(종목 목록·오늘 주가
    자동채우기 결과)이 안 바뀌었으면 같은 결과가 나온다 — 카드 클릭처럼 입력값을 안 바꾸는
    rerun에서는 재사용한다.
    """
    # 종목별 상세 입력 카드는 사용자가 직접 값을 고쳐 쓸 수 있고(snap_{ticker}_{field}),
    # build_kr_stage2_preview()는 가격 필드 외에도 진입가·손절가 등 위험관리 입력값
    # (_collect_risk_fields)까지 읽는다. 특정 필드만 골라 캐시 키에 넣으면 나중에
    # 함수가 새 필드를 더 읽게 됐을 때 캐시가 그 변경을 놓치고 옛 값을 돌려줄 수 있으므로,
    # snap_{ticker}_ 로 시작하는 session_state 항목을 통째로 스캔해 키를 만든다
    # (한국 종목 티커는 밑줄을 포함하지 않으므로 "snap_티커_필드명" 분리가 안전하다).
    _ticker_list = [s["ticker"] for s in SNAPSHOT_STOCKS]
    _ticker_set = set(_ticker_list)
    _snap_state = {}
    for _k, _v in st.session_state.items():
        if not _k.startswith("snap_"):
            continue
        _parts = _k.split("_", 2)
        if len(_parts) == 3 and _parts[1] in _ticker_set:
            _snap_state.setdefault(_parts[1], []).append((_parts[2], _v))
    _cache_key = (
        tuple(
            (t, tuple(sorted(_snap_state.get(t, []))))
            for t in _ticker_list
        ),
        st.session_state.get("kr_mood_auto_results") is not None,
    )
    _cache = st.session_state.get("_kr_stage2_preview_cache")
    if _cache and _cache.get("key") == _cache_key:
        return _cache["value"]
    _value = build_kr_stage2_preview()
    st.session_state["_kr_stage2_preview_cache"] = {"key": _cache_key, "value": _value}
    return _value


def _us_swing_upside_score(change_pct):
    """상승률 점수(0~20). 전일 대비 등락률 기준."""
    if change_pct is None:
        return 0.0, "전일대비 데이터 없음"
    if change_pct >= 6:
        return 20.0, f"전일 대비 약 {change_pct:+.1f}% 이상 급등"
    if change_pct >= 4:
        return 16.0, f"전일 대비 {change_pct:+.1f}% 상승"
    if change_pct >= 2:
        return 12.0, f"전일 대비 {change_pct:+.1f}% 상승"
    if change_pct >= 0:
        return 8.0, f"전일 대비 {change_pct:+.1f}% 소폭 상승"
    return 4.0, f"전일 대비 {change_pct:+.1f}% 하락"


def _us_swing_close_pos_score(high_drop_pct):
    """종가 위치 점수(0~20). 장중 고점 대비 마감 위치 기준."""
    if high_drop_pct is None:
        return 0.0, "고점 대비 데이터 없음"
    if high_drop_pct >= -1:
        return 20.0, "장중 고가 근처에서 마감"
    if high_drop_pct >= -3:
        return 14.0, f"고점 대비 {high_drop_pct:.1f}%로 소폭 밀림"
    if high_drop_pct >= -5:
        return 8.0, f"고점 대비 {high_drop_pct:.1f}%로 밀림"
    return 4.0, f"고점 대비 {high_drop_pct:.1f}%로 크게 밀림"


def _us_swing_market_mood_score():
    """시장 분위기 점수(0~15). 나스닥100 선물 등락률 + 외부 환경 방향 입력을 종합.

    아무것도 입력하지 않았으면 중립값(7.5)을 준다(과대/과소 확정 방지).
    """
    nq_change = st.session_state.get("snap_nq_change", 0.0) or 0.0
    favorable = {"강함", "상승", "순매수"}
    unfavorable = {"약함", "하락", "순매도"}
    dirs = {
        "SOXX/SMH": st.session_state.get("snap_soxx_dir", "미입력"),
        "KOSPI200 선물": st.session_state.get("snap_kospi200_dir", "미입력"),
        "외국인 선물": st.session_state.get("snap_foreign_dir", "미입력"),
        "프로그램 수급": st.session_state.get("snap_program_dir", "미입력"),
    }
    fav = [k for k, v in dirs.items() if v in favorable]
    unfav = [k for k, v in dirs.items() if v in unfavorable]

    score = 7.5
    if nq_change >= 1:
        score += 4
    elif nq_change >= 0.3:
        score += 2
    elif nq_change < 0:
        score -= 2
    score += len(fav) * 1.5
    score -= len(unfav) * 1.5
    score = round(max(0.0, min(score, 15.0)), 1)

    if not fav and not unfav and not nq_change:
        note = "시장 분위기 입력 없음(중립 처리)"
    else:
        parts = []
        if nq_change:
            parts.append(f"나스닥100 선물 {nq_change:+.2f}%")
        if fav:
            parts.append(f"{'/'.join(fav)} 우호적")
        if unfav:
            parts.append(f"{'/'.join(unfav)} 비우호적")
        note = ", ".join(parts) if parts else "중립적 시장 분위기"
    return score, note


def _us_swing_material_score(material_memo):
    """재료 점수(0~20). 뉴스를 자동으로 읽지 못하므로 메모가 없으면 낮은 기본값을 준다."""
    if material_memo:
        return 15.0, material_memo
    return 8.0, "재료 메모 없음. 가격 흐름 중심 판단이며, 재료 확인 필요."


def _us_swing_momentum_score(turnover_ratio_pct):
    """거래/탄력 점수(0~15). 시총 대비 거래대금 기준."""
    if turnover_ratio_pct is None:
        return 0.0, "거래대금 데이터 없음"
    if turnover_ratio_pct >= 3:
        return 15.0, "거래량과 장중 탄력 양호"
    if turnover_ratio_pct >= 1.5:
        return 11.0, "거래량과 장중 탄력 보통"
    if turnover_ratio_pct >= 0.5:
        return 7.0, "거래량과 장중 탄력 약함"
    return 3.0, "거래량과 장중 탄력 매우 약함"


def _us_swing_risk_score(change_pct, high_drop_pct, has_material_memo):
    """위험 감점(최대 -10). 급등 눌림 위험 + 재료 미확인 위험 + 고점 대비 큰 밀림을 반영."""
    risk = 0.0
    notes = []
    if change_pct is not None and change_pct >= 6:
        risk -= 4
        notes.append("하루 급등 후 다음날 눌림 위험")
    elif change_pct is not None and change_pct >= 3:
        risk -= 2
        notes.append("단기 급등에 따른 되돌림 가능성")
    if not has_material_memo:
        risk -= 4
        notes.append("재료가 아직 실적 확정이 아닌 가격 흐름 중심 판단")
    if high_drop_pct is not None and high_drop_pct <= -5:
        risk -= 2
        notes.append("고점 대비 밀림 큰 편")
    risk = round(max(-10.0, risk), 1)
    note = "; ".join(notes) if notes else "특별한 위험 요인 없음"
    return risk, note


def _us_swing_tier_label(total_score):
    """총점(0~100) 기준 표시용 등급 이름. 저장용 판정(verdict)과는 별개다."""
    if total_score >= 90:
        return "매우 강한 1순위 후보"
    if total_score >= 85:
        return "강한 1순위 후보"
    if total_score >= 75:
        return "관심 후보"
    if total_score >= 60:
        return "감시"
    return "보류"


def _us_swing_verdict(total_score):
    """총점(0~100) 기준 저장용 판정(미국장 스윙 바로 저장 전용).

    75점 이상 -> 추천 후보(1순위/관심 후보 통합 저장), 60점 이상 -> 감시, 미만 -> 보류(선반영).
    등급 이름(매우 강한 1순위 후보 등)은 _us_swing_tier_label()이 표시용으로 따로 만든다.
    """
    if total_score >= 75:
        return VERDICT_NORMALIZE["관심 후보"]
    if total_score >= 60:
        return "감시"
    return VERDICT_NORMALIZE["보류"]


def compute_us_swing_breakdown(name, change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, material_memo):
    """미국장 스윙 기록 바로 저장 전용 100점 만점 점수 근거표를 계산한다.

    자동매수 신호가 아니라, 왜 그 점수/판단이 나왔는지 사람이 읽을 수 있는 근거를 만들기
    위한 것이다. 매수 확정 여부는 진입가/손절가/매수 비중/다음날 확인 조건 4가지가 이 화면에서
    입력되지 않는 한 항상 "미확정"이다.
    """
    upside_score, upside_note = _us_swing_upside_score(change_pct)
    close_score, close_note = _us_swing_close_pos_score(high_drop_pct)
    # 시장 분위기(mood_score)는 근거표에 참고용으로만 표시하며, 총점·판정 계산에는
    # 반영하지 않는다 (뉴스·공시·시황·테마는 점수·판정에 반영하지 않는다는 원칙).
    mood_score, mood_note = _us_swing_market_mood_score()
    material_score, material_note = _us_swing_material_score(material_memo)
    momentum_score, momentum_note = _us_swing_momentum_score(turnover_ratio_pct)
    risk_score, risk_note = _us_swing_risk_score(change_pct, high_drop_pct, bool(material_memo))

    total_score = round(
        upside_score + close_score + material_score + momentum_score + risk_score, 1
    )
    total_score = max(0.0, min(total_score, 100.0))
    tier_label = _us_swing_tier_label(total_score)
    verdict = _us_swing_verdict(total_score)

    strong = []
    if upside_score >= 16:
        strong.append("상승률")
    if close_score >= 16:
        strong.append("종가 위치")
    if momentum_score >= 12:
        strong.append("거래 탄력")
    if mood_score >= 12:
        strong.append("시장 분위기")
    if material_score >= 16:
        strong.append("재료")

    if total_score >= 75:
        if strong:
            priority_reason = (
                f"가격 흐름은 총점 {total_score:.0f}점입니다. {', '.join(strong)}이(가) 모두 강한 편입니다."
            )
        else:
            priority_reason = (
                f"총점 {total_score:.0f}점으로 1순위 후보 기준을 충족하지만, 개별 항목은 고르게 보통 수준입니다."
            )
    else:
        priority_reason = f"총점 {total_score:.0f}점으로 1순위 후보 기준(75점)에 못 미칩니다. 개별 항목 점수를 참고하세요."

    deduction_reason = risk_note if risk_score < 0 else "특별한 감점 요인이 없습니다."

    return {
        "name": name,
        "total_score": total_score,
        "tier_label": tier_label,
        "verdict": verdict,
        "upside_score": upside_score,
        "upside_note": upside_note,
        "close_pos_score": close_score,
        "close_pos_note": close_note,
        "mood_score": mood_score,
        "mood_note": mood_note,
        "material_score": material_score,
        "material_note": material_note,
        "momentum_score": momentum_score,
        "momentum_note": momentum_note,
        "risk_score": risk_score,
        "risk_note": risk_note,
        "priority_reason": priority_reason,
        "deduction_reason": deduction_reason,
        "buy_confirmed": "미확정",
        "buy_confirm_condition": (
            "진입가, 손절가, 매수 비중, 다음날 확인 조건이 모두 정해져야 매수 확정으로 전환됩니다. "
            "이 화면은 아직 이 값을 입력받지 않으므로 항상 '미확정'으로 표시됩니다."
        ),
    }


def _us_swing_narrative_text(row):
    """compute_us_swing_breakdown() 결과 1건을 TSLA 예시와 같은 문장형 근거로 만든다."""
    lines = [
        f"{row['name']} 총점 {row['total_score']:.0f}점 ({row['tier_label']})",
        "",
        "점수 근거:",
        f"상승률 {row['upside_score']:.0f}/20: {row['upside_note']}",
        f"종가 위치 {row['close_pos_score']:.0f}/20: {row['close_pos_note']}",
        f"시장 분위기 {row['mood_score']:.0f}/15: {row['mood_note']}",
        f"재료 {row['material_score']:.0f}/20: {row['material_note']}",
        f"거래/탄력 {row['momentum_score']:.0f}/15: {row['momentum_note']}",
        f"위험 감점 {row['risk_score']:.0f}: {row['risk_note']}",
        "",
        "1순위 근거:",
        row["priority_reason"],
        "",
        "감점 이유:",
        row["deduction_reason"],
        "",
        "매수 확정 여부:",
        row["buy_confirmed"],
        "",
        "매수 확정 조건:",
        row["buy_confirm_condition"],
    ]
    return "\n".join(lines)


def build_us_stage2_preview():
    """미국장 2단계(총점/판단/1순위 근거/감점 이유) 미리보기 전용 함수 — 한국장
    build_kr_stage2_preview()와 동일한 목적의 US 버전(2026-07-15 사용자 요청).

    US_SNAPSHOT_STOCKS(거래대금 상위 자동 선정 결과)를 순회하며 기존 "② 미국장 스윙
    계산 결과"와 똑같은 compute_us_swing_breakdown() 점수 엔진을 그대로 재사용한다 —
    새 점수 공식을 만들지 않는다. session_state에 있는 현재 입력값을 그대로 읽어서
    계산만 하며 DB에는 아무 것도 저장하지 않는다.
    """
    rows = []
    for s in US_SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)
        material_memo = (st.session_state.get(f"snap_{ticker}_material_memo", "") or "").strip()

        breakdown = compute_us_swing_breakdown(
            s["name"], change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, material_memo
        )
        breakdown["ticker"] = ticker
        breakdown["sector"] = s.get("sector", "-")
        breakdown["change_pct"] = change_pct
        breakdown["open_pos_pct"] = open_pos_pct
        breakdown["high_drop_pct"] = high_drop_pct
        breakdown["turnover_ratio_pct"] = turnover_ratio_pct
        breakdown["validation_errors"] = _validate_snapshot_price_inputs(
            s["name"], current, open_price, high, low, _get_snapshot_value(ticker, "volume"), turnover,
        )
        breakdown["needs_confirmation"] = bool(breakdown["validation_errors"])
        rows.append(breakdown)

    return {"rows": rows}


def _build_item_text_lookup():
    """(report_id, ticker, trade_mode) -> 관련 텍스트를 합친 문자열 목록. 후보 점수의 숫자
    근거를 저장된 문장에서 뽑아내기 위한 조회용이다(DB에 새 컬럼을 만들지 않는다)."""
    lookup = {}
    for report in db.list_reports():
        for item in db.get_report_items(report["id"]):
            key = (report["id"], item.get("ticker"), item.get("trade_mode"))
            text_parts = [
                item.get("event_title"),
                item.get("stock_market_basis_a"),
                item.get("stock_market_basis_b"),
                item.get("stock_market_basis_c"),
                item.get("betting_basis_ga"),
                item.get("betting_basis_na"),
                item.get("betting_basis_da"),
                item.get("stock_market_judgment"),
                item.get("betting_market_judgment"),
            ]
            lookup.setdefault(key, []).append(" ".join(p for p in text_parts if p))
    return lookup


def _build_item_judgment_lookup():
    """(report_id, ticker, trade_mode) -> report_item 전체 dict. 결과 확인의 '자세히 보기'에서
    저장 당시 점수/근거/매수 확정 정보를 다시 보여주기 위한 조회용이다."""
    lookup = {}
    for report in db.list_reports():
        for item in db.get_report_items(report["id"]):
            key = (report["id"], item.get("ticker"), item.get("trade_mode"))
            lookup[key] = item
    return lookup


def _rank_label(rank):
    """순위 숫자를 표시용 문구로 바꾼다. 1위="1순위 후보", 2위="2순위", 3위="3순위", 그 외="N위"."""
    if rank == 1:
        return "1순위 후보"
    if rank == 2:
        return "2순위"
    if rank == 3:
        return "3순위"
    return f"{rank}위"


def _rank_scores(pairs):
    """[(key, score), ...] 목록에서 score가 있고(>0) 큰 순으로 순위를 매긴다.

    score가 없거나(None) 0 이하이면 순위 계산에서 제외하고 "미평가"로 표시한다.
    자동매수 신호가 아니라 화면 표시용 상대 순위이며, DB에는 저장하지 않는다.
    반환: {key: 순위 라벨}
    """
    valid = [(k, s) for k, s in pairs if (s or 0) > 0]
    valid.sort(key=lambda pair: -pair[1])
    labels = {}
    for idx, (k, _) in enumerate(valid, start=1):
        labels[k] = _rank_label(idx)
    for k, _ in pairs:
        if k not in labels:
            labels[k] = "미평가"
    return labels


def _item_combined_text(item):
    """report_item의 자유 서술 텍스트 필드를 전부 합친 문자열. 자동 점수 계산에서
    가점/감점 키워드를 찾는 용도로만 쓴다(저장/파싱 로직과는 무관)."""
    parts = [
        item.get("event_title"),
        item.get("stock_market_basis_a"),
        item.get("stock_market_basis_b"),
        item.get("stock_market_basis_c"),
        item.get("betting_basis_ga"),
        item.get("betting_basis_na"),
        item.get("betting_basis_da"),
        item.get("stock_market_judgment"),
        item.get("betting_market_judgment"),
    ]
    return " ".join(p for p in parts if p)


# 자동 점수 계산(1차 규칙 기반) 전용 상수. 실시간 시세 조회가 아니라, 이미 저장된
# 문장/판정/신호 분류/매매유형/시장 구분만으로 만드는 참고용 점수다.
_AUTO_SCORE_VERDICT_BASE = {
    "추천 후보": 70,  # 관심 후보
    "감시": 60,
    "확인 필요": 50,  # 기타/알 수 없음 취급
    "보류(선반영)": 45,
    "제외": 25,
}

_AUTO_SCORE_GAIN_KEYWORDS = {
    "종가 강함": 4,
    "종가 유지": 3,
    "섹터 강세": 4,
    "동반 강세": 3,
    "프로그램 매수": 5,
    "외국인 선물 매수": 5,
    "상대강도": 4,
    "주도주": 5,
    "대장주": 5,
}

_AUTO_SCORE_PENALTY_KEYWORDS = {
    "종가 약함": 4,
    "긴 윗꼬리": 4,
    "프로그램 매도": 5,
    "외국인 선물 매도": 5,
    "나스닥 선물 약세": 4,
    "보류": 3,
    "늦은 신호": 5,
    "추격 주의": 4,
    "확인 필요": 3,
}

# 단타/스윙 보정: 일반 목록과 겹치는 키워드는 가중치만 +-1 더하고, 스윙 전용 개념
# ("일봉 추세", "재료 지속성", "다음날 확인 필요", "거래대금은 큰데 주가 못 버팀")은
# 일반 목록에 없으므로 별도 점수를 준다. 시가 위치/고점 대비 밀림/거래대금은 아래
# "신호 카테고리"에서 텍스트·수치 신호를 하나로 합쳐 처리하므로 여기서는 빠진다
# (중복 가산/감점 방지).
_DANTA_EXTRA_GAIN_KEYWORDS = ["섹터 강세"]
_DANTA_EXTRA_PENALTY_KEYWORDS = ["추격 주의", "늦은 신호"]
_SWING_EXTRA_GAIN_KEYWORDS = ["종가 강함", "종가 유지"]
_SWING_EXTRA_PENALTY_KEYWORDS = ["긴 윗꼬리", "종가 약함"]
_SWING_ONLY_GAIN_KEYWORDS = {"일봉 추세": 4, "재료 지속성": 4}
_SWING_ONLY_PENALTY_KEYWORDS = {"다음날 확인 필요": 3, "거래대금은 큰데 주가 못 버팀": 5}

# 신호 카테고리(시가 위치/고점 대비 밀림/거래대금): 텍스트 키워드와 수치 계산값이 같은
# 의미를 가리키면 카테고리당 신호를 한 번만 반영한다. 수치 계산값이 있으면 그 값을
# 우선 쓰고(더 정확한 근거), 없으면 텍스트 키워드로 대체한다.
_PRICE_POSITION_POSITIVE_KEYWORDS = ["시가 위"]
_PRICE_POSITION_NEGATIVE_KEYWORDS = ["시가 아래"]
_HIGH_DROP_POSITIVE_KEYWORDS = ["고점 대비 밀림 적음"]
_HIGH_DROP_NEGATIVE_KEYWORDS = ["고점 대비 밀림"]
_LIQUIDITY_POSITIVE_KEYWORDS = ["거래대금 증가", "거래대금 유지", "거래대금 양호"]
_LIQUIDITY_NEGATIVE_KEYWORDS = ["거래대금 부족", "거래대금 감소"]

# 매매유형별 카테고리 점수(양수 가점, 음수 감점 크기). 카테고리당 이 점수를 한 번만
# 적용한다 — 0이면 그 매매유형에서는 해당 방향 신호를 점수에 반영하지 않는다(예: 스윙은
# 시가 부정/거래대금 부정에 대한 감점 규칙이 없음).
_CATEGORY_POINTS_BY_MODE = {
    "단타": {"price_position": (5, 6), "high_drop": (4, 6), "liquidity": (4, 4)},
    "스윙": {"price_position": (3, 0), "high_drop": (3, 5), "liquidity": (3, 0)},
    "__default__": {"price_position": (3, 4), "high_drop": (3, 5), "liquidity": (4, 4)},
}


def _find_keyword(text, keywords):
    for kw in keywords:
        if kw in text:
            return kw
    return None


def _resolve_signal_category(
    text, positive_keywords, negative_keywords, numeric_value, positive_fn, negative_fn, positive_phrase, negative_phrase
):
    """카테고리 하나(시가 위치/고점 대비 밀림/거래대금)의 텍스트+수치 신호를 하나로 합친다.
    수치 계산값이 있으면 그 값을 우선 쓰고(더 정확), 없으면 텍스트 키워드로 대체한다
    (같은 의미의 신호가 중복으로 가산/감점되지 않도록).
    반환: ("positive"|"negative"|None, 표시용 문구)
    """
    if numeric_value is not None:
        if positive_fn(numeric_value):
            return "positive", positive_phrase(numeric_value)
        if negative_fn(numeric_value):
            return "negative", negative_phrase(numeric_value)
        return None, None
    kw = _find_keyword(text, positive_keywords)
    if kw:
        return "positive", kw
    kw = _find_keyword(text, negative_keywords)
    if kw:
        return "negative", kw
    return None, None


def _auto_buy_confirm_condition(trade_mode, market, turnover_ratio_pct=None):
    """매수 확정 조건 자동 문구. 매매유형(단타/스윙)을 먼저 보고, 공통/그 외면 시장(KR/US)
    기준 문구를 쓴다.

    turnover_ratio_pct가 있으면 "거래대금 유지" 뒤 괄호에 실제 시총 대비 거래대금
    수치를 채운다(2026-07-15 사용자 요청: 조건 문구가 항상 똑같은 안내문이라 실제
    자료를 찾아 넣어달라는 지적). 5% 기준은 기존 "② 오늘 주가 계산 결과" 표의
    "확인 필요" 판정과 동일하다. 프로그램/외국인 수급은 아직 데이터 소스가 없어
    "자료 미연동"으로 명시한다(임의로 값을 지어내지 않는다).
    """
    if turnover_ratio_pct is None:
        _turnover_note = ""
    elif turnover_ratio_pct >= 5:
        _turnover_note = f"({turnover_ratio_pct:.2f}%, 확인 필요)"
    else:
        _turnover_note = f"({turnover_ratio_pct:.2f}%, 기준 이내)"
    if trade_mode == "단타":
        return f"시가 위 유지 + 고점 대비 밀림 제한 + 거래대금 유지{_turnover_note} + 프로그램/외국인 수급(자료 미연동)"
    if trade_mode == "스윙":
        return f"종가 강세 유지 + 거래대금 유지{_turnover_note} + 다음날 흐름 재확인 필요"
    if market == "US":
        return "본장 거래량 + 섹터 동반 강도 + 프리/애프터 변동 확인 필요"
    return "장중 수급 + 섹터 강도 + 종가 위치 확인 필요"


def _auto_fill_item_display(item):
    """score/score_reason/penalty_reason/buy_confirmed/buy_confirm_condition 중 비어 있는
    값만 문장·판정·신호 분류·매매유형·시장 구분 기반 1차 규칙으로 자동 채워 화면 표시용으로
    반환한다. 실시간 가격 조회가 아니며, DB에는 다시 쓰지 않는다(표시 시점 계산).
    사용자가 이미 입력한 값은 그대로 쓰고 절대 덮어쓰지 않는다.

    반환: {"score", "score_is_auto", "score_reason", "penalty_reason",
           "buy_confirmed", "buy_confirm_condition"}
    """
    verdict = item.get("verdict")
    trade_mode = item.get("trade_mode") or "공통"
    market = item.get("market") or "KR"
    signal_type = item.get("signal_type")
    buy_confirmed = item.get("buy_confirmed") or "미확정"
    text = _item_combined_text(item)

    gains = []
    penalties = []
    for kw, pts in _AUTO_SCORE_GAIN_KEYWORDS.items():
        if kw in text:
            gains.append((kw, pts))
    for kw, pts in _AUTO_SCORE_PENALTY_KEYWORDS.items():
        if kw in text:
            penalties.append((kw, pts))
    if signal_type == "재확인 신호":
        gains.append(("재확인 신호", 3))
    if verdict == "추천 후보":
        gains.append(("관심 후보", 5))
    if trade_mode == "스윙":
        for kw, pts in _SWING_ONLY_GAIN_KEYWORDS.items():
            if kw in text:
                gains.append((kw, pts))
        for kw, pts in _SWING_ONLY_PENALTY_KEYWORDS.items():
            if kw in text:
                penalties.append((kw, pts))

    # 저장된 문장에 이미 담긴 전일대비/시가대비/고점대비/시총대비 거래대금 수치를 뽑아
    # price_vs_open_pct/drop_from_high_pct/trading_value_to_market_cap_pct 보조 신호로 쓴다.
    # drop_from_high_pct는 "밀린 정도(양수)"이므로 기존 high_drop_pct(음수 관례)의 부호를 뒤집는다.
    basis = extract_score_basis_from_text(text)
    price_vs_open_pct = basis.get("open_pos_pct")
    drop_from_high_pct = -basis["high_drop_pct"] if basis.get("high_drop_pct") is not None else None
    trading_value_to_market_cap_pct = basis.get("turnover_ratio_pct")

    # 시가 위치/고점 대비 밀림/거래대금: 텍스트 키워드와 수치 계산값이 같은 의미면
    # 카테고리당 신호를 한 번만 반영한다(중복 가산/감점 방지). 수치 계산값이 있으면
    # 그 값을 우선 쓴다(문구도 수치 기반이 우선).
    category_points = _CATEGORY_POINTS_BY_MODE.get(trade_mode, _CATEGORY_POINTS_BY_MODE["__default__"])
    high_drop_pos_threshold = 2 if trade_mode == "단타" else 3
    high_drop_neg_threshold = 5 if trade_mode == "단타" else 7
    liquidity_pos_threshold = 0.3 if trade_mode == "단타" else 0.2

    price_direction, price_phrase = _resolve_signal_category(
        text,
        _PRICE_POSITION_POSITIVE_KEYWORDS,
        _PRICE_POSITION_NEGATIVE_KEYWORDS,
        price_vs_open_pct,
        lambda v: v > 0,
        lambda v: v < 0,
        lambda v: f"시가 대비 {v:+.2f}%로 시가 위 유지",
        lambda v: f"시가 대비 {v:+.2f}%로 시가 아래",
    )
    high_drop_direction, high_drop_phrase = _resolve_signal_category(
        text,
        _HIGH_DROP_POSITIVE_KEYWORDS,
        _HIGH_DROP_NEGATIVE_KEYWORDS,
        drop_from_high_pct,
        lambda v, t=high_drop_pos_threshold: v <= t,
        lambda v, t=high_drop_neg_threshold: v >= t,
        lambda v: f"고점 대비 밀림 {v:.2f}%로 장중 생존력 양호",
        lambda v: f"고점 대비 {v:.2f}% 밀림",
    )
    liquidity_direction, liquidity_phrase = _resolve_signal_category(
        text,
        _LIQUIDITY_POSITIVE_KEYWORDS,
        _LIQUIDITY_NEGATIVE_KEYWORDS,
        trading_value_to_market_cap_pct,
        lambda v, t=liquidity_pos_threshold: v >= t,
        lambda v: v < 0.1,
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 양호",
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 부족",
    )

    pos_pts, neg_pts = category_points["price_position"]
    if price_direction == "positive" and pos_pts:
        gains.append((price_phrase, pos_pts))
    elif price_direction == "negative" and neg_pts:
        penalties.append((price_phrase, neg_pts))

    pos_pts, neg_pts = category_points["high_drop"]
    if high_drop_direction == "positive" and pos_pts:
        gains.append((high_drop_phrase, pos_pts))
    elif high_drop_direction == "negative" and neg_pts:
        penalties.append((high_drop_phrase, neg_pts))

    pos_pts, neg_pts = category_points["liquidity"]
    if liquidity_direction == "positive" and pos_pts:
        gains.append((liquidity_phrase, pos_pts))
    elif liquidity_direction == "negative" and neg_pts:
        penalties.append((liquidity_phrase, neg_pts))

    stored_score = item.get("score")
    score_is_auto = stored_score is None  # 저장된 점수가 없을 때만 자동 계산(0점도 유효한 저장값)
    if score_is_auto:
        score = float(_AUTO_SCORE_VERDICT_BASE.get(verdict, 50))
        for _, pts in gains:
            score += pts
        for _, pts in penalties:
            score -= pts
        if trade_mode == "단타":
            for kw in _DANTA_EXTRA_GAIN_KEYWORDS:
                if kw in text:
                    score += 1
            for kw in _DANTA_EXTRA_PENALTY_KEYWORDS:
                if kw in text:
                    score -= 1
        elif trade_mode == "스윙":
            for kw in _SWING_EXTRA_GAIN_KEYWORDS:
                if kw in text:
                    score += 1
            for kw in _SWING_EXTRA_PENALTY_KEYWORDS:
                if kw in text:
                    score -= 1
        if buy_confirmed == "확정":
            score = max(score, 85)
        if verdict == "보류(선반영)":
            score = min(score, 60)
        if verdict == "제외":
            score = min(score, 35)
        score = int(round(max(0.0, min(score, 100.0))))
    else:
        score = stored_score

    score_reason = item.get("score_reason") or (
        " + ".join(kw for kw, _ in gains) if gains else "특이 사항 없음 (1차 규칙 기반 자동 계산)"
    )
    penalty_reason = item.get("penalty_reason") or (
        ", ".join(kw for kw, _ in penalties) if penalties else "특별한 감점 요인 없음 (1차 규칙 기반 자동 계산)"
    )
    buy_confirm_condition = item.get("buy_confirm_condition") or _auto_buy_confirm_condition(trade_mode, market)

    return {
        "score": score,
        "score_is_auto": score_is_auto,
        "score_reason": score_reason,
        "penalty_reason": penalty_reason,
        "buy_confirmed": buy_confirmed,
        "buy_confirm_condition": buy_confirm_condition,
    }


def _compute_score_rank_labels(items):
    """report_item dict 목록(같은 report일 수도, 여러 report가 섞여 있을 수도 있음)에서
    (report_id, market, trade_mode) 그룹별로 score 기준 순위를 매겨 item id -> 순위 라벨을 반환한다.

    한국장/미국장, 단타/스윙을 서로 섞지 않기 위해 report_id·market·trade_mode가 모두 같은
    항목끼리만 순위를 비교한다. score가 비어 있으면 _auto_fill_item_display()의 1차 규칙
    자동 계산값을 순위 계산에 쓰므로, 오래된 report도 순위가 매겨질 수 있다.
    """
    groups = {}
    for item in items:
        key = (item.get("report_id"), item.get("market") or "OTHER", item.get("trade_mode") or "공통")
        groups.setdefault(key, []).append(item)

    labels = {}
    for group_items in groups.values():
        pairs = [(it["id"], _auto_fill_item_display(it)["score"]) for it in group_items]
        labels.update(_rank_scores(pairs))
    return labels


VERDICT_BADGE_COLOR = {
    "추천 후보": "green",
    "감시": "yellow",
    "확인 필요": "orange",
    "보류(선반영)": "gray",
    "제외": "red",
}
SIGNAL_TYPE_DISPLAY = {
    "선행 신호": "장전 신호",
    "재확인 신호": "재확인",
    "늦은 신호": "늦게 발견",
    "가짜 신호": "실패 가능",
    "미분류": "미정",
}
TRADE_MODE_BADGE_COLOR = {
    "단타": "blue",
    "스윙": "violet",
    "공통": "gray",
}


def _display_verdict_name(verdict):
    """판정 내부값을 화면 표시용 쉬운 이름으로 바꾼다 (저장값은 불변)."""
    return VERDICT_DISPLAY.get(verdict, verdict)


def _display_signal_type(signal_type):
    """신호 분류 내부값을 화면 표시용 쉬운 이름으로 바꾼다 (저장값은 불변)."""
    return SIGNAL_TYPE_DISPLAY.get(signal_type, signal_type)


def _verdict_badge(verdict):
    color = VERDICT_BADGE_COLOR.get(verdict, "gray")
    return f":{color}-badge[{_display_verdict_name(verdict)}]"


def _trade_mode_badge(trade_mode):
    color = TRADE_MODE_BADGE_COLOR.get(trade_mode, "gray")
    return f":{color}-badge[{trade_mode or '공통'}]"


TRADE_MODE_ORDER = ["단타", "스윙", "공통"]
TRADE_MODE_HEADING = {"단타": "단타 관점", "스윙": "스윙 관점", "공통": "공통"}
TRADE_MODE_EMOJI = {"단타": "🔵", "스윙": "🟣", "공통": "⚪"}


def _group_items_by_trade_mode_and_verdict(report_id):
    """report_items를 매매유형(단타→스윙→공통) → 판정(VERDICT_ORDER) 순서로 2단 그룹화한다.

    같은 매매유형 + 같은 판정 안에서는 db.get_report_items()가 반환하는 입력(저장) 순서를
    그대로 유지한다. 같은 종목이 단타/스윙 둘 다로 저장돼 있으면 각 그룹에 각각 나타난다
    (합치지 않음).
    """
    grouped = {tm: {v: [] for v in VERDICT_ORDER} for tm in TRADE_MODE_ORDER}
    for item in db.get_report_items(report_id):
        tm = item.get("trade_mode") or "공통"
        if tm not in TRADE_MODE_ORDER:
            tm = "공통"
        v = item.get("verdict")
        grouped[tm].setdefault(v, []).append(item)
    return grouped


def extract_priority_basis(raw_briefing):
    """상세 메모(raw_briefing) 안에서 "[우선순위 근거]" 구역만 표시용으로 추출한다.

    저장/파싱 로직(parse_quick_text, save_report)과는 무관한 읽기 전용 표시 보조 함수다.
    DB에 별도 컬럼을 만들지 않고, 이미 저장된 raw_briefing 텍스트에서 그때그때 뽑아 보여준다.
    """
    if not raw_briefing:
        return None
    sections = {}
    current = None
    buffer = []
    for line in raw_briefing.splitlines():
        m = _SECTION_HEADER_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = m.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections.get("우선순위 근거") or None


def _render_trade_mode_section(tm, grouped, rank_labels=None):
    """단타/스윙/공통 중 하나(tm)의 판정별 그룹을 "현재 컨테이너 안에" 그려 넣는다.

    호출부에서 `with column:` 등으로 컨테이너를 이미 지정한 상태에서 호출한다.
    rank_labels가 있으면(같은 report·시장·매매유형 안에서 score 기준으로 계산한 순위) 각 항목
    제목/카드 상단에 순위를 표시하고, 같은 판정 그룹 안에서는 score 높은 순으로 정렬한다.
    score가 없는 항목("미평가")은 그룹 맨 뒤로 간다. rank_labels가 없으면(예: 계산 실패) 기존
    순서를 그대로 쓴다 — 오래된 report에도 이 화면이 오류 없이 동작해야 한다.
    """
    rank_labels = rank_labels or {}
    st.markdown(f"## {TRADE_MODE_EMOJI.get(tm, '')} {_trade_mode_badge(tm)} {TRADE_MODE_HEADING[tm]}")
    for verdict in VERDICT_ORDER:
        bucket = grouped[tm].get(verdict, [])
        bucket = sorted(bucket, key=lambda it: -_auto_fill_item_display(it)["score"])
        st.markdown(f"#### {_verdict_badge(verdict)} ({len(bucket)}건)")
        if not bucket:
            st.caption("해당 없음")
            continue
        for item in bucket:
            label = item.get("stock_name") or item.get("ticker") or item.get("event_title") or "(제목 없음)"
            trade_mode = item.get("trade_mode") or "공통"
            rank_label = rank_labels.get(item.get("id"), "미평가")
            auto_info = _auto_fill_item_display(item)
            auto_tag = " (자동계산)" if auto_info["score_is_auto"] else ""
            score_text = f"{auto_info['score']:.0f}점{auto_tag}"
            card_title = f"{_trade_mode_badge(trade_mode)} [{rank_label}] {label}"
            if item.get("event_title"):
                card_title += f" - {item['event_title']}"
            card_title += f" ({auto_info['score']:.0f}점){auto_tag}"
            top_reason = item.get("top_candidate_reason") or auto_info["score_reason"]
            with st.container():
                st.markdown(f"**{card_title}**")
                st.write(f"점수: {score_text}")
                st.write(f"점수 근거: {auto_info['score_reason']}")
                st.write(f"1순위 후보 근거: {top_reason}")
                st.write(f"감점 이유: {auto_info['penalty_reason']}")
                st.write(f"매수 확정 여부: {auto_info['buy_confirmed']}")
                with st.expander("전체 근거", expanded=False):
                    st.markdown(
                        f"**[{trade_mode} {rank_label}] {label} / {score_text} / "
                        f"{auto_info['buy_confirmed']}**"
                    )
                    st.write(f"매매유형: {trade_mode}")
                    st.write(f"판단: {_display_verdict_name(item.get('verdict'))}")
                    st.write(f"종목코드: {item.get('ticker') or '-'}")
                    st.write(f"시장: {item.get('market') or '-'}")
                    st.write(f"신호 종류: {_display_signal_type(item.get('signal_type') or '-')}")
                    st.write(f"주식시장 판단: {item.get('stock_market_judgment') or '-'}")
                    st.write(f"베팅시장 판단: {item.get('betting_market_judgment') or '-'}")
                    st.write(f"점수: {score_text}")
                    st.write(f"점수 근거: {auto_info['score_reason']}")
                    st.write(f"1순위 후보 근거: {top_reason}")
                    st.write(f"감점 이유: {auto_info['penalty_reason']}")
                    st.write(f"매수 확정 여부: {auto_info['buy_confirmed']}")
                    st.write(f"매수 확정 조건: {auto_info['buy_confirm_condition']}")


def render_report_detail(report, show_raw_briefing=False):
    """report 1건의 한줄 요약 + report_items(판정 5종별 그룹, 최신 카드형)를 표시한다."""
    st.caption(
        f"저장 시각: {report['saved_at']}  |  시장: {report['market_scope']}  |  "
        f"장 구분: {report['timing_class']}  |  판단 시점: {report.get('briefing_stage') or '-'}"
    )
    st.markdown("**오늘 요약**")
    st.write(report["day_conclusion"])

    priority_basis = extract_priority_basis(report.get("raw_briefing"))
    if priority_basis:
        st.markdown("**우선순위 근거**")
        st.write(priority_basis)

    if show_raw_briefing:
        with st.expander("판단 근거 보기"):
            st.write(report["raw_briefing"])

    items = db.get_report_items(report["id"])

    if not items:
        st.info("종목별 기록은 없습니다. 오늘 요약만 저장되었습니다.")
        return

    st.markdown("---")
    st.markdown("**종목별 기록**")
    st.info("1순위 후보는 매수 확정이 아니라, 현재 기록 기준에서 가장 먼저 확인할 후보입니다.")
    st.caption(
        "정렬 기준: 단타와 스윙을 먼저 나누고, 각 관점 안에서 1순위 후보 → 관찰 후보 → "
        "재확인 → 보류 → 제외 순서로 표시합니다. 같은 그룹 안에서는 위에 있을수록 우선순위가 "
        "높으며, 입력 순서를 유지합니다."
    )

    grouped = _group_items_by_trade_mode_and_verdict(report["id"])
    rank_labels = _compute_score_rank_labels(items)

    # 좌우 2단: 왼쪽=스윙 관점, 오른쪽=단타 관점 (넓은 화면 기준. 좁은 화면에서는
    # Streamlit이 자동으로 세로 배치한다). 공통은 두 컬럼 아래에 별도 영역으로 표시.
    col_swing, col_danta = st.columns(2, gap="large")
    with col_swing:
        _render_trade_mode_section("스윙", grouped, rank_labels)
    with col_danta:
        _render_trade_mode_section("단타", grouped, rank_labels)

    common_count = sum(len(items) for items in grouped["공통"].values())
    if common_count > 0:
        st.markdown("---")
        _render_trade_mode_section("공통", grouped, rank_labels)


def _classify_actual_trade_status(saved_item):
    """저장된 actual_action/청산 필드만으로 ③ 화면 진행 상태를 분류한다."""
    action = db.normalize_actual_action(saved_item.get("actual_action"))
    if action == "미기록":
        return "행동 미입력"
    if action == "보류":
        return "보류"
    if action == "제외":
        return "제외"
    if (
        action == "매수"
        and saved_item.get("actual_exit_price") is not None
        and saved_item.get("actual_exit_date")
    ):
        return "청산 완료"
    if action == "매수":
        return "보유 중"
    return "행동 미입력"


def _today_progress_snapshot(reports, items_by_report, today=None):
    """공통 상단 상태 스트립용 읽기 전용 집계. ticker가 아닌 report_items 행을 센다."""
    today_text = (today or datetime.now()).strftime("%Y-%m-%d")
    today_reports = [r for r in reports if str(r.get("saved_at") or "").startswith(today_text)]
    latest_by_market = {}
    for report in sorted(today_reports, key=lambda r: (r.get("saved_at") or "", r.get("id") or 0), reverse=True):
        for market in ("KR", "US"):
            if market not in latest_by_market and market in str(report.get("market_scope") or ""):
                latest_by_market[market] = report
    today_items = []
    for report in latest_by_market.values():
        today_items.extend(items_by_report.get(report.get("id"), []))
    all_items = [item for items in items_by_report.values() for item in items]
    review_pending = sum(
        1 for item in all_items
        if _classify_actual_trade_status(item) in ("청산 완료", "보류", "제외")
        and item.get("review_done") not in (1, True)
    )
    return {
        "kr_saved": "KR" in latest_by_market,
        "us_saved": "US" in latest_by_market,
        "today_action_missing": sum(
            1 for item in today_items if _classify_actual_trade_status(item) == "행동 미입력"
        ),
        "holding": sum(1 for item in all_items if _classify_actual_trade_status(item) == "보유 중"),
        "review_pending": review_pending,
    }


def _render_today_progress_status_strip():
    reports = db.list_reports()
    items_by_report = {report["id"]: db.get_report_items(report["id"]) for report in reports}
    status = _today_progress_snapshot(reports, items_by_report)
    columns = st.columns(5)
    columns[0].metric("KR 저장", "완료" if status["kr_saved"] else "미완료")
    columns[1].metric("US 저장", "완료" if status["us_saved"] else "미완료")
    columns[2].metric("오늘 행동 미입력", f"{status['today_action_missing']}건")
    columns[3].metric("보유 중", f"{status['holding']}건")
    columns[4].metric("복기 대기", f"{status['review_pending']}건")

tab_kr, tab_us, tab_action, tab_review, tab_saved, tab_aux = st.tabs(
    [
        "① 한국장 판단", "② 미국장 판단", "③ 행동·청산", "④ 복기·통계", "⑤ 기록 조회", "⑥ 보조",
    ]
)

# 탭을 바꿔도 브라우저 스크롤 위치가 그대로 남아, 미국장 판단을 눌러도 화면 중간부터
# 보이던 문제(2026-07-15 사용자 지적) — 탭 버튼 클릭 시 맨 위로 스크롤한다.
# st.markdown의 <script>는 실행되지 않으므로 components.html(iframe)로 부모 문서에
# 리스너를 단다. 새 요소가 생겨도 리스너가 유지되도록 MutationObserver로 재바인딩한다.
import streamlit.components.v1 as _st_components

_st_components.html(
    """<script>
    (function () {
      const doc = window.parent.document;
      function scrollAllTops() {
        [
          doc.querySelector('[data-testid="stMain"]'),
          doc.querySelector('section.main'),
          doc.querySelector('[data-testid="stAppViewContainer"]'),
          doc.scrollingElement,
        ].forEach(function (el) { if (el && el.scrollTo) el.scrollTo({ top: 0 }); });
        window.parent.scrollTo({ top: 0 });
      }
      function bind() {
        doc.querySelectorAll('[data-testid="stTabs"] [role="tab"]').forEach(function (btn) {
          if (btn.dataset.jarvisScrollBound) return;
          btn.dataset.jarvisScrollBound = "1";
          btn.addEventListener("click", function () {
            requestAnimationFrame(function () { requestAnimationFrame(scrollAllTops); });
          });
        });
      }
      bind();
      new MutationObserver(bind).observe(doc.body, { subtree: true, childList: true });
    })();
    </script>""",
    height=0,
)

DEFAULT_SNAPSHOT_STOCKS = [
    {"name": "삼성전자", "ticker": "005930.KS", "sector": "반도체"},
    {"name": "SK하이닉스", "ticker": "000660.KS", "sector": "반도체"},
    {"name": "현대차", "ticker": "005380.KS", "sector": "자동차"},
    {"name": "기아", "ticker": "000270.KS", "sector": "자동차"},
    {"name": "현대모비스", "ticker": "012330.KS", "sector": "자동차부품"},
    {"name": "한화오션", "ticker": "042660.KS", "sector": "조선"},
    {"name": "한화에어로스페이스", "ticker": "012450.KS", "sector": "방산"},
]
# 2026-07-13(사용자 명시 요청): 하드코딩 7종목 고정 대신, "오늘 거래대금 상위 종목 다시
# 선정" 버튼을 누르면 session_state["dynamic_snapshot_stocks"]가 채워져 이 목록을
# 대체한다. 버튼을 아직 안 눌렀으면(세션 시작 직후 등) DEFAULT_SNAPSHOT_STOCKS로
# 안전하게 대체(fallback)한다. SNAPSHOT_STOCKS를 참조하는 기존 코드는 전부 그대로 두고
# (이 이름 자체가 매 스크립트 실행마다 새로 계산되는 전역 변수라) 손댈 필요 없다.
SNAPSHOT_STOCKS = st.session_state.get("dynamic_snapshot_stocks") or DEFAULT_SNAPSHOT_STOCKS
SNAPSHOT_FIELDS = ["current", "prev_close", "open", "high", "low", "turnover", "market_cap", "volume"]
SNAPSHOT_NAME_TO_TICKER = {s["name"]: s["ticker"] for s in SNAPSHOT_STOCKS}


def _kr_dart_stock_code(ticker):
    """Return only a valid six-digit Korean stock code."""
    code = str(ticker or "").strip().upper().removesuffix(".KS").removesuffix(".KQ")
    return code if re.fullmatch(r"\d{6}", code) else None


def _format_dart_date(value):
    text = str(value or "")
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if re.fullmatch(r"\d{8}", text) else (text or "-")


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_kr_dart_corp_code_map(api_key):
    return disclosure_data.fetch_dart_corp_code_map(api_key)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_kr_chart_history(ticker):
    """종목별 상세 입력 카드에서 쓰는 최근 3개월 일봉 차트 데이터(종가). 참고용, 점수/저장 무관."""
    end = datetime.now()
    start = end - timedelta(days=95)
    return price_data.get_ohlc_history_for_chart(
        ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    )


def _fetch_kr_dart_disclosures(api_key, stocks, today=None):
    """Fetch read-only DART references for the Korean snapshot stocks."""
    if not api_key:
        return {"checked_at": None, "rows": [], "summary": {"normal": 0, "empty": 0, "failed": 0, "missing": 0}, "message": "OpenDART 인증키 설정이 필요합니다"}
    today = today or datetime.now().date()
    start_date = (today - timedelta(days=2)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    corp_result = _cached_kr_dart_corp_code_map(api_key)
    corp_map = corp_result.get("data") if corp_result.get("status") == "정상" else {}
    rows = []
    summary = {"normal": 0, "empty": 0, "failed": 0, "missing": 0}
    for stock in stocks:
        code = _kr_dart_stock_code(stock.get("ticker"))
        base = {"name": stock.get("name") or "-", "ticker": stock.get("ticker") or "-", "stock_code": code}
        if not code:
            rows.append({**base, "status": "종목코드 없음", "data": []})
            summary["missing"] += 1
            continue
        corp = corp_map.get(code)
        if not corp:
            rows.append({**base, "status": "corp_code 없음", "data": []})
            summary["missing"] += 1
            continue
        try:
            result = disclosure_data.fetch_recent_dart_disclosures(api_key, corp["corp_code"], start_date, end_date)
        except Exception:
            result = {"status": "조회 오류", "data": []}
        status = result.get("status", "조회 오류")
        if status == "정상":
            summary["normal"] += 1
        elif status == "데이터 없음":
            summary["empty"] += 1
        else:
            summary["failed"] += 1
        rows.append({**base, "status": status, "data": result.get("data") or [], "message": result.get("message", "")})
    return {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "rows": rows, "summary": summary, "start_date": start_date, "end_date": end_date}


@_reference_panel_guard(
    "KR OpenDART 공시",
    (("disclosure_data", "fetch_dart_corp_code_map"), ("disclosure_data", "fetch_recent_dart_disclosures")),
    "현재 공시 조회에 실패했습니다. 잠시 후 다시 시도하세요.",
)
def _render_kr_dart_disclosure_panel():
    st.markdown("### 📢 한국장 최근 공시 자동 확인")
    st.caption("OpenDART 참고 조회 · 저장 안 됨 · 점수 미반영")
    api_key = st.secrets.get("DART_API_KEY")
    if not api_key:
        st.info("OpenDART 인증키 설정이 필요합니다")
    if st.button("최근 공시 자동 확인", key="kr_dart_check_button"):
        result = _fetch_kr_dart_disclosures(api_key, SNAPSHOT_STOCKS)
        st.session_state["kr_dart_disclosure_results"] = result
        st.session_state["kr_dart_checked_at"] = result.get("checked_at")
    result = st.session_state.get("kr_dart_disclosure_results")
    if not result:
        return
    summary = result.get("summary", {})
    st.caption(
        f"조회 시각: {st.session_state.get('kr_dart_checked_at') or '-'} · "
        f"조회 종목 수: {len(result.get('rows', []))} · 정상 {summary.get('normal', 0)} · "
        f"공시 없음 {summary.get('empty', 0)} · 실패 {summary.get('failed', 0)} · 코드 없음 {summary.get('missing', 0)}"
    )
    for row in result.get("rows", []):
        if row.get("data"):
            header_status = f"공시 {len(row['data'])}건"
        elif row.get("status") == "데이터 없음":
            header_status = "최근 3일 공시 없음"
        else:
            header_status = row.get("status") or "조회 오류"
        with st.expander(f"{row['name']} ({row['ticker']}) · {header_status}", expanded=False):
            if row["status"] in ("종목코드 없음", "corp_code 없음"):
                st.info(row["status"])
            elif row["status"] == "데이터 없음":
                st.info("최근 3일 공시 없음")
            elif row["status"] != "정상":
                st.warning(row.get("message") or row["status"])
            for item_index, item in enumerate(row.get("data", [])):
                if item_index:
                    st.markdown("---")
                st.write(f"접수일자: {_format_dart_date(item.get('rcept_dt'))}")
                st.write(f"보고서명: {item.get('report_nm') or '-'}")
                st.write(f"제출인: {item.get('flr_nm') or '-'}")
                rcept_no = item.get("rcept_no")
                if rcept_no:
                    st.markdown(f"[DART 원문 보기](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no})")


def _recent_naver_news_items(items, today=None):
    today = today or datetime.now().date()
    first_day = today - timedelta(days=2)
    recent = []
    for item in items or []:
        try:
            item_date = datetime.fromisoformat(str(item.get("pub_date", "")).replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            continue
        if first_day <= item_date <= today:
            recent.append(item)
        if len(recent) == 5:
            break
    return recent


def _fetch_market_naver_news(client_id, client_secret, stocks, today=None):
    today = today or datetime.now().date()
    rows = []
    summary = {"normal": 0, "empty": 0, "failed": 0}
    for stock in stocks:
        try:
            result = news_data.fetch_naver_news(client_id, client_secret, stock.get("name", ""), display=10, sort="date")
            items = _recent_naver_news_items(result.get("data", []), today=today)
            status = result.get("status", "응답 오류")
            if status == "정상" and items:
                summary["normal"] += 1
            elif status in ("정상", "데이터 없음"):
                status = "데이터 없음"
                summary["empty"] += 1
            else:
                summary["failed"] += 1
            rows.append({"name": stock.get("name") or "-", "ticker": stock.get("ticker") or "-", "status": status, "data": items, "message": result.get("message", "")})
        except Exception:
            summary["failed"] += 1
            rows.append({"name": stock.get("name") or "-", "ticker": stock.get("ticker") or "-", "status": "응답 오류", "data": [], "message": "뉴스 조회에 실패했습니다"})
    return {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "rows": rows, "summary": summary}


def _classify_market_news_items(items, company_name, ticker):
    classified = [
        (item, news_data.classify_news_materiality(item, company_name, ticker))
        for item in items or []
    ]
    def sort_key(pair):
        item, classification = pair
        try:
            published = datetime.fromisoformat(str(item.get("pub_date", ""))).timestamp()
        except (TypeError, ValueError, OverflowError):
            published = float("-inf")
        return (classification.get("level") == "기업 직접 재료 후보", published)
    return sorted(classified, key=sort_key, reverse=True)


@_reference_panel_guard(
    "시장 뉴스",
    (("news_data", "fetch_naver_news"), ("news_data", "classify_news_materiality")),
    "현재 뉴스 조회에 실패했습니다. 잠시 후 다시 시도하세요.",
)
def _render_market_naver_news_panel(market, stocks, title, button_key, results_key, checked_at_key):
    st.markdown(f"### {title}")
    st.caption("네이버 뉴스 참고 조회 · 저장 안 됨 · 점수 미반영")
    st.caption("키워드 기반 1차 참고 분류 · 점수 미반영")
    client_id = st.secrets.get("NAVER_CLIENT_ID")
    client_secret = st.secrets.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        st.info("네이버 뉴스 API 설정이 필요합니다")
    if st.button("최근 뉴스 자동 확인", key=button_key):
        if client_id and client_secret:
            result = _fetch_market_naver_news(client_id, client_secret, stocks)
            st.session_state[results_key] = result
            st.session_state[checked_at_key] = result.get("checked_at")
    result = st.session_state.get(results_key)
    if not result:
        return
    summary = result.get("summary", {})
    st.caption(f"조회 시각: {st.session_state.get(checked_at_key) or '-'} · 조회 종목 수: {len(result.get('rows', []))} · 정상 {summary.get('normal', 0)} · 최근 뉴스 없음 {summary.get('empty', 0)} · 실패 {summary.get('failed', 0)}")
    for row in result.get("rows", []):
        display_items = _classify_market_news_items(row.get("data", []), row.get("name", ""), row.get("ticker", ""))
        direct_count = sum(1 for _, classification in display_items if classification.get("level") == "기업 직접 재료 후보")
        header = f"최근 뉴스 {len(display_items)}건 · 기업 직접 재료 후보 {direct_count}건" if display_items else ("최근 뉴스 없음" if row.get("status") == "데이터 없음" else row.get("status", "조회 오류"))
        with st.expander(f"{row['name']} · {row['ticker']} · {header}", expanded=False):
            if row.get("status") == "데이터 없음":
                st.info("최근 3일 뉴스 없음")
            elif row.get("status") != "정상":
                st.warning(row.get("message") or row.get("status") or "뉴스 조회에 실패했습니다")
            for index, (item, classification) in enumerate(display_items):
                if index:
                    st.markdown("---")
                if classification["level"] == "기업 직접 재료 후보":
                    label = f"{classification['level']} · {classification['category']} · {classification['market_reaction']}"
                else:
                    label = f"{classification['level']} · {classification['market_reaction']}"
                st.write(label)
                if classification.get("reason"):
                    st.caption(f"분류 근거: {classification['reason']}")
                st.write(f"날짜·시간: {item.get('pub_date') or '-'}")
                st.write(f"제목: {item.get('title') or '-'}")
                st.caption(item.get("description") or "-")
                link = item.get("originallink") or item.get("link")
                if link:
                    st.markdown(f"[원문 보기]({link})")

# 사람이 보기 쉬운 "기준 이름" 정리(별칭/문서화용). 기존 session_state 키(snap_{ticker}_current 등)와
# 계산 변수 이름(open_pos_pct 등)은 그대로 두고 바꾸지 않는다 — 나중에 DB 저장이나 실제 시세 API를
# 연결할 때 이 기준 이름을 참고용으로 쓰기 위해 미리 정리만 해 둔다. 지금은 어떤 로직에도 쓰이지 않는다.
SNAPSHOT_FIELD_CANONICAL_NAMES = {
    "current": "current_price",
    "open": "open_price",
    "high": "high_price",
    "low": "low_price",
    "turnover": "trading_value",
    "market_cap": "market_cap",
    "volume": "volume",
}
SNAPSHOT_CALC_CANONICAL_NAMES = {
    "open_pos_pct": "price_vs_open_pct",
    "high_drop_pct": "drop_from_high_pct",
    "turnover_ratio_pct": "trading_value_to_market_cap_pct",
}

# 미국장 스윙 기록 바로 저장 전용 기본 종목(8개, 고정 리스트 안 뽑혔을 때 대체값).
# 한국 종목(SNAPSHOT_STOCKS)과는 ticker가 겹치지 않으므로 같은 session_state 키 규칙
# (snap_{ticker}_{field})을 그대로 쓴다.
DEFAULT_US_SNAPSHOT_STOCKS = [
    {"name": "TSLA", "ticker": "TSLA", "sector": "미국-자동차"},
    {"name": "AMD", "ticker": "AMD", "sector": "미국-반도체"},
    {"name": "AVGO", "ticker": "AVGO", "sector": "미국-반도체"},
    {"name": "META", "ticker": "META", "sector": "미국-빅테크"},
    {"name": "GOOGL", "ticker": "GOOGL", "sector": "미국-빅테크"},
    {"name": "AAPL", "ticker": "AAPL", "sector": "미국-빅테크"},
    {"name": "NVDA", "ticker": "NVDA", "sector": "미국-반도체"},
    {"name": "MSFT", "ticker": "MSFT", "sector": "미국-빅테크"},
]

# 2026-07-15(사용자 명시 요청): 한국장처럼 "거래대금 상위 종목 자동 선정"을 미국장에도
# 적용한다. 다만 미국 전체 상장 종목(수천 개)을 무료 소스로 실시간 스캔할 방법이 없어
# (KRX 전체 종목표 같은 벌크 API가 없음), 유동성 높은 대형주 후보군 안에서 오늘 거래대금
# (근사치 = 거래량×종가) 상위를 골라낸다. 사용자가 이 방식(1안)을 명시적으로 선택했다.
US_CANDIDATE_UNIVERSE = [
    {"name": "TSLA", "ticker": "TSLA", "sector": "미국-자동차"},
    {"name": "AMD", "ticker": "AMD", "sector": "미국-반도체"},
    {"name": "AVGO", "ticker": "AVGO", "sector": "미국-반도체"},
    {"name": "META", "ticker": "META", "sector": "미국-빅테크"},
    {"name": "GOOGL", "ticker": "GOOGL", "sector": "미국-빅테크"},
    {"name": "AAPL", "ticker": "AAPL", "sector": "미국-빅테크"},
    {"name": "NVDA", "ticker": "NVDA", "sector": "미국-반도체"},
    {"name": "MSFT", "ticker": "MSFT", "sector": "미국-빅테크"},
    {"name": "AMZN", "ticker": "AMZN", "sector": "미국-빅테크"},
    {"name": "NFLX", "ticker": "NFLX", "sector": "미국-미디어"},
    {"name": "INTC", "ticker": "INTC", "sector": "미국-반도체"},
    {"name": "QCOM", "ticker": "QCOM", "sector": "미국-반도체"},
    {"name": "MU", "ticker": "MU", "sector": "미국-반도체"},
    {"name": "PLTR", "ticker": "PLTR", "sector": "미국-소프트웨어"},
    {"name": "COIN", "ticker": "COIN", "sector": "미국-핀테크"},
    {"name": "RIVN", "ticker": "RIVN", "sector": "미국-자동차"},
    {"name": "LCID", "ticker": "LCID", "sector": "미국-자동차"},
    {"name": "SOFI", "ticker": "SOFI", "sector": "미국-핀테크"},
    {"name": "F", "ticker": "F", "sector": "미국-자동차"},
    {"name": "GM", "ticker": "GM", "sector": "미국-자동차"},
    {"name": "BA", "ticker": "BA", "sector": "미국-항공방산"},
    {"name": "DIS", "ticker": "DIS", "sector": "미국-미디어"},
    {"name": "PYPL", "ticker": "PYPL", "sector": "미국-핀테크"},
    {"name": "UBER", "ticker": "UBER", "sector": "미국-플랫폼"},
    {"name": "ABNB", "ticker": "ABNB", "sector": "미국-플랫폼"},
    {"name": "CRWD", "ticker": "CRWD", "sector": "미국-소프트웨어"},
    {"name": "SNOW", "ticker": "SNOW", "sector": "미국-소프트웨어"},
    {"name": "SHOP", "ticker": "SHOP", "sector": "미국-소프트웨어"},
    {"name": "SQ", "ticker": "SQ", "sector": "미국-핀테크"},
    {"name": "MRNA", "ticker": "MRNA", "sector": "미국-바이오"},
    {"name": "PFE", "ticker": "PFE", "sector": "미국-바이오"},
    {"name": "XOM", "ticker": "XOM", "sector": "미국-에너지"},
    {"name": "CVX", "ticker": "CVX", "sector": "미국-에너지"},
    {"name": "JPM", "ticker": "JPM", "sector": "미국-금융"},
    {"name": "BAC", "ticker": "BAC", "sector": "미국-금융"},
    {"name": "WMT", "ticker": "WMT", "sector": "미국-유통"},
]

# 2026-07-13(한국장과 동일 패턴): "미국 거래대금 상위 종목 다시 선정" 버튼을 누르면
# session_state["dynamic_us_snapshot_stocks"]가 채워져 이 목록을 대체한다. 아직 버튼을
# 안 눌렀으면(세션 시작 직후 등) DEFAULT_US_SNAPSHOT_STOCKS로 안전하게 대체한다.
# US_SNAPSHOT_STOCKS를 참조하는 기존 코드(스윙 계산, 종목 자동 채우기 등)는 전부 그대로
# 두고 손댈 필요 없다 — 매 스크립트 실행마다 새로 계산되는 전역 변수이기 때문.
US_SNAPSHOT_STOCKS = st.session_state.get("dynamic_us_snapshot_stocks") or DEFAULT_US_SNAPSHOT_STOCKS


MARKET_OVERVIEW_MIN_SIGNALS = 3
MARKET_OVERVIEW_PRICE_SPECS = {
    "KR": [
        ("KOSPI·KOSDAQ", ("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")),
        ("달러/원", ("달러/원", "KRW=X")),
        ("반도체", ("SOXX", "SOXX"), ("SMH", "SMH")),
        ("나스닥100 선물", ("나스닥100 선물", "NQ=F")),
    ],
    "US": [
        ("S&P500·Nasdaq", ("S&P500", "^GSPC"), ("Nasdaq", "^IXIC")),
        ("미국 10년물", ("미국 10년물", "^TNX")),
        ("VIX", ("VIX", "^VIX")),
        ("반도체", ("SOXX", "SOXX"), ("SMH", "SMH")),
    ],
}
MARKET_OVERVIEW_NEWS_QUERIES = {
    "KR": ("코스피 코스닥 마감", "국내 증시 환율 외국인 기관"),
    "US": ("뉴욕증시 마감 나스닥", "미국 국채금리 연준 증시"),
}
MARKET_OVERVIEW_NEWS_CONTEXT = {
    "KR": ("코스피", "코스닥", "국내증시", "국내 증시", "증시", "환율", "원달러", "외국인", "기관"),
    "US": ("뉴욕증시", "미국증시", "미국 증시", "나스닥", "S&P500", "연준", "미국 국채금리", "국채금리"),
}
MARKET_OVERVIEW_OTHER_MARKET_TERMS = {
    "KR": ("뉴욕증시", "미국 증시", "나스닥", "일본 증시", "중국 증시", "홍콩 증시", "유럽 증시"),
    "US": ("한국 증시", "코스피", "코스닥", "일본 증시", "중국 증시", "홍콩 증시", "유럽 증시"),
}
MARKET_OVERVIEW_HISTORY_TERMS = ("과거", "역사", "회고", "몇 년 전", "10년 전", "지난해")


def _market_overview_direction(changes, positive_label, negative_label, mixed_label):
    valid = [value for value in changes if isinstance(value, (int, float)) and math.isfinite(value)]
    if not valid:
        return "확인 불가"
    if all(value > 0 for value in valid):
        return positive_label
    if all(value < 0 for value in valid):
        return negative_label
    if any(value > 0 for value in valid) and any(value < 0 for value in valid):
        return mixed_label
    return "보합"


def _market_overview_status(market, signal_changes, signal_details=None):
    """Return a neutral four-state market summary from already fetched changes."""
    changes = [value for value in signal_changes.values() if isinstance(value, (int, float)) and math.isfinite(value)]
    if len(changes) < MARKET_OVERVIEW_MIN_SIGNALS:
        return "자료 부족", "[규칙 해석] 평가 가능한 시장 신호가 부족해 추가 확인이 필요합니다."
    positive = sum(value > 0 for value in changes)
    negative = sum(value < 0 for value in changes)
    state = "우호" if positive > negative else "경계" if negative > positive else "혼조"
    if signal_details:
        if market == "KR":
            index_text = _market_overview_direction(signal_details.get("KOSPI·KOSDAQ", []), "코스피·코스닥 동반 상승", "코스피·코스닥 동반 하락", "코스피·코스닥 흐름 엇갈림")
            dollar_text = _market_overview_direction([-value for value in signal_details.get("달러/원", [])], "달러/원 하락", "달러/원 상승", "달러/원 보합")
            semi_text = _market_overview_direction(signal_details.get("반도체", []), "반도체 ETF 동반 상승", "반도체 ETF 동반 하락", "반도체 ETF 흐름 엇갈림")
            future_text = _market_overview_direction(signal_details.get("나스닥100 선물", []), "나스닥100 선물 상승", "나스닥100 선물 하락", "나스닥100 선물 보합")
            return state, f"[규칙 해석] {index_text}, {dollar_text}, {semi_text}, {future_text}으로 실제 조회 결과를 함께 확인합니다."
        index_text = _market_overview_direction(signal_details.get("S&P500·Nasdaq", []), "S&P500·Nasdaq 동반 상승", "S&P500·Nasdaq 동반 하락", "S&P500·Nasdaq 흐름 엇갈림")
        rate_text = _market_overview_direction([-value for value in signal_details.get("미국 10년물", [])], "미국 10년물 하락", "미국 10년물 상승", "미국 10년물 보합")
        vix_text = _market_overview_direction([-value for value in signal_details.get("VIX", [])], "VIX 하락", "VIX 상승", "VIX 보합")
        semi_text = _market_overview_direction(signal_details.get("반도체", []), "반도체 ETF 동반 상승", "반도체 ETF 동반 하락", "반도체 ETF 흐름 엇갈림")
        return state, f"[규칙 해석] {index_text}, {rate_text}, {vix_text}, {semi_text}으로 실제 조회 결과를 함께 확인합니다."
    if positive > negative:
        return "우호", "[규칙 해석] 긍정 신호가 상대적으로 우세해 시장 흐름을 확인할 수 있습니다."
    if negative > positive:
        return "경계", "[규칙 해석] 부정 신호가 상대적으로 우세해 시장 확인이 우선입니다."
    return "혼조", "[규칙 해석] 긍정·부정 신호가 엇갈려 시장 확인이 우선입니다."


def _dedup_market_overview_news(rows, market=None):
    """Deduplicate market-news candidates by URL identity and normalized title."""
    seen_urls = set()
    seen_titles = set()
    result = []
    context_terms = MARKET_OVERVIEW_NEWS_CONTEXT.get(market, ())
    other_terms = MARKET_OVERVIEW_OTHER_MARKET_TERMS.get(market, ())
    for row in sorted(rows or [], key=lambda item: item.get("pub_date") or "", reverse=True):
        title = " ".join(str(row.get("title") or "").split()).strip()
        search_text = f"{title} {row.get('description') or ''}"
        context_hits = sum(term in search_text for term in context_terms)
        if market and (not context_hits or any(term in search_text for term in MARKET_OVERVIEW_HISTORY_TERMS)):
            continue
        if market and any(term in search_text for term in other_terms):
            continue
        url = str(row.get("originallink") or row.get("link") or "").strip()
        identity = url or title
        if not identity or url in seen_urls or title in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        result.append({**row, "title": title, "_context_hits": context_hits})
    result.sort(key=lambda item: (item.get("_context_hits", 0), item.get("pub_date") or ""), reverse=True)
    for row in result:
        row.pop("_context_hits", None)
    return result


def _market_overview_price_item(label, ticker, result):
    if not result or not result.get("ok"):
        return {"label": label, "ticker": ticker, "status": "확인 불가", "current": None, "change_pct": None}
    current = result.get("current")
    previous = result.get("prev_close")
    change_pct = _safe_pct_diff(current, previous)
    if not isinstance(current, (int, float)) or not math.isfinite(current) or current <= 0:
        return {"label": label, "ticker": ticker, "status": "확인 불가", "current": None, "change_pct": None}
    return {"label": label, "ticker": ticker, "status": "정상", "current": current, "change_pct": change_pct}


def _get_kr_index_intraday(ticker):
    """KIS, 네이버 현재지수, Yahoo 지연 1분봉 순서로 국내 장중지수를 조회한다."""
    try:
        kis_result = kis_market_data.get_index_snapshot(
            ticker,
            st.secrets.get("KIS_APP_KEY"),
            st.secrets.get("KIS_APP_SECRET"),
        )
    except Exception:
        kis_result = {"ok": False}
    if kis_result.get("ok"):
        return kis_result
    try:
        naver_result = naver_market_data.get_index_snapshot(ticker)
    except Exception:
        naver_result = {"ok": False}
    if naver_result.get("ok"):
        return naver_result
    try:
        yahoo_result = price_data.get_intraday_last(ticker)
    except Exception:
        yahoo_result = {"ok": False}
    if yahoo_result.get("ok"):
        return {**yahoo_result, "source": "Yahoo 1분봉(지연 가능)"}
    return yahoo_result


def _get_recent_market_intraday(ticker, *, now=None):
    """최근 1분봉만 장중값으로 인정한다. 오래된 마지막 봉은 종가 fallback으로 넘긴다."""
    try:
        result = price_data.get_intraday_last(ticker)
    except Exception:
        return {"ok": False, "error": "장중 1분봉 조회 실패"}
    if not result or not result.get("ok") or not result.get("prev_close"):
        return result or {"ok": False, "error": "장중 1분봉 데이터 없음"}

    try:
        as_of_date = str(result.get("as_of_date") or "").strip()
        as_of_time = str(result.get("as_of_time") or result.get("asof") or "").strip()
        as_of = datetime.strptime(f"{as_of_date} {as_of_time}", "%Y-%m-%d %H:%M").replace(
            tzinfo=ZoneInfo("Asia/Seoul")
        )
        now_seoul = now or datetime.now(ZoneInfo("Asia/Seoul"))
        if now_seoul.tzinfo is None:
            now_seoul = now_seoul.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        else:
            now_seoul = now_seoul.astimezone(ZoneInfo("Asia/Seoul"))
        # Yahoo의 NQ 선물은 약 10분 늦을 수 있어 15분까지 허용한다. 그 밖의 자산은
        # 5분 이내 봉만 사용해 미국장 마감 뒤의 ETF 마지막 봉을 장중가로 오인하지 않는다.
        max_age = timedelta(minutes=15 if str(ticker).upper() == "NQ=F" else 5)
        age = now_seoul - as_of
        if as_of.date() != now_seoul.date() or age > max_age or age < -timedelta(minutes=1):
            return {"ok": False, "error": "최신 장중 1분봉이 아님"}
    except (TypeError, ValueError):
        return {"ok": False, "error": "장중 1분봉 기준 시각 확인 실패"}
    return {**result, "source": "Yahoo 1분봉(지연 가능)"}


def _sparkline_svg(values, is_up, width=110, height=32):
    """최근 며칠치 종가로 아주 작은 추세선(SVG)을 그린다. 실시간이 아니라 "오늘 X장 자료
    불러오기" 버튼을 누른 시점의 일봉 데이터로만 그린다(CLAUDE.md "실시간 자동조회 금지"
    규칙 — 버튼 클릭 시에만 조회하는 기존 종목별 일봉 차트와 동일한 방식, 2026-07-13
    사용자 승인). values가 2개 미만이면 빈 문자열(그릴 게 없음)."""
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1
    step = width / (len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - ((v - lo) / rng) * (height - 4) - 2:.1f}"
        for i, v in enumerate(values)
    )
    color = "#ff4b4b" if is_up else "#4b9fff"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:block;margin-top:6px">'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def _build_market_overview_price_item(market, label, ticker):
    """카드 항목 1개(티커 1개)의 장중가→종가 폴백 + 10일 이력을 만든다.

    2026-07-15: 예전에는 이 작업을 티커 8~10개에 대해 순차 실행해서(티커당 장중 조회
    0.5~1초 + 이력 조회 0.5초) 시장 자료 버튼 한 번에 6~10초가 걸렸다 — 사용자가
    반복 지적한 "너무 느리다"의 최대 단일 병목. _fetch_market_overview()가 이 함수를
    티커별로 병렬 호출한다.
    """
    _intraday = {"ok": False}
    if market == "KR" and ticker in {"^KS11", "^KQ11"}:
        try:
            _intraday = _get_kr_index_intraday(ticker)
        except Exception:
            _intraday = {"ok": False}
    else:
        try:
            _intraday = _get_recent_market_intraday(ticker)
        except Exception:
            _intraday = {"ok": False}
    if _intraday.get("ok") and _intraday.get("prev_close"):
        item = _market_overview_price_item(label, ticker, _intraday)
        item["asof"] = _intraday.get("as_of_time") or _intraday.get("asof")
        item["as_of_time"] = item["asof"]
        item["as_of_date"] = _intraday.get("as_of_date")
        item["data_kind"] = "intraday"
        item["source"] = _intraday.get("source")
    else:
        _daily_result = None
        if market == "KR" and ticker in {"^KS11", "^KQ11"}:
            # 야간에는 yfinance가 당일 종가를 하루 늦게 올려서 KOSPI/KOSDAQ가
            # 어제 값(-8.95% 같은)으로 보이던 문제(2026-07-15 사용자 확인) —
            # 네이버가 주는 가장 최근 종가를 먼저 쓰고, 그것도 실패할 때만
            # yfinance 완료 거래일 종가로 넘어간다. price_data.py는 손대지 않는다.
            try:
                _naver_close = naver_market_data.get_index_daily_close(ticker)
            except Exception:
                _naver_close = {"ok": False}
            if _naver_close.get("ok"):
                _daily_result = _naver_close
        if _daily_result is None:
            try:
                if market == "KR" and ticker in {"^KS11", "^KQ11"}:
                    _daily_result = price_data.get_snapshot_defaults(ticker, completed_only=True)
                else:
                    _daily_result = price_data.get_snapshot_defaults(ticker)
            except Exception:
                _daily_result = None
        item = _market_overview_price_item(label, ticker, _daily_result)
        # 장중 조회 실패 시에만 최근 완료 거래일 종가로 대체한다. KIS/Yahoo
        # 모두 실패해도 다른 카드와 뉴스는 계속 표시한다.
        item["data_kind"] = "daily_close" if _daily_result and _daily_result.get("as_of_date") else "unknown"
        item["asof"] = _daily_result.get("as_of_date") if _daily_result else None
        item["as_of_date"] = _daily_result.get("as_of_date") if _daily_result else None
        item["as_of_time"] = None
        if item["status"] != "정상":
            # 2026-07-15 실측 확인: yfinance가 최신 거래일 행에 NaN OHLC를 준 채로
            # 며칠 유지하는 경우가 있다(SOXX/SMH에서 재현) — get_snapshot_defaults가
            # 쓰는 헬퍼는 "최신 행 하나라도 무효면 전체 거부"라 이럴 때 완전히 실패한다.
            # get_ohlc_history_for_chart는 그 문제를 피하려고 이미 따로 만든 함수라서
            # (price_data.py 자체 주석에 명시) 마지막 유효한 종가까지 내려가서 쓴다.
            # price_data.py는 건드리지 않는다.
            try:
                _fallback_end = datetime.now()
                _fallback_start = _fallback_end - timedelta(days=10)
                _fallback_df = price_data.get_ohlc_history_for_chart(
                    ticker, _fallback_start.strftime("%Y-%m-%d"), _fallback_end.strftime("%Y-%m-%d")
                )
            except Exception:
                _fallback_df = None
            if _fallback_df is not None and not _fallback_df.empty and "Close" in _fallback_df.columns:
                _valid_closes = [
                    (idx, float(v)) for idx, v in _fallback_df["Close"].items()
                    if isinstance(v, (int, float)) and math.isfinite(v) and v > 0
                ]
                if len(_valid_closes) >= 2:
                    _fb_asof, _fb_current = _valid_closes[-1]
                    _fb_prev_close = _valid_closes[-2][1]
                    item = {
                        "label": label, "ticker": ticker, "status": "정상",
                        "current": _fb_current,
                        "change_pct": _safe_pct_diff(_fb_current, _fb_prev_close),
                    }
                    item["data_kind"] = "daily_close"
                    _fb_date_text = pd.Timestamp(_fb_asof).strftime("%Y-%m-%d")
                    item["asof"] = _fb_date_text
                    item["as_of_date"] = _fb_date_text
                    item["as_of_time"] = None
    item["history"] = []
    item["history_kind"] = "daily"
    if item["status"] == "정상":
        # 장중 값이면 미니 차트도 오늘 장중 흐름(5분봉)으로 그린다 — 네이버처럼
        # 숫자(+6%)와 차트 방향이 일치해야 한다는 지적(2026-07-15) 반영.
        # 실시간 스트리밍이 아니라 이 조회 시점에 한 번 받는 지연 가능 스냅샷이다.
        if item.get("data_kind") == "intraday":
            try:
                import yfinance as yf

                _intra_df = yf.Ticker(ticker).history(period="1d", interval="5m")
                _intra_closes = [
                    float(v) for v in _intra_df["Close"].tolist()
                    if isinstance(v, (int, float)) and math.isfinite(v)
                ]
                if len(_intra_closes) >= 5:
                    item["history"] = _intra_closes[-40:]
                    item["history_kind"] = "intraday"
            except Exception:
                pass
        if not item["history"]:
            # 실시간 아님 — 이 버튼을 누른 시점에만 최근 10일치 종가를 한 번 조회한다.
            try:
                _hist_end = datetime.now()
                _hist_start = _hist_end - timedelta(days=14)
                _hist_df = price_data.get_ohlc_history_for_chart(
                    ticker, _hist_start.strftime("%Y-%m-%d"), _hist_end.strftime("%Y-%m-%d")
                )
                if _hist_df is not None and not _hist_df.empty:
                    item["history"] = [float(v) for v in _hist_df["Close"].tail(10).tolist()]
            except Exception:
                item["history"] = []
        # yfinance 이력에 아직 오늘 값이 없으면(밤·장중), 이력 끝에 현재값을
        # 붙인다 — 숫자는 +6%인데 미니 차트는 어제까지의 하락만 그려져 서로
        # 모순돼 보이던 문제(2026-07-15 사용자 지적) 수정. 마지막 이력과 거의
        # 같은 값이면(이미 반영됨) 중복으로 붙이지 않는다.
        _cur = item.get("current")
        if item["history"] and isinstance(_cur, (int, float)) and math.isfinite(_cur):
            _last_hist = item["history"][-1]
            if _last_hist and abs(_cur - _last_hist) / abs(_last_hist) > 0.0005:
                item["history"] = item["history"] + [float(_cur)]
    return item


def _fetch_market_overview(market):
    rows = []
    signal_changes = {}
    signal_details = {}

    # 카드 항목(티커)들을 전부 동시에 조회한다 — 순서는 카드 정의 순서를 유지한다.
    _specs = []
    for _card_index, card in enumerate(MARKET_OVERVIEW_PRICE_SPECS[market]):
        for label, ticker in card[1:]:
            _specs.append((_card_index, label, ticker))
    _items_by_position = {}
    if _specs:
        with ThreadPoolExecutor(max_workers=min(16, len(_specs))) as _executor:
            _future_to_position = {
                _executor.submit(_build_market_overview_price_item, market, label, ticker): position
                for position, (_card_index, label, ticker) in enumerate(_specs)
            }
            for _future in as_completed(_future_to_position):
                _position = _future_to_position[_future]
                _card_index, _label, _ticker = _specs[_position]
                try:
                    _items_by_position[_position] = _future.result()
                except Exception:
                    _items_by_position[_position] = {
                        "label": _label, "ticker": _ticker, "status": "확인 불가",
                        "current": None, "change_pct": None, "history": [],
                        "data_kind": "unknown", "asof": None, "as_of_date": None, "as_of_time": None,
                    }

    for _card_index, card in enumerate(MARKET_OVERVIEW_PRICE_SPECS[market]):
        card_items = [
            _items_by_position[position]
            for position, (spec_card_index, _label, _ticker) in enumerate(_specs)
            if spec_card_index == _card_index
        ]
        valid_changes = [item["change_pct"] for item in card_items if item["change_pct"] is not None]
        signal_details[card[0]] = valid_changes
        if valid_changes:
            signal_value = sum(valid_changes) / len(valid_changes)
            if (market == "KR" and card[0] == "달러/원") or (
                market == "US" and card[0] in ("미국 10년물", "VIX")
            ):
                signal_value = -signal_value
            signal_changes[card[0]] = signal_value
        rows.append({"label": card[0], "items": card_items})

    news_rows = []
    news_failed = 0
    client_id = st.secrets.get("NAVER_CLIENT_ID")
    client_secret = st.secrets.get("NAVER_CLIENT_SECRET")
    _news_queries = MARKET_OVERVIEW_NEWS_QUERIES[market]

    def _fetch_news_query(query):
        return news_data.fetch_naver_news(client_id, client_secret, query, display=10, sort="date")

    with ThreadPoolExecutor(max_workers=len(_news_queries)) as _news_executor:
        _news_futures = [_news_executor.submit(_fetch_news_query, query) for query in _news_queries]
        for _news_future in _news_futures:
            try:
                result = _news_future.result()
                if result.get("status") in ("정상", "데이터 없음"):
                    recent = _recent_naver_news_items(result.get("data", []))
                    news_rows.extend(recent)
                else:
                    news_failed += 1
            except Exception:
                news_failed += 1
    return {
        "market": market,
        "price_cards": rows,
        "news": _dedup_market_overview_news(news_rows, market),
        "news_failed": news_failed,
        "status": _market_overview_status(market, signal_changes, signal_details),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@st.cache_data(ttl=45, show_spinner=False)
def _cached_fetch_market_overview(market):
    """로그인 자동조회가 가까운 시각의 동일 시장 자료를 중복 호출하지 않게 한다."""
    return _fetch_market_overview(market)


# 2026-07-15 사용자 요청: "새로고침" 버튼들은 지금까지 캐시를 완전히 무시하고 매번
# 새로 조회했다 — 의도적 새로고침이니 당연한 설계였지만, 실수로 또는 확인 차 바로
# 다시 누르면 매번 몇 초씩 다시 기다려야 했다("다시 누르면 너무 느리다"). 8초 정도의
# 아주 짧은 캐시만 끼워 넣으면 연속 재클릭은 즉시 응답되면서도, 실제 "새로고침" 의도
# (몇 초~몇 분 뒤 다시 누르는 경우)는 그대로 살아있다. 시세 데이터는 8초 안에 크게
# 달라지지 않으므로 정확도 손해도 사실상 없다.
FORCE_REFRESH_SHORT_TTL = 8


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_fetch_market_overview(market):
    return _fetch_market_overview(market)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_fetch_bookmaker_snapshot():
    """사용자가 버튼을 눌렀을 때만 조회하고, 짧은 시간의 중복 조회는 재사용한다."""
    return bookmaker_data.fetch_bookmaker_snapshot()


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_translate_bookmaker_texts(texts, _api_key):
    """같은 공개 시장 문장의 번역을 기기별 세션에서도 다시 요청하지 않는다."""
    return deepl_translate.translate_texts_to_ko(list(texts), _api_key)


def _render_kr_market_mood_strip():
    """한국장 요약 스트립(KOSPI/KOSDAQ/달러원/나스닥100선물/SOXX·SMH/오늘저장/금일손실R)을
    한 줄 카드로 렌더링한다. 2026-07-13 사용자 요청으로 "시장 주요 뉴스 후보" 위로
    옮겼다(기존엔 그 아래, _render_kr_fable_mockup1_preview 안에 있었음). CSS 클래스
    (.jarvis-m1-strip 등)는 _render_kr_fable_mockup1_preview가 주입하며, style 태그는
    DOM 순서와 무관하게 적용되므로 렌더 순서가 바뀌어도 문제없다."""
    mood_rows = st.session_state.get("kr_mood_auto_results") or []
    mood_by_name = {
        row.get("항목"): row
        for row in mood_rows
        if isinstance(row, dict) and row.get("항목")
    }
    kospi_row = mood_by_name.get("KOSPI") or mood_by_name.get("코스피") or {}
    kosdaq_row = mood_by_name.get("KOSDAQ") or mood_by_name.get("코스닥") or {}
    usdkrw_row = mood_by_name.get("달러/원") or {}
    nasdaq_row = mood_by_name.get("나스닥100 선물") or {}
    soxx_row = mood_by_name.get("SOXX") or {}
    smh_row = mood_by_name.get("SMH") or {}

    try:
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        today_saved = sum(
            1
            for report in db.list_reports()
            if str(report.get("saved_at") or "").startswith(today_prefix)
        )
    except Exception:
        today_saved = "-"

    if "risk_today_loss_r" in st.session_state and st.session_state["risk_today_loss_r"] is not None:
        today_loss_r = f"{st.session_state['risk_today_loss_r']}R"
    else:
        today_loss_r = "-"

    strip_items = [
        ("KOSPI", kospi_row.get("등락률(%)", "-")),
        ("KOSDAQ", kosdaq_row.get("등락률(%)", "-")),
        ("달러/원", usdkrw_row.get("등락률(%)", "-")),
        ("나스닥100 선물", nasdaq_row.get("등락률(%)", "-")),
        (
            "SOXX / SMH",
            f"SOXX {soxx_row.get('등락률(%)', '-')} · SMH {smh_row.get('등락률(%)', '-')}",
        ),
        ("오늘 저장", today_saved),
        ("금일 손실 R", today_loss_r),
    ]

    def _strip_value_class(value):
        text = str(value)
        if "+" in text:
            return " jarvis-m1-up"
        if "-" in text and text != "-":
            return " jarvis-m1-down"
        return ""

    strip_html = "".join(
        '<div class="jarvis-m1-strip-item">'
        f'<span class="jarvis-m1-strip-label">{label}</span>'
        f'<span class="jarvis-m1-strip-value{_strip_value_class(value)}">{value}</span>'
        "</div>"
        for label, value in strip_items
    )
    if any(value != "-" for _, value in strip_items[:5]):
        st.markdown(f'<div class="jarvis-m1-strip">{strip_html}</div>', unsafe_allow_html=True)


def _render_market_overview(market):
    prefix = market.lower()
    result_key = f"{prefix}_market_overview_result"
    checked_key = f"{prefix}_market_overview_checked_at"
    button_key = f"{prefix}_market_overview_load"
    title = "오늘 한국장 한눈에" if market == "KR" else "오늘 미국장 한눈에"
    market_label = "한국장" if market == "KR" else "미국장"
    result = st.session_state.get(result_key)

    st.markdown(f"<div style='font-size:26px;font-weight:800;margin:0 0 10px 0'>{title}</div>", unsafe_allow_html=True)
    if market == "KR":
        _overview_guide = (
            "로그인 후 한국장 자료를 자동으로 불러왔습니다. 필요할 때만 아래 파란 버튼으로 다시 조회하세요."
            if result else
            "로그인 후 한국장 자료·종목 판단·테마 참고판을 자동으로 불러오는 중입니다."
        )
    else:
        _overview_guide = f"먼저 아래 파란 버튼을 눌러 오늘 {market_label} 자료를 확인하세요."
    st.markdown(
        f"<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin:14px 0 22px'>{_overview_guide}</div>",
        unsafe_allow_html=True,
    )
    if st.button("오늘 한국장 자료 불러오기" if market == "KR" else "오늘 미국장 자료 불러오기", key=button_key):
        st.session_state[result_key] = _short_cached_fetch_market_overview(market)
        st.session_state[checked_key] = st.session_state[result_key]["checked_at"]
        result = st.session_state[result_key]
    if not result:
        if market == "KR":
            st.info("한국장 자동 조회가 진행 중입니다.")
        else:
            st.info("버튼을 눌러 시장 자료를 확인하세요. 앱 실행만으로 외부 조회는 하지 않습니다.")
        return
    state, explanation = result["status"]
    state_colors = {"우호": "#15803D", "혼조": "#1D4ED8", "경계": "#D97706", "자료 부족": "#6B7280"}
    st.markdown(
        f"<div style='color:{state_colors[state]};font-size:20px;line-height:1.65;font-weight:800;margin-top:20px'>상태: {state}</div>"
        f"<div style='font-size:19px;line-height:1.65;font-weight:700;margin:14px 0 24px'>{explanation}</div>",
        unsafe_allow_html=True,
    )
    with st.container(key=f"market_overview_cards_{prefix}"):
        card_columns = st.columns(4)
        for column, card in zip(card_columns, result["price_cards"]):
            with column:
                card_parts = [
                    "<div style='background:#171a21;border:1px solid #303642;border-radius:10px;"
                    "padding:14px 14px 12px 14px;min-height:128px'>",
                    f"<div style='font-size:18px;line-height:1.65;font-weight:800;color:#dbeafe;margin-bottom:10px'>{card['label']}</div>",
                ]
                for item in card["items"]:
                    if item["status"] != "정상":
                        card_parts.append(
                            f"<div style='font-size:18px;line-height:1.65;color:#CBD5E1'>{item['label']}</div>"
                            "<div style='font-size:20px;line-height:1.5;font-weight:800;color:#f3f4f6'>확인 불가</div>"
                            "<div style='font-size:14px;line-height:1.5;color:#8b95a5;margin-top:2px'>조회 기준 확인 불가</div>"
                        )
                    else:
                        unit = "%" if item["label"] == "미국 10년물" else ""
                        change = item["change_pct"]
                        change_color = "#22c55e" if change is not None and change > 0 else "#f87171" if change is not None and change < 0 else "#d1d5db"
                        change_text = "확인 불가" if change is None else _fmt_signed_pct(change)
                        _spark = _sparkline_svg(
                            item.get("history") or [], is_up=(change is not None and change >= 0)
                        )
                        # 2026-07-13 2차 수정: "지금 이 순간"처럼 보이지 않도록 데이터 종류별로
                        # 문구를 분리한다. 휴장/장마감으로 1분봉이 없으면 현재시각이 아니라
                        # 실제 대체된 종가의 날짜를 보여주고 "가격 지연 가능"을 항상 덧붙인다.
                        _data_kind = item.get("data_kind")
                        if _data_kind == "intraday":
                            _source_text = f" · {item.get('source')}" if item.get("source") else ""
                            _asof_text = f"장중 {item['asof']} 기준{_source_text}"
                        elif _data_kind == "daily_close":
                            _asof_text = f"{item['asof']} 종가 기준"
                        else:
                            _asof_text = "조회 기준 확인 불가"
                        card_parts.append(
                            f"<div style='font-size:18px;line-height:1.65;color:#CBD5E1'>{item['label']}</div>"
                            f"<div style='font-size:23px;line-height:1.5;font-weight:800;color:#f9fafb'>{item['current']:,.2f}{unit}</div>"
                            f"<div style='font-size:18px;line-height:1.65;color:{change_color};margin-top:6px'>{'등락률' if _data_kind == 'intraday' else '전일 대비 등락률'} {change_text}</div>"
                            f"<div style='font-size:14px;line-height:1.5;color:#8b95a5;margin-top:2px'>{_asof_text}</div>"
                            f"{_spark}"
                            # 장중 값이면 오늘 5분봉 흐름, 아니면 최근 10일 종가 추이 —
                            # 어떤 구간의 차트인지 라벨로 명시한다(2026-07-15 사용자 지적).
                            + (
                                (
                                    "<div style='font-size:12px;line-height:1.4;color:#6b7280'>오늘 장중 추이(5분봉·지연 가능)</div>"
                                    if item.get("history_kind") == "intraday"
                                    else "<div style='font-size:12px;line-height:1.4;color:#6b7280'>최근 10일 추이</div>"
                                )
                                if item.get("history") else ""
                            )
                        )
                card_parts.append("</div>")
                st.markdown("".join(card_parts), unsafe_allow_html=True)

    # 도박사(예측시장) 의견 — ChatGPT 브리핑의 [도박사] 구획을 붙여넣는 참고용 칸 +
    # Polymarket/Kalshi 공개 API 참고 조회(2026-07-13 추가). docs/PROJECT_SPEC.md의
    # "자동연동 금지"는 자동으로 점수·판정·DB에 반영하는 것을 금지한다는 뜻이지, 조회
    # 자체가 기술적으로 불가능하다는 뜻이 아니다(공개 API는 인증 없이 조회 가능,
    # theme_data.py의 네이버 스크래핑과 동일하게 이미 한 번 재승인된 전례가 있는 종류의
    # 제한). session_state에만 유지하며 DB에 저장하지 않고, 점수·판정 계산에도 절대
    # 반영하지 않는다. (2026-07-15: 사용자 요청으로 KR·US 둘 다 로그인/탭 진입 후 자동
    # 조회 체인에 포함시켰다 — kr_auto_run_stage2 / us_auto_run_stage1에서 세션당 한 번만
    # pending 플래그를 세운다.)
    # 2026-07-15 사용자 지적: 위 가격 카드와 아래 도박사 패널이 너무 붙어있었다.
    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
    # 2026-07-15 사용자 요청: 이 구획 제목만 글자 2배 크기(17px -> 34px)에 붉은색,
    # 연한 코발트 블루 배경을 넣는다. st.expander는 label에 HTML을 못 쓰므로
    # key로 이 expander만 골라 CSS로 덮어쓴다(다른 expander는 기존 스타일 유지).
    st.markdown(
        f"""
        <style>
        .st-key-{prefix}_bookmaker_expander [data-testid="stExpander"] summary,
        .st-key-{prefix}_bookmaker_expander [data-testid="stExpander"] summary p {{
            font-size: 34px !important;
            font-weight: 800 !important;
            color: #ef4444 !important;
        }}
        .st-key-{prefix}_bookmaker_expander [data-testid="stExpander"] {{
            background-color: rgba(0, 71, 171, 0.16) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.expander(
        f"오늘 {market_label} 도박사(예측시장) 의견",
        expanded=True,
        key=f"{prefix}_bookmaker_expander",
    ):
        _bookmaker_manual_fetch = st.button("오늘 도박사 신호 불러오기(Polymarket/Kalshi)", key=f"{prefix}_bookmaker_fetch")
        _bookmaker_auto_fetch = st.session_state.pop(f"{prefix}_bookmaker_auto_fetch_pending", False)
        # 2026-07-13 3차 수정: 임계값 다른 계약을 "사건 그룹"으로 묶어 보여주고(중복
        # 삭제 아님 — 확률분포), DeepL Free API로 사건 제목을 한국어로 번역해서 큰
        # 글씨로 먼저 보여준다(상하님이 영어 원문을 알아보기 어렵다는 지적). 번역은
        # 이 버튼을 눌렀을 때(또는 자동 조회 때), 그리고 세션 캐시에 없는 새 문장만
        # 호출한다.
        if _bookmaker_manual_fetch or _bookmaker_auto_fetch:
            with st.spinner("Polymarket/Kalshi 조회 중..."):
                _snapshot = _cached_fetch_bookmaker_snapshot()
            _translation_cache = st.session_state.setdefault("bookmaker_translation_cache", {})
            _market_texts = []
            for _event in _snapshot.get("events", []):
                if _event.get("title"):
                    _market_texts.append(_event["title"])
                _market_texts.extend(
                    contract["question"]
                    for contract in _event.get("contracts", [])
                    if contract.get("question")
                )
            _texts_to_translate = [
                text for text in dict.fromkeys(_market_texts)
                if text not in _translation_cache
            ]
            _deepl_key = st.secrets.get("DEEPL_API_KEY")
            st.session_state.pop("bookmaker_translation_error", None)
            if _texts_to_translate and _deepl_key:
                with st.spinner("한국어 번역 중..."):
                    _translate_result = _cached_translate_bookmaker_texts(
                        tuple(_texts_to_translate), _deepl_key
                    )
                if _translate_result.get("ok"):
                    _translation_cache.update(_translate_result.get("translations") or {})
                    # 배치 일부만 실패한 경우: 성공분은 반영하고 실패 사실도 알려준다.
                    if _translate_result.get("error"):
                        st.session_state["bookmaker_translation_error"] = _translate_result.get("error")
                else:
                    st.session_state["bookmaker_translation_error"] = _translate_result.get("error")
            st.session_state[f"{prefix}_bookmaker_snapshot"] = _snapshot
        _bookmaker_snapshot = st.session_state.get(f"{prefix}_bookmaker_snapshot")
        if _bookmaker_snapshot:
            if _bookmaker_snapshot.get("checked_at"):
                st.caption(f"마지막 조회: {_bookmaker_snapshot['checked_at']}")
            for _err in _bookmaker_snapshot.get("errors") or []:
                st.caption(f"일부 실패: {_err}")
            if st.secrets.get("DEEPL_API_KEY") and st.session_state.get("bookmaker_translation_error"):
                st.caption(f"번역 일부 실패: {st.session_state['bookmaker_translation_error']}")
            _translation_cache = st.session_state.get("bookmaker_translation_cache") or {}
            if _bookmaker_snapshot.get("events"):
                _source_order = ["Polymarket", "Kalshi"]
                _source_order.extend(
                    source for source in dict.fromkeys(
                        event.get("source") for event in _bookmaker_snapshot["events"]
                    )
                    if source and source not in _source_order
                )
                for _source in _source_order:
                    _source_events = [
                        event for event in _bookmaker_snapshot["events"]
                        if event.get("source") == _source
                    ]
                    if not _source_events:
                        continue
                    st.markdown(
                        f"<div style='font-size:22px;font-weight:800;color:#dbeafe;"
                        f"margin:18px 0 8px'>{html.escape(_source)}</div>",
                        unsafe_allow_html=True,
                    )
                    for _ev in _source_events:
                        # 이벤트(카드) 하나가 번역 실패 등으로 문제가 생겨도 다른 카드
                        # 렌더링은 계속되도록 카드별로 격리한다.
                        try:
                            _title_ko = (
                                _translation_cache.get(_ev["title"])
                                or deepl_translate.translate_market_text_locally(_ev["title"])
                            )
                            _title_html = (
                                # 2026-07-15 사용자 요청: 굵게 표시한 제목이 흰색 계열이라
                                # 색이 없어 보였다 — 눈에 띄는 파란색으로 바꾼다.
                                f"<div style='font-size:23px;line-height:1.45;font-weight:800;color:#60a5fa'>{html.escape(_title_ko)}</div>"
                                f"<div style='font-size:14px;line-height:1.5;color:#9ca3af;margin-top:4px'>영어 원문: {html.escape(_ev['title'])}</div>"
                                if _title_ko else
                                f"<div style='font-size:19px;line-height:1.5;font-weight:800;color:#f9fafb'>{html.escape(_ev['title'] or '-')}</div>"
                                + ("<div style='font-size:14px;color:#9ca3af;margin-top:3px'>번역 실패 · 영어 원문 표시</div>"
                                   if st.secrets.get("DEEPL_API_KEY") else "")
                            )
                            _event_volume = _ev.get("event_volume")
                            _event_volume_text = f"{_event_volume:,.0f}" if _event_volume is not None else "확인 불가"
                            _meta = (
                                f"<div style='font-size:15px;color:#aeb7c5;margin-top:8px'>{html.escape(str(_ev['source']))} · "
                                f"마감 {html.escape(str(_ev.get('end_date') or '-'))} · 24시간 거래량 {_event_volume_text}</div>"
                            )
                            _contract_rows = []
                            # 2026-07-15 사용자 지적: 확률이 낮은 계약까지 다 보여주면
                            # 화면이 너무 길어진다 — 확률 높은 순 상위 3개만 표시한다.
                            _ev_contracts_sorted = sorted(
                                _ev.get("contracts", []),
                                key=lambda c: c.get("probability_pct") or 0,
                                reverse=True,
                            )
                            for _c in _ev_contracts_sorted[:3]:
                                _label_ko = bookmaker_data._translate_threshold_label(_c.get("label"))
                                _prob = f"{_c['probability_pct']}%" if _c.get("probability_pct") is not None else "-"
                                _prob_color = "#22c55e" if (_c.get("probability_pct") or 0) >= 50 else "#f87171"
                                _updated = html.escape(str(_c.get("updated_at") or "-")[:16])
                                _question_original = str(_c.get("question") or "-")
                                _question_ko = (
                                    _translation_cache.get(_question_original)
                                    or deepl_translate.translate_market_text_locally(_question_original)
                                )
                                _question_html = (
                                    f"<div style='color:#e5e7eb;font-size:17px;line-height:1.55;font-weight:700;margin-top:7px'>"
                                    f"{html.escape(_question_ko)}</div>"
                                    f"<div style='color:#9ca3af;font-size:14px;line-height:1.5;margin-top:3px'>"
                                    f"영어 원문: {html.escape(_question_original)}</div>"
                                    if _question_ko else
                                    f"<div style='color:#cbd5e1;font-size:16px;line-height:1.55;margin-top:7px'>"
                                    f"{html.escape(_question_original)}</div>"
                                )
                                _market_id = html.escape(str(_c.get("market_id") or "-"))
                                _volume = _c.get("volume_24h")
                                _volume_text = f"{_volume:,.0f}" if _volume is not None else "확인 불가"
                                _market_url = str(_c.get("url") or "")
                                _url_html = (
                                    f" · <a href='{html.escape(_market_url, quote=True)}' target='_blank' "
                                    "style='color:#93c5fd'>원문 시장</a>"
                                    if _market_url.startswith(("https://", "http://")) else ""
                                )
                                _contract_rows.append(
                                    "<div style='padding:12px 0;border-bottom:1px solid #2a2f3a'>"
                                    "<div style='display:flex;justify-content:space-between;gap:12px;font-size:18px;font-weight:800'>"
                                    f"<span style='color:#e2e8f0'>{html.escape(str(_label_ko))}</span>"
                                    f"<span style='white-space:nowrap;color:{_prob_color}'>{_prob}</span>"
                                    "</div>"
                                    f"{_question_html}"
                                    f"<div style='color:#7f8998;font-size:13px;line-height:1.5;margin-top:5px'>시장 ID {_market_id} · "
                                    f"24시간 거래량 {_volume_text} · 갱신 {_updated}{_url_html}</div>"
                                    "</div>"
                                )
                            st.markdown(
                                "<div style='background:#171a21;border:1px solid #303642;border-radius:8px;"
                                f"padding:18px 20px;margin-bottom:16px'>{_title_html}{_meta}"
                                f"<div style='margin-top:12px'>{''.join(_contract_rows)}</div></div>",
                                unsafe_allow_html=True,
                            )
                        except Exception:
                            st.caption(f"[{_ev.get('source', '-')}] 카드 표시 실패 — 건너뜁니다.")
                            continue
                st.caption("확률은 각 계약의 Yes 확률이며 매수·매도 추천이 아닙니다.")
            elif not _bookmaker_snapshot.get("errors"):
                st.caption("현재 거시경제 관련 활성 시장을 찾지 못했습니다.")
    # 2026-07-15 사용자 요청으로 수동 메모 입력칸 삭제(자동 조회 결과만 참고, 손으로
    # 다시 옮겨 적을 필요 없음). 저장하는 값이 아니었으므로 삭제해도 손실 없음.

    # 2026-07-13 사용자 요청으로 KOSPI/코스닥/달러원/나스닥100선물/SOXX·SMH 요약 스트립 제거
    # — 위 차트 카드(가격+스파크라인)와 정보가 중복된다는 지적. _render_kr_market_mood_strip()
    # 함수 자체는 다른 곳에서 쓸 수도 있어 남겨두고 호출만 뺀다.
    st.markdown("<div style='font-size:19px;line-height:1.65;font-weight:800;margin-top:40px;margin-bottom:14px'>시장 주요 뉴스 후보</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin-bottom:22px'>네이버 뉴스 검색 결과를 중복 제거한 참고 후보이며 시장 전체를 대표하지 않습니다.</div>", unsafe_allow_html=True)
    if not result["news"] and result.get("news_failed"):
        st.markdown("<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin-bottom:18px'>시장 주요 뉴스 후보: 확인 불가</div>", unsafe_allow_html=True)
    for item in result["news"][:3]:
        hostname = urlparse(str(item.get("originallink") or item.get("link") or "")).hostname
        link = item.get("originallink") or item.get("link")
        title = item.get("title") or "-"
        title_html = html.escape(title)
        title_markdown = f"<a href='{html.escape(str(link), quote=True)}' target='_blank'>{title_html}</a>" if link else title_html
        st.markdown(f"<div style='font-size:19px;line-height:1.65;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:18px 0 6px'>• {title_markdown}</div>", unsafe_allow_html=True)
        source = f" · 원문 도메인: {hostname}" if hostname else ""
        st.markdown(f"<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin-bottom:18px'>{item.get('pub_date') or '-'}{source}</div>", unsafe_allow_html=True)
    if len(result["news"]) > 3:
        with st.expander("시장 주요 뉴스 후보 더 보기", expanded=False):
            for item in result["news"][3:10]:
                link = item.get("originallink") or item.get("link")
                title = item.get("title") or "-"
                title_html = html.escape(title)
                title_markdown = f"<a href='{html.escape(str(link), quote=True)}' target='_blank'>{title_html}</a>" if link else title_html
                hostname = urlparse(str(link or "")).hostname
                source = f" · 원문 도메인: {hostname}" if hostname else ""
                st.markdown(f"<div style='font-size:19px;line-height:1.65;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:18px 0 6px'>• {title_markdown}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin-bottom:18px'>{item.get('pub_date') or '-'}{source}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin-top:22px'>최신 조회 {st.session_state.get(checked_key) or '-'} · 뉴스는 자동 반복 갱신이 아닌 조회 시점의 검색 결과 · 발행시각은 한국시간 기준</div>", unsafe_allow_html=True)
    next_step = (
        "다음에는 아래의 0단계 시장 분위기 자동 확인과 ① 오늘 주가 자동 채우기를 진행하세요."
        if market == "KR"
        else "다음에는 아래에서 미국장 시장 분위기와 테마를 확인한 뒤 ① 미국장 기본 종목 불러오기를 진행하세요."
    )
    st.markdown(f"<div style='font-size:18px;line-height:1.7;color:#CBD5E1;margin:24px 0 40px'>{next_step}</div>", unsafe_allow_html=True)


def _get_snapshot_value(ticker, field):
    """아직 위젯이 생성되기 전이라도, session_state에 있는 현재 입력값을 미리 읽는다.

    "계산 결과 요약표"를 "종목별 상세 입력 카드"보다 화면 위쪽에 배치하기 위한 방법이다.
    (Streamlit 위젯 값은 key로 session_state에 남으므로, 위젯 호출 순서와 무관하게
    같은 key로 먼저 읽을 수 있다.)
    """
    return st.session_state.get(f"snap_{ticker}_{field}", 0.0)


def _parse_snapshot_number(text):
    """쉼표 포함 숫자 문자열("309,000")을 float로 변환한다. 실패하면 None."""
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_quick_snapshot_text(text):
    """"종목명 / 현재가 / 전일종가 / 시가 / 장중고가 / 장중저가 / 거래대금 / 시가총액" 줄을 파싱한다.

    등록된 7개 종목명과 일치하는 줄만 반영한다. 모르는 종목명이나 숫자로 해석할 수 없는
    값은 경고 문자열로만 남기고(자동판정/저장과 무관), 해당 줄은 반영하지 않는다.

    기존 8개 필드(종목명 포함) 형식을 그대로 지원하고(거래량 없이도 동작), 맨 뒤에
    거래량을 추가한 9개 필드 형식도 함께 지원한다(선택 사항, 기존 형식은 깨지지 않는다).
    """
    updates = {}
    warnings = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("/")]
        if len(parts) not in (8, 9):
            warnings.append(f"형식을 인식하지 못했습니다(종목명 포함 8개 또는 9개 필드 필요): {line}")
            continue
        name = parts[0]
        ticker = SNAPSHOT_NAME_TO_TICKER.get(name)
        if not ticker:
            warnings.append(f"'{name}'은(는) 등록된 7개 종목이 아니라 건너뜁니다.")
            continue
        # 9개 필드면 거래량까지, 8개 필드면 기존 7개 필드까지만 사용한다(하위 호환).
        fields_to_use = SNAPSHOT_FIELDS if len(parts) == 9 else SNAPSHOT_FIELDS[:-1]
        values = {}
        line_ok = True
        for field, raw in zip(fields_to_use, parts[1:]):
            num = _parse_snapshot_number(raw)
            if num is None:
                warnings.append(f"'{name}'의 값 '{raw}'을(를) 숫자로 인식하지 못했습니다.")
                line_ok = False
                break
            values[field] = num
        if line_ok:
            updates[ticker] = values
    return updates, warnings


def _fragment_scoped_rerun():
    """`@st.fragment` 안에서 클릭 등으로 발생한 rerun을 가능하면 그 프래그먼트로만 좁힌다.

    st.rerun()을 scope 없이 그냥 부르면 fragment 안에서 호출해도 항상 전체 앱을
    다시 실행한다(Streamlit 기본값 scope="app" — streamlit.commands.execution_control.rerun
    실측 확인). 반면 scope="fragment"는 "지금 진짜로 fragment-scoped rerun이 진행
    중일 때"만 허용되는데, 이는 클릭한 위젯이 프론트엔드에서 fragment_id와 함께
    전달됐을 때만 성립한다 — AppTest는 이 경로를 제대로 재현하지 못해(예: st.dataframe
    행 선택을 흉내 낼 방법이 없음) 예전 세션에서 "플랫폼 제약"으로 오판했었다.
    실제 배포(진짜 브라우저 클릭)에서는 성립할 가능성이 높으므로, 여기서 먼저
    scope="fragment"를 시도하고, 조건이 안 맞으면(StreamlitAPIException) 기존과
    동일하게 전체 rerun으로 안전하게 되돌아간다 — 실패해도 동작은 항상 이전과 같다.
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        st.rerun()


def _safe_pct_diff(a, b):
    """(a-b)/b*100. b가 0/None이면 None(계산 불가)."""
    if not b:
        return None
    return (a - b) / b * 100


def _safe_ratio_pct(a, b):
    """a/b*100. b가 0/None이면 None(계산 불가)."""
    if not b:
        return None
    return a / b * 100


def _parse_price_number(value):
    """숫자(float/int) 또는 쉼표 포함 숫자 문자열("71,500")을 float로 변환한다.
    비어 있거나(None/빈 문자열) 0이거나 변환 실패하면 None(계산 생략으로 취급).
    NaN/Infinity/-Infinity도 None으로 취급한다 — bool(float('nan'))이 True라서
    기존 "0이면 None" 처리만으로는 NaN이 정상 숫자처럼 통과했다."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        if not math.isfinite(num):
            return None
        return num if num else None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if not math.isfinite(num):
        return None
    return num if num else None


def compute_price_vs_open_pct(current_price, open_price):
    """시가 대비 등락률: (current_price - open_price) / open_price * 100.
    값이 없거나 open_price가 0이면 None(계산 생략, 0으로 나누기 방지)."""
    current_price = _parse_price_number(current_price)
    open_price = _parse_price_number(open_price)
    if current_price is None or not open_price:
        return None
    return (current_price - open_price) / open_price * 100


def compute_drop_from_high_pct(current_price, high_price):
    """고점 대비 밀림률(양수 = 밀린 정도): (high_price - current_price) / high_price * 100.
    값이 없거나 high_price가 0이면 None(계산 생략, 0으로 나누기 방지)."""
    current_price = _parse_price_number(current_price)
    high_price = _parse_price_number(high_price)
    if current_price is None or not high_price:
        return None
    return (high_price - current_price) / high_price * 100


def compute_trading_value(trading_value_input, current_price, volume):
    """거래대금: 직접 입력값이 있으면 그 값을 우선 쓰고, 없으면 current_price * volume으로
    추정한다. 둘 다 없으면 None(계산 생략)."""
    trading_value_input = _parse_price_number(trading_value_input)
    if trading_value_input is not None:
        return trading_value_input
    current_price = _parse_price_number(current_price)
    volume = _parse_price_number(volume)
    if current_price is None or volume is None:
        return None
    return current_price * volume


def compute_trading_value_to_market_cap_pct(trading_value, market_cap):
    """시총 대비 거래대금 비율: trading_value / market_cap * 100.
    값이 없거나 market_cap이 0이면 None(계산 생략, 0으로 나누기 방지)."""
    trading_value = _parse_price_number(trading_value)
    market_cap = _parse_price_number(market_cap)
    if trading_value is None or not market_cap:
        return None
    return trading_value / market_cap * 100


def _render_snapshot_calc_summary(ticker):
    """종목별 상세 입력 카드 안에서, 현재 입력값 기준 계산값(시가 대비/고점 대비 밀림/거래대금/
    시총 대비 거래대금)을 표시한다. 화면 표시 전용이며 DB에는 저장하지 않는다. 값이 비어 있으면
    (open_price/high_price/market_cap이 0이거나 없음) 해당 항목은 건너뛴다."""
    current = _get_snapshot_value(ticker, "current")
    open_price = _get_snapshot_value(ticker, "open")
    high = _get_snapshot_value(ticker, "high")
    turnover_input = _get_snapshot_value(ticker, "turnover")
    volume = _get_snapshot_value(ticker, "volume")
    market_cap = _get_snapshot_value(ticker, "market_cap")

    price_vs_open_pct = compute_price_vs_open_pct(current, open_price)
    drop_from_high_pct = compute_drop_from_high_pct(current, high)
    trading_value = compute_trading_value(turnover_input, current, volume)
    trading_value_to_market_cap_pct = compute_trading_value_to_market_cap_pct(trading_value, market_cap)

    lines = []
    if price_vs_open_pct is not None:
        lines.append(f"시가 대비: {price_vs_open_pct:+.2f}%")
    if drop_from_high_pct is not None:
        lines.append(f"고점 대비 밀림: {drop_from_high_pct:.2f}%")
    if trading_value is not None:
        lines.append(f"거래대금: {trading_value:,.0f}원")
    if trading_value_to_market_cap_pct is not None:
        lines.append(f"시총 대비 거래대금: {trading_value_to_market_cap_pct:.2f}%")

    if lines:
        st.caption(" · ".join(lines))


def _render_risk_and_warning_inputs(ticker, market, compact=False):
    """v1.1 리스크 엔진 + 청산 계획 + 경고형 확정 차단 입력/표시.

    화면 표시 계산(risk_amount/recommended_qty 등)은 저장하지 않는다. entry_price/stop_loss_price
    등 사용자가 입력한 값만 저장 대상이 된다(저장 시점에 items_to_save에 포함). compact=False는
    기존 한국장·미국장 종목별 상세 입력 카드 표시를 그대로 유지한다.
    """
    prefix = f"snap_{ticker}_"
    current = _get_snapshot_value(ticker, "current")
    high = _get_snapshot_value(ticker, "high")
    low = _get_snapshot_value(ticker, "low")
    prev_close = _get_snapshot_value(ticker, "prev_close")

    # entry_price 기본값은 current_price를 계속 따라가되, 사용자가 진입가를 직접 수정하면
    # 그 뒤로는 current_price가 바뀌어도 따라가지 않는다(아직 "직접 수정 전"인지는
    # 마지막 자동입력값과 현재 entry_price가 같은지로 판단한다).
    entry_key = prefix + "entry_price"
    auto_track_key = prefix + "entry_price_auto_track"
    if entry_key not in st.session_state or st.session_state.get(auto_track_key) == st.session_state[entry_key]:
        st.session_state[entry_key] = current
        st.session_state[auto_track_key] = current

    if compact:
        st.markdown("#### 리스크 관리")
        st.markdown(
            """
            <style>
            .st-key-mockup1_detail_panel [data-testid="stNumberInput"] label,
            .st-key-mockup1_detail_panel [data-testid="stNumberInput"] label p {
                font-size: 18px !important;
                font-weight: 700 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        rc1, rc2, rc3 = st.columns(3)
        entry_price = rc1.number_input(
            "진입가", min_value=0.0, step=100.0, key=prefix + "entry_price"
        )
        # 2026-07-15 사용자 3번째 지적: 19px로는 여전히 작다고 해서 2배(38px)로,
        # 색도 회색 계열 대신 눈에 띄는 초록으로 바꾼다.
        rc1.markdown(
            f"<div style='font-size:38px;color:#4ade80;font-weight:800'>{entry_price:,.0f}</div>"
            if entry_price else
            "<div style='font-size:16px;color:#8b95a5'>아직 입력 안 함</div>",
            unsafe_allow_html=True,
        )
        stop_loss_price = rc2.number_input(
            "손절가", value=0.0, min_value=0.0, step=100.0, key=prefix + "stop_loss_price"
        )
        rc2.markdown(
            f"<div style='font-size:38px;color:#f87171;font-weight:800'>{stop_loss_price:,.0f}</div>"
            if stop_loss_price else
            "<div style='font-size:16px;color:#8b95a5'>아직 입력 안 함(자동 계산 안 됨, 직접 입력 필요)</div>",
            unsafe_allow_html=True,
        )

        account_size = st.session_state.get("risk_account_size", 0.0)
        risk_percent = st.session_state.get("risk_percent_setting", 1.0)
        risk = _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price)
        if risk["recommended_qty"] is None:
            qty_display = "손절가 입력 후 계산" if not stop_loss_price else "-"
        else:
            qty_display = f"{risk['recommended_qty']:,}주"
        rc3.metric("권장 수량", qty_display)
        if risk["recommended_qty"] is not None:
            cap_note = " (계좌 25% 상한 적용)" if risk["capped"] else ""
            rc3.caption(f"권장 매수금액: {risk['recommended_buy_amount']:,.0f}{cap_note}")
        if risk["error"]:
            st.warning(risk["error"])
        if risk["warning"]:
            st.warning(risk["warning"])

        # 공통 설정 위젯(risk_account_size 등)은 전역 키라 한 페이지에 한 번만 만들 수
        # 있다 — 한국장 목업이 항상 먼저 렌더링하므로 KR에서만 생성하고, 미국장 목업
        # (2026-07-15 추가)에서는 안내만 표시한다(값은 같은 세션 키를 공유).
        if market == "KR":
            with st.expander("리스크 관리 공통 설정", expanded=False):
                st.caption(
                    "계좌금액/1회 리스크%는 한국장·미국장 권장 수량 계산에 공통으로 쓰입니다. "
                    "자동매매가 아니라 화면 표시용 참고 계산입니다."
                )
                r1, r2, r3 = st.columns(3)
                r1.number_input(
                    "계좌금액", value=0.0, min_value=0.0, step=1000000.0, key="risk_account_size"
                )
                r2.number_input(
                    "1회 리스크(%)", value=1.0, min_value=0.0, max_value=2.0, step=0.1,
                    key="risk_percent_setting",
                )
                today_loss_r = r3.number_input(
                    "금일 손실R (수동 입력)", value=0.0, step=0.1, key="risk_today_loss_r"
                )
                if today_loss_r <= -2:
                    st.error("금일 신규 판단 중지 - 당일 손실 -2R 도달")
        else:
            st.caption("계좌금액/1회 리스크% 공통 설정은 ① 한국장 판단 탭의 종목 판단 미리보기에서 변경합니다.")

        with st.expander("청산 계획", expanded=False):
            ec1, ec2, ec3 = st.columns(3)
            ec1.number_input(
                "계획 손절가", value=0.0, min_value=0.0, step=100.0,
                key=prefix + "planned_stop_price",
            )
            ec2.number_input(
                "목표가", value=0.0, min_value=0.0, step=100.0, key=prefix + "target_price"
            )
            ec3.number_input(
                "예상 보유일수", value=0, min_value=0, step=1,
                key=prefix + "expected_holding_days",
            )

        with st.expander("경고·확정 차단", expanded=False):
            wc1, wc2, wc3 = st.columns(3)
            disclosure_type = wc1.selectbox(
                "공시 유형", ["없음", "수주", "기타"], key=prefix + "disclosure_type"
            )
            news_status = wc2.selectbox(
                "뉴스 확인 상태", ["있음", "없음확인", "확인실패", "루머테마"],
                key=prefix + "news_status",
            )
            five_day_change_pct = wc3.number_input(
                "5일 등락률(%)", value=0.0, min_value=0.0, step=1.0,
                key=prefix + "five_day_change_pct",
            )

            daily_change_pct = _safe_pct_diff(current, prev_close)
            retracement_ratio = _compute_retracement_ratio(high, low, current)
            if _check_disclosure_chase_warning(
                disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio
            ):
                suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
                st.error(f"수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지{suffix}")
            if _check_no_news_chase_warning(
                news_status, daily_change_pct, five_day_change_pct, retracement_ratio
            ):
                suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
                st.error(f"무뉴스 급등 - 반전 위험, 추격 금지{suffix}")
        return

    st.markdown("**리스크 관리 (v1.1)**")
    rc1, rc2 = st.columns(2)
    entry_price = rc1.number_input(
        "진입가(기본값=현재가)", min_value=0.0, step=100.0, key=prefix + "entry_price"
    )
    stop_loss_price = rc2.number_input(
        "손절가", value=0.0, min_value=0.0, step=100.0, key=prefix + "stop_loss_price"
    )

    account_size = st.session_state.get("risk_account_size", 0.0)
    risk_percent = st.session_state.get("risk_percent_setting", 1.0)
    risk = _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price)
    if risk["recommended_qty"] is not None:
        cap_note = " (계좌 25% 상한 적용)" if risk["capped"] else ""
        st.caption(
            f"권장 수량: {risk['recommended_qty']:,}주 / 권장 매수금액: "
            f"{risk['recommended_buy_amount']:,.0f}{cap_note}"
        )
    if risk["error"]:
        st.warning(risk["error"])
    if risk["warning"]:
        st.warning(risk["warning"])

    st.markdown("**청산 계획 (v1.1, 저장 전용)**")
    ec1, ec2, ec3 = st.columns(3)
    ec1.number_input("목표 손절가(planned)", value=0.0, min_value=0.0, step=100.0, key=prefix + "planned_stop_price")
    ec2.number_input("목표가", value=0.0, min_value=0.0, step=100.0, key=prefix + "target_price")
    ec3.number_input(
        "예상 보유일수", value=0, min_value=0, step=1, key=prefix + "expected_holding_days"
    )
    ec4, ec5 = st.columns(2)
    ec4.selectbox("계획 준수 여부", ["미입력", "예", "아니오", "부분"], key=prefix + "plan_followed")
    ec5.selectbox(
        "위반 사유", ["미입력", "손절지연", "조기매도", "복구매매", "감정매매", "뉴스변경", "기타"],
        key=prefix + "violation_reason",
    )

    st.markdown("**경고형 확정 차단 (v1.1)**")
    wc1, wc2, wc3 = st.columns(3)
    disclosure_type = wc1.selectbox("공시 유형", ["없음", "수주", "기타"], key=prefix + "disclosure_type")
    news_status = wc2.selectbox(
        "뉴스 확인 상태", ["있음", "없음확인", "확인실패", "루머테마"], key=prefix + "news_status"
    )
    five_day_change_pct = wc3.number_input(
        "5일 등락률(%)", value=0.0, min_value=0.0, step=1.0, key=prefix + "five_day_change_pct"
    )

    daily_change_pct = _safe_pct_diff(current, prev_close)
    retracement_ratio = _compute_retracement_ratio(high, low, current)
    if _check_disclosure_chase_warning(disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio):
        suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
        st.error(f"수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지{suffix}")
    if _check_no_news_chase_warning(news_status, daily_change_pct, five_day_change_pct, retracement_ratio):
        suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
        st.error(f"무뉴스 급등 - 반전 위험, 추격 금지{suffix}")


def _collect_risk_fields(ticker):
    """저장 시점에 v1.1 입력 필드 값을 세션 상태에서 모아온다(화면 표시 계산값은 포함하지 않음)."""
    prefix = f"snap_{ticker}_"
    plan_followed = st.session_state.get(prefix + "plan_followed", "미입력")
    violation_reason = st.session_state.get(prefix + "violation_reason", "미입력")
    return {
        "entry_price": st.session_state.get(prefix + "entry_price") or None,
        "stop_loss_price": st.session_state.get(prefix + "stop_loss_price") or None,
        "planned_stop_price": st.session_state.get(prefix + "planned_stop_price") or None,
        "target_price": st.session_state.get(prefix + "target_price") or None,
        "expected_holding_days": st.session_state.get(prefix + "expected_holding_days") or None,
        "plan_followed": None if plan_followed == "미입력" else plan_followed,
        "violation_reason": None if violation_reason == "미입력" else violation_reason,
        "disclosure_type": st.session_state.get(prefix + "disclosure_type", "없음"),
        "news_status": st.session_state.get(prefix + "news_status", "있음"),
        "five_day_change_pct": st.session_state.get(prefix + "five_day_change_pct") or None,
    }


def _fmt_pct(value):
    return "-" if value is None else f"{value:.2f}"


def _fmt_signed_pct(value):
    """부호를 명시해서 보여준다 (+3.36% / -4.92%). 브리핑 초안 문장용."""
    return "-" if value is None else f"{value:+.2f}%"


def _fmt_actual_entry_price_display(value):
    """실제 평균 체결가(REAL, NULL 허용)를 입력칸 기본값 문자열로 표시한다.

    NULL -> 빈칸. 정수 가격이면 불필요한 소수점(.0) 없이, 소수 가격이면 유효 소수만
    남기고 표시한다. 통화 기호는 붙이지 않는다.
    """
    if value is None:
        return ""
    value = float(value)
    if value == int(value):
        return f"{int(value):,}"
    text = f"{value:,.4f}".rstrip("0").rstrip(".")
    return text


def _parse_actual_entry_price_text(text):
    """실제 체결가 입력칸 문자열을 파싱한다. 반환: (price 또는 None, 에러 메시지 또는 None).

    앞뒤 공백 제거, 쉼표 제거 후 숫자로 변환한다. 빈 문자열은 (None, None)으로 반환해
    NULL 저장(미기록)을 허용한다. 숫자로 바꿀 수 없거나 0 이하/NaN/Infinity면
    (None, 에러 메시지)를 반환해 저장을 막는다(실제 DB 쓰기는 하지 않음, 파싱만).
    """
    text = (text or "").strip()
    if not text:
        return None, None
    cleaned = text.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None, f"'{text}' 값을 숫자로 변환할 수 없습니다."
    if not math.isfinite(value):
        return None, "유효한 숫자가 아닙니다(NaN/Infinity 불가)."
    if value <= 0:
        return None, "0보다 큰 값만 입력할 수 있습니다."
    return value, None


# ---- v1.2A: 청산 결과 기록 (기존 report_item 업데이트 전용, 새 report 생성 없음) ----

def _compute_result_r(entry_price, stop_loss_price, actual_exit_price):
    """R수익률 = (actual_exit_price - entry_price) / (entry_price - stop_loss_price).

    entry_price/stop_loss_price/actual_exit_price 중 하나라도 없거나(0/None),
    stop_loss_price가 entry_price보다 낮지 않으면 계산하지 않는다(None)."""
    if not entry_price or not stop_loss_price or not actual_exit_price:
        return None
    if not (stop_loss_price < entry_price):
        return None
    per_share_risk = entry_price - stop_loss_price
    if per_share_risk <= 0:
        return None
    return (actual_exit_price - entry_price) / per_share_risk


def _fmt_result_r(value):
    return "계산 불가" if value is None else f"{value:+.2f}R"


def _compute_realized_pnl(actual_entry_price, actual_exit_price, quantity, actual_fee):
    """실현손익 = (actual_exit_price - actual_entry_price) * quantity - actual_fee.

    actual_entry_price/actual_exit_price는 유한한 양수여야 하고, quantity는 bool이
    아닌 int이며 1 이상이어야 한다. actual_fee는 None이면 "미입력"을 뜻하므로 0으로
    치환하지 않고 그대로 계산 불가(None) 처리한다 — actual_fee=0은 "명시적으로 0원
    입력"이므로 정상 계산한다. 조건을 하나라도 만족하지 못하면 None을 반환한다."""
    if (
        not isinstance(actual_entry_price, (int, float))
        or isinstance(actual_entry_price, bool)
        or not math.isfinite(actual_entry_price)
        or actual_entry_price <= 0
    ):
        return None
    if (
        not isinstance(actual_exit_price, (int, float))
        or isinstance(actual_exit_price, bool)
        or not math.isfinite(actual_exit_price)
        or actual_exit_price <= 0
    ):
        return None
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None
    if actual_fee is None:
        return None
    if (
        not isinstance(actual_fee, (int, float))
        or isinstance(actual_fee, bool)
        or not math.isfinite(actual_fee)
        or actual_fee < 0
    ):
        return None
    return (actual_exit_price - actual_entry_price) * quantity - actual_fee


def _compute_realized_return_pct(realized_pnl, actual_entry_price, quantity):
    """실현수익률(%) = realized_pnl / (actual_entry_price * quantity) * 100.

    realized_pnl은 유한한 숫자여야 하고, actual_entry_price는 유한한 양수, quantity는
    bool이 아닌 int이며 1 이상이어야 한다. 분모(actual_entry_price * quantity)가 0
    이하이면 None을 반환한다."""
    if (
        not isinstance(realized_pnl, (int, float))
        or isinstance(realized_pnl, bool)
        or not math.isfinite(realized_pnl)
    ):
        return None
    if (
        not isinstance(actual_entry_price, (int, float))
        or isinstance(actual_entry_price, bool)
        or not math.isfinite(actual_entry_price)
        or actual_entry_price <= 0
    ):
        return None
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None
    denominator = actual_entry_price * quantity
    if denominator <= 0:
        return None
    return realized_pnl / denominator * 100


def _normalize_to_date(value):
    """문자열("YYYY-MM-DD")/date/datetime을 date로 정규화한다. 실패 시 None.

    datetime.datetime은 datetime.date의 하위 클래스이므로 datetime 인스턴스를 먼저
    검사해 .date()로 시각 정보를 제거한 뒤, 순수 date 인스턴스를 그대로 받아들인다."""
    from datetime import date as _date_cls

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, _date_cls):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _compute_holding_days(actual_entry_date, actual_exit_date):
    """보유일(달력일) = actual_exit_date - actual_entry_date.

    둘 다 "YYYY-MM-DD" 문자열/date/datetime 중 하나를 받아 date로 정규화한다. 정규화에
    실패하거나 None이면 계산 불가(None). 매도일이 매수일보다 빠르면 None(미청산/오류
    방지, 음수 보유일 차단). 같은 날이면 0을 반환한다(정상). 거래일이 아닌 달력일
    기준이며, 2차 과제인 거래일 계산은 이 함수의 범위가 아니다."""
    entry = _normalize_to_date(actual_entry_date)
    exit_ = _normalize_to_date(actual_exit_date)
    if entry is None or exit_ is None:
        return None
    if exit_ < entry:
        return None
    return (exit_ - entry).days


def _compute_verification_status(actual_exit_price, actual_exit_date):
    """실제 청산가/청산일 입력 여부만으로 검증 상태를 정한다(가격/일자 둘 다 있으면 입력완료,
    하나만 있으면 계산불가, 둘 다 없으면 미입력)."""
    has_price = bool(actual_exit_price)
    has_date = bool(actual_exit_date)
    if has_price and has_date:
        return "입력완료"
    if has_price or has_date:
        return "계산불가"
    return "미입력"


# ---- v1.2B: 필터 무시 매매 로그 (기존 report_item 업데이트 전용, 새 report 생성 없음) ----
# 화면에는 한국어로 표시하고, DB(filter_ignore_reason)에는 고정 코드를 콤마로 연결해 저장한다.
FILTER_IGNORE_TAG_OPTIONS = [
    ("NO_STOP", "손절없음"),
    ("STOP_DELAY", "손절지연"),
    ("UNCONFIRMED_ENTRY", "미확정진입"),
    ("PENALTY_IGNORED", "감점무시"),
    ("WARNING_IGNORED", "경고무시"),
    ("NEWS_IMPULSE", "뉴스충동"),
    ("RECOMMEND_BUY", "추천매수"),
    ("REVENGE_TRADE", "복구매매"),
    ("CHASE_BUY", "추격매수"),
    ("SIZE_OVER", "비중초과"),
    ("TAKE_PROFIT_DELAY", "익절지연"),
    ("EARLY_EXIT", "조기매도"),
]
FILTER_IGNORE_TAG_CODE_TO_LABEL = dict(FILTER_IGNORE_TAG_OPTIONS)
FILTER_IGNORE_TAG_LABEL_TO_CODE = {v: k for k, v in FILTER_IGNORE_TAG_OPTIONS}

EMOTION_TAG_OPTIONS = [
    ("EMOTION_CALM", "평온"),
    ("EMOTION_EXCITED", "흥분"),
    ("EMOTION_REVENGE", "복구욕"),
    ("EMOTION_ANXIOUS", "불안"),
]
EMOTION_TAG_CODE_TO_LABEL = dict(EMOTION_TAG_OPTIONS)
EMOTION_TAG_LABEL_TO_CODE = {v: k for k, v in EMOTION_TAG_OPTIONS}

# 플레이북 태그: 이 매매가 어떤 전략/셋업이었는지 기록하는 순수 분류 태그다. 수주공시추격금지/
# 뉴스충동매매/복구매매/손절지연처럼 경고·실수 성격의 개념은 여기 넣지 않고 filter_ignore_reason
# 쪽(FILTER_IGNORE_TAG_OPTIONS)에 남겨둔다.
PLAYBOOK_TAG_OPTIONS = [
    ("US_EARNINGS_SWING", "미국실적스윙"),
    ("KR_BUYBACK_SWING", "자사주스윙"),
    ("LEADER_LAGGARD_DAYTRADE", "1등주2등주단타"),
    ("RECOMMEND_BUY_SETUP", "추천매수셋업"),
    ("OTHER_SETUP", "기타셋업"),
    ("THEME_LEADER", "테마-대장주"),
    ("THEME_SECOND", "테마-2등주"),
    ("THEME_THIRD_OR_LOWER", "테마-3등이하"),
]
PLAYBOOK_TAG_CODE_TO_LABEL = dict(PLAYBOOK_TAG_OPTIONS)
PLAYBOOK_TAG_LABEL_TO_CODE = {v: k for k, v in PLAYBOOK_TAG_OPTIONS}

# 종목별 테마 태그 선택지: 한국장 "오늘 강세 테마 1차 참고판"과 미국장 "테마 레이더 1차 참고판"에
# 이미 있는 테마 이름을 그대로 재사용한 목록이다(중복 문자열은 하나로 합침, 정렬해서 표시).
# 이 상수는 저장/점수/판단에 반영되지 않는 단순 기록용 선택지이며, 두 테마 참고판 코드 자체는
# 건드리지 않는다.
THEME_TAG_OPTIONS = sorted(
    {
        "반도체/HBM", "전력기기/전력망", "원전", "방산", "조선/해운", "자동차/부품",
        "2차전지", "바이오", "AI/로봇", "정유/화학",
        "AI/반도체", "금리/성장주", "전력망/원전", "방산/전쟁", "에너지/유가", "자동차/전기차",
    }
)


def _fetch_filter_compliance_stats():
    """전체 report_items에서 필터 준수/무시별 평균 R수익률을 계산한다(화면 표시 전용, 저장 없음).

    result_r이 NULL이거나 숫자로 변환할 수 없는 행은 평균 계산에서 제외한다."""
    conn = db.get_connection()
    rows = conn.execute("SELECT filter_ignored, result_r FROM report_items").fetchall()
    conn.close()

    ignored_count = 0
    followed_count = 0
    unset_count = 0
    ignored_r_values = []
    followed_r_values = []
    for row in rows:
        flag = row["filter_ignored"]
        if flag == "YES":
            ignored_count += 1
        elif flag == "NO":
            followed_count += 1
        else:
            unset_count += 1

        try:
            r_num = float(row["result_r"]) if row["result_r"] is not None else None
        except (TypeError, ValueError):
            r_num = None
        if r_num is None:
            continue
        if flag == "YES":
            ignored_r_values.append(r_num)
        elif flag == "NO":
            followed_r_values.append(r_num)

    return {
        "ignored_count": ignored_count,
        "followed_count": followed_count,
        "unset_count": unset_count,
        "ignored_avg_r": (sum(ignored_r_values) / len(ignored_r_values)) if ignored_r_values else None,
        "followed_avg_r": (sum(followed_r_values) / len(followed_r_values)) if followed_r_values else None,
        "comparable_n": len(ignored_r_values) + len(followed_r_values),
    }


def _fmt_avg_r(value):
    return "데이터 없음" if value is None else f"{value:+.2f}R"


def _n_confidence_label(n):
    if n < 30:
        return "미검증"
    if n < 50:
        return "참고"
    return "검토 가능"


def _fetch_worst_trades(limit=5):
    """전체 report_items에서 result_r이 숫자로 변환 가능한 행만 모아 낮은(손실이 큰) 순으로
    정렬해 상위 N개를 반환한다. 화면 표시 전용이며 계산/저장 로직에는 영향을 주지 않는다."""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT stock_name, ticker, trade_mode, result_r, actual_exit_date, exit_reason, filter_ignored "
        "FROM report_items WHERE result_r IS NOT NULL"
    ).fetchall()
    conn.close()

    parsed = []
    for row in rows:
        try:
            r_num = float(row["result_r"])
        except (TypeError, ValueError):
            continue
        parsed.append(
            {
                "종목명": row["stock_name"] or "-",
                "티커": row["ticker"] or "-",
                "매매유형": row["trade_mode"] or "-",
                "result_r": r_num,
                "청산일": row["actual_exit_date"] or "-",
                "청산사유": row["exit_reason"] or "-",
                "필터무시여부": {"YES": "예", "NO": "아니오"}.get(row["filter_ignored"], "미입력"),
            }
        )
    parsed.sort(key=lambda d: d["result_r"])
    total_n = len(parsed)
    worst_rows = parsed[:limit]
    avg_worst = (sum(d["result_r"] for d in worst_rows) / len(worst_rows)) if worst_rows else None
    lowest = worst_rows[0]["result_r"] if worst_rows else None
    return {"total_n": total_n, "worst_rows": worst_rows, "avg_worst": avg_worst, "lowest": lowest}


def _fetch_open_risk_positions():
    """실제 매수해서 아직 청산하지 않은 포지션들의 총 오픈 리스크를 R 단위로 낸다.

    화면 표시 전용이며 계산/저장 로직에는 영향을 주지 않는다. planned_stop_price와 buy_confirmed는
    이번 계산 기준에 쓰지 않는다(buy_confirmed는 현재 신뢰 가능한 값이 아님).

    R 정의는 _compute_result_r과 동일하게 "위험폭 대비 배수"로 맞춘다: 계좌금액×1회 리스크%로
    1R 금액을 구하고, 각 포지션의 실제 위험액(수량×(진입가-손절가))을 1R 금액으로 나눈 값을
    그 포지션의 R로 본다. entry_price - stop_loss_price를 그대로 더하던 예전 방식은 화폐 단위가
    섞이고(원/달러) 수량을 반영하지 못해 실제 R이 아니었다 — 이번에 정정한다.

    실제로 매수하지 않은 행(actual_action != '매수')은 계획 단계일 뿐 실제 오픈 포지션이
    아니므로 제외한다.
    """
    account_size = st.session_state.get("risk_account_size", 0.0) or 0.0
    risk_percent = st.session_state.get("risk_percent_setting", 1.0) or 0.0
    one_r_amount = account_size * risk_percent / 100

    conn = db.get_connection()
    rows = conn.execute(
        "SELECT stock_name, ticker, trade_mode, entry_price, stop_loss_price, quantity, "
        "filter_ignored, actual_action FROM report_items WHERE actual_exit_price IS NULL"
    ).fetchall()
    conn.close()

    if one_r_amount <= 0:
        return {
            "positions": [],
            "count": 0,
            "total_risk": None,
            "excluded_count": 0,
            "needs_account_setting": True,
        }

    positions = []
    excluded_count = 0
    for row in rows:
        if db.normalize_actual_action(row["actual_action"]) != "매수":
            continue
        try:
            entry = float(row["entry_price"]) if row["entry_price"] is not None else None
            stop = float(row["stop_loss_price"]) if row["stop_loss_price"] is not None else None
            qty = float(row["quantity"]) if row["quantity"] is not None else None
        except (TypeError, ValueError):
            entry = None
            stop = None
            qty = None
        if entry is None or stop is None or qty is None or not (stop < entry) or qty <= 0:
            excluded_count += 1
            continue
        position_risk_amount = qty * (entry - stop)
        positions.append(
            {
                "종목명": row["stock_name"] or "-",
                "티커": row["ticker"] or "-",
                "매매유형": row["trade_mode"] or "-",
                "진입가": entry,
                "손절가": stop,
                "수량": qty,
                "1건 위험": position_risk_amount / one_r_amount,
                "필터무시여부": {"YES": "예", "NO": "아니오"}.get(row["filter_ignored"], "미입력"),
            }
        )
    total_risk = sum(p["1건 위험"] for p in positions)
    return {
        "positions": positions,
        "count": len(positions),
        "total_risk": total_risk,
        "excluded_count": excluded_count,
        "needs_account_setting": False,
    }


def _open_risk_status_label(count, total_risk):
    if count == 0 or total_risk is None:
        return "데이터 없음"
    if total_risk < 1:
        return "낮음"
    if total_risk < 3:
        return "주의"
    return "위험"


# ---- v1.1: 리스크 엔진 / 경고형 확정 차단 / 입력 검증 (한국장·미국장 "바로 저장" 전용) ----
# 점수 가점/감점 로직과는 무관하며, 여기서 계산되는 값은 화면 표시/경고 문구 전용이다.
# 한국장/미국장 바로 저장은 이미 모든 항목을 "미확정"으로만 저장하므로(기존 동작), 별도의
# 확정 상태 차단 로직은 필요 없고 경고 문구를 눈에 띄게 보여주는 것으로 "확정 차단"을 만족한다.

def _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price):
    """계좌금액/리스크% 기준 권장 수량을 계산한다. 화면 표시 전용이며 저장하지 않는다."""
    result = {
        "risk_amount": None,
        "per_share_loss": None,
        "recommended_qty": None,
        "recommended_buy_amount": None,
        "capped": False,
        "error": None,
        "warning": None,
    }
    if not account_size or not entry_price:
        return result

    risk_amount = account_size * risk_percent / 100
    result["risk_amount"] = risk_amount

    if not stop_loss_price:
        result["error"] = "손절가 없음 - 매수 확정 불가"
        return result

    per_share_loss = entry_price - stop_loss_price
    result["per_share_loss"] = per_share_loss

    if stop_loss_price >= entry_price or per_share_loss <= 0:
        result["error"] = "손절가는 진입가보다 낮아야 합니다"
        return result

    recommended_qty = math.floor(risk_amount / per_share_loss)
    recommended_buy_amount = recommended_qty * entry_price

    if recommended_buy_amount > account_size * 0.25:
        recommended_qty = math.floor((account_size * 0.25) / entry_price)
        recommended_buy_amount = recommended_qty * entry_price
        result["capped"] = True

    result["recommended_qty"] = recommended_qty
    result["recommended_buy_amount"] = recommended_buy_amount

    stop_pct = per_share_loss / entry_price
    if stop_pct > 0.08:
        result["warning"] = "손절폭 8% 초과 - 수량 축소 또는 보류 권고"

    return result


def _compute_retracement_ratio(high_price, low_price, current_price):
    """고점 대비 되돌림 비율: (high-current)/(high-low). 변동폭이 현재가의 1% 미만이면
    계산을 건너뛴다(None)."""
    if not high_price or not low_price or current_price is None:
        return None
    price_range = high_price - low_price
    if price_range <= 0 or price_range < current_price * 0.01:
        return None
    return (high_price - current_price) / price_range


def _is_surge_condition(daily_change_pct, five_day_change_pct):
    """급등 조건: 당일 등락률 10% 이상 또는 5일 등락률 15% 이상."""
    if daily_change_pct is not None and daily_change_pct >= 10:
        return True
    if five_day_change_pct is not None and five_day_change_pct >= 15:
        return True
    return False


def _check_disclosure_chase_warning(disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio):
    """경고1: 수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지."""
    if disclosure_type != "수주":
        return False
    if not _is_surge_condition(daily_change_pct, five_day_change_pct):
        return False
    return retracement_ratio is not None and retracement_ratio >= 0.5


def _check_no_news_chase_warning(news_status, daily_change_pct, five_day_change_pct, retracement_ratio):
    """경고2: 무뉴스/루머 급등 - 반전 위험, 추격 금지."""
    if news_status not in ("없음확인", "루머테마"):
        return False
    if not _is_surge_condition(daily_change_pct, five_day_change_pct):
        return False
    return retracement_ratio is not None and retracement_ratio >= 0.5


def _validate_snapshot_price_inputs(name, current, open_price, high, low, volume, turnover):
    """가격/거래량/거래대금 입력값 검증(작업5). 위반 사유 문자열 목록을 반환(빈 목록=정상).

    NaN/Infinity/-Infinity는 먼저 명시적 오류로 걸러낸다. 이렇게 걸러진 값은 이후
    음수·가격 관계 비교에서 None과 동일하게(검증 대상에서 제외) 취급해 같은 값이
    "비정상 숫자"와 "음수"/"관계 오류"로 중복 표시되지 않게 한다. 기존 0/None/미입력
    처리 방식과 기존 가격 관계·음수 거래량 검증 로직 자체는 그대로 유지한다."""
    errors = []
    fields = (
        ("현재가", current), ("시가", open_price), ("고가", high), ("저가", low),
        ("거래량", volume), ("거래대금", turnover),
    )
    cleaned = {}
    for label, value in fields:
        if value is None:
            cleaned[label] = None
            continue
        try:
            is_finite = math.isfinite(value)
        except TypeError:
            is_finite = False
        if not is_finite:
            errors.append(f"{name}: {label}가 비정상 숫자입니다(NaN/Infinity)")
            cleaned[label] = None
        else:
            cleaned[label] = value
    current = cleaned["현재가"]
    open_price = cleaned["시가"]
    high = cleaned["고가"]
    low = cleaned["저가"]
    volume = cleaned["거래량"]
    turnover = cleaned["거래대금"]

    for label, value in (
        ("현재가", current), ("시가", open_price), ("고가", high), ("저가", low),
        ("거래량", volume), ("거래대금", turnover),
    ):
        if value is not None and value < 0:
            errors.append(f"{name}: {label}가 음수입니다")
    if high and current and not (high >= current):
        errors.append(f"{name}: 고가가 현재가보다 낮습니다")
    if low and current and not (current >= low):
        errors.append(f"{name}: 현재가가 저가보다 낮습니다")
    if high and open_price and not (high >= open_price):
        errors.append(f"{name}: 고가가 시가보다 낮습니다")
    if low and open_price and not (open_price >= low):
        errors.append(f"{name}: 시가가 저가보다 낮습니다")
    return errors


def classify_snapshot_temp(high_drop_pct, open_pos_pct, turnover_ratio_pct):
    """장중 스냅샷 계산값으로 임시 매매유형/판정을 만든다.

    자동판정이 아니라 브리핑 초안을 만들기 위한 참고용 임시 규칙이다. 실제 판정은
    사람이 브리핑 붙여넣기 탭에서 최종 확인/수정한 뒤 저장한다.
    - 고점대비 -3% 이하 -> 단타 / 보류
    - 시가대비 0% 이상 이고 시총대비 거래대금 1% 이상 -> 스윙 / 관심 후보
    - 그 외 -> 공통 / 감시
    """
    if high_drop_pct is not None and high_drop_pct <= -3:
        return "단타", "보류"
    if (
        open_pos_pct is not None
        and open_pos_pct >= 0
        and turnover_ratio_pct is not None
        and turnover_ratio_pct >= 1
    ):
        return "스윙", "관심 후보"
    return "공통", "감시"


def _reports_signature():
    return tuple(sorted(r["id"] for r in db.list_reports()))


@st.cache_data(ttl=600, show_spinner="결과 확인 데이터 조회 중 (시세 조회)...")
def _cached_verification_rows(signature):
    return performance.build_verification_rows()


@st.cache_data(ttl=600, show_spinner="오늘 관심 종목 없음 평가 조회 중 (시세 조회)...")
def _cached_no_recommendation_rows(signature):
    return performance.build_no_recommendation_rows()


PERFORMANCE_DATA_LOAD_KEY = "performance_data_load_requested"


def _render_performance_data_load_gate(button_key):
    """Keep expensive performance price lookups behind an explicit user action."""
    if st.session_state.get(PERFORMANCE_DATA_LOAD_KEY):
        return True
    st.info("성과 시세 데이터 미조회")
    st.caption("1·3·5·10·20일 성과 확인이 필요할 때만 불러옵니다. 첫 조회는 시간이 걸릴 수 있습니다.")
    if st.button("성과 시세 데이터 불러오기", key=button_key):
        st.session_state[PERFORMANCE_DATA_LOAD_KEY] = True
        st.rerun()
    return False

with tab_saved:
    _saved_view = st.radio(
        "기록 조회 화면",
        ["저장 결과", "오늘 요약", "지난 기록"],
        horizontal=True,
        key="saved_view_selector",
    )
    st.markdown("<div style='font-size:17px;line-height:1.5;color:#CBD5E1'>아래에서 오늘 요약·저장 결과·지난 기록 중 확인할 화면을 선택하세요.</div>", unsafe_allow_html=True)
if _saved_view == "오늘 요약":
    with tab_saved:
        st.subheader("오늘 저장 요약")
        st.info(
            "이 화면은 오늘 저장된 기록을 관점별로 다시 보여주는 화면입니다.\n"
            "증시 전체 요약 화면이 아닙니다.\n"
            "먼저 🇰🇷 한국장 먼저 확인 또는 🇺🇸 미국장 스윙 확인에서 계산 후 저장해야 오늘 저장 요약과 지난 기록에 반영됩니다."
        )

        latest = db.get_latest_report()
        if latest is None:
            st.info("저장된 기록이 없습니다.")
        else:
            render_report_detail(latest)

with tab_aux:
    _aux_view = st.radio(
        "보조 화면",
        ["사용법", "자비스 매매 사용법", "이 앱의 원칙", "수동 기록 입력", "추가 기능"],
        horizontal=True,
        key="aux_view_selector",
    )
    st.markdown("<div style='font-size:17px;line-height:1.5;color:#CBD5E1'>필요할 때만 수동 기록 입력·추가 기능·사용법·이 앱의 원칙·자비스 매매 사용법을 선택하세요.</div>", unsafe_allow_html=True)
if _aux_view == "자비스 매매 사용법":
    with tab_aux:
        st.subheader("자비스 하루 사용 흐름")
        st.markdown("#### 장 시작 전 (8:30~9:00)")
        st.markdown(
            "1. ① 한국장 탭에서 \"오늘 한국장 자료 불러오기\" 클릭\n"
            "   → 상태(우호/비우호)만 확인. 비우호면 오늘 신규 진입 개수를 미리 줄이겠다고 결정한다.\n"
            "2. \"테마 참고판 자동 조회\" 클릭 → 오늘 강한 테마 확인 (참고용).\n"
            "3. \"오늘 종목 판단 준비하기\" 클릭 → 1순위·관찰후보만 검토. 보류 종목은 보지 않는다."
        )
        st.markdown("#### 매수 결정할 때 (가장 중요한 순서)")
        st.markdown(
            "4. 진입가·손절가 입력 → 권장 수량 확인\n"
            "   (손절가 없으면 저장이 차단된다 — 이 차단이 나를 지키는 기능이다)\n"
            "5. 총 오픈 리스크 확인 → 3R 초과면 오늘 추가 진입 없음\n"
            "6. 청산 시나리오 한 줄 작성 → 저장 전 확인 → 최종 저장\n"
            "7. 필터가 막는데도 사고 싶다면: 무시 로그에 태그와 이유를 정직하게 남긴다. "
            "이 정직함이 나중에 내 돈을 지킨다."
        )
        st.markdown("#### 장중")
        st.markdown(
            "- 계획한 손절가에 도달하면 실행하고 ③ 행동·청산 탭에 기록\n"
            "- 새로운 충동이 생기면 먼저 자비스에 넣어본다. "
            "필터 통과 못 하면 무시 로그를 남기고 판단한다."
        )
        st.markdown("#### 장 마감 후 (10분)")
        st.markdown(
            "- ③ 탭에서 오늘 실제 행동 입력\n"
            "- ④ 탭에서 복기 대기 항목 처리"
        )
        st.markdown("#### 주말 (15분)")
        st.markdown(
            "- \"필터 준수 vs 무시 R 비교\" 확인\n"
            "- 기록 30건이 넘으면 조건별 기대값 통계를 보기 시작한다"
        )
        st.markdown("#### 이 앱이 수익에 기여하는 3가지 원리")
        st.markdown(
            "(a) 손절 강제 = 계좌를 무너뜨리는 큰 손실을 원천 차단\n\n"
            "(b) 3R 제한 = 여러 종목에 동시에 물려 한 번에 무너지는 것 방지\n\n"
            "(c) 무시 로그 = 몇 주 뒤 \"무시 매매 평균 -0.8R\" 같은 내 숫자가 "
            "의지력보다 강하게 행동을 바꾼다\n\n"
            "앱이 돈을 벌어주는 게 아니라, 새는 돈을 막는 것이다."
        )
        st.markdown("#### 테마 추격매매 규칙 (참고)")
        st.markdown(
            "- 테마 시작 신호: 테마 내 3종목 이상 동시 상승 + 대장주 거래대금 급증 "
            "+ 2~3일 연속 강세 (하루 급등은 노이즈)\n"
            "- 추격은 2등주까지만. 3등주부터 기대값이 급감하고 4등 이하는 추격주의.\n"
            "- 테마 시작 4일차부터 신규 진입은 추격주의.\n"
            "- 대장주가 고점 대비 -7~10% 꺾이면 후발주는 이유 불문 청산 (후발주는 자생력이 없다)\n"
            "- 손절: 진입 당일 저가 이탈 또는 시가 아래 확정"
        )
        st.markdown("#### 스윙매매 기준 (참고)")
        st.markdown(
            "**[한국장, 보유 2~10일]**\n"
            "- 대상: 거래대금 상위 + 20일선 위 + 고점 대비 -10% 이내\n"
            "- 진입: 강한 상승 후 얕은 눌림에서 재반등할 때. 눌림 -15% 넘으면 제외\n"
            "- 손절: 눌림 저점 이탈 = 1R\n"
            "- 청산: +2R에서 절반 익절, 나머지는 전일 저가 이탈 시\n\n"
            "**[미국장, 보유 5~20일]**\n"
            "- 한국 시간상 장중 대응 불가 → 예약 손절(stop) 주문 필수\n"
            "- 대상: 강한 섹터(ETF 조회로 확인) 내 50일선 위 + 신고가 근접 종목\n"
            "- 실적 발표 전 1주일은 신규 진입 금지 (갭 위험)"
        )
elif _aux_view == "이 앱의 원칙":
    with tab_aux:
        st.subheader("자비스가 돈을 지켜주는 방식")
        st.markdown(
            "> **이 앱의 목표는 더 좋은 종목을 찾아주는 게 아니라, "
            "나쁜 매매를 빼는 장치와 조건의 기대값을 증명하는 기록입니다.**"
        )
        st.markdown("#### 핵심 기능 6가지")
        st.markdown(
            "1. **손절 없는 매수 차단** — 치명적 손실을 원천 차단 `[적용됨]`\n"
            "2. **총 오픈 리스크 3R 제한** — 여러 종목에 동시에 물려 한 번에 무너지는 것 방지 `[적용됨]`\n"
            "3. **필터 무시 로그** — 준수 매매와 무시 매매의 실제 손익 차이를 숫자로 확인 `[적용됨]`\n"
            "4. **R·청산 기록** — 계획대로 팔았는지 감정적으로 팔았는지 사후 확인 `[적용됨]`\n"
            "5. **조건별 플레이북 태그** — 어떤 조건이 반복되는지 기록 `[적용됨]`\n"
            "   (조건별 기대값 통계는 기록 30건 이상 쌓이면 자동 활성화 예정)\n"
            "6. **탈락 종목 추적** — 필터가 너무 세서 좋은 기회를 놓치고 있진 않은지 확인 `[적용됨]`"
        )
        st.markdown("#### 하지 않기로 한 것 (원칙적으로 배제)")
        st.markdown(
            "- 예측시장 정보를 점수에 반영하는 것\n"
            "- 뉴스 키워드로 자동 가점 주는 것\n"
            "- AI 추천을 매수 신호로 직결하는 것\n"
            "- 승률만 강조하는 화면\n"
            "- 근거 없는 매수 차단 남발"
        )
elif _aux_view == "수동 기록 입력":
    with tab_aux:
        st.subheader("새 기록 입력")

        st.session_state.setdefault("form_version", 0)
        st.session_state.setdefault("draft_items", [])
        st.session_state.setdefault("item_seq", 0)

        fv = st.session_state.form_version

        with st.expander("쉽게 붙여넣는 입력칸 (입력 내용 정리)", expanded=False):
            st.caption(
                "[기본]/[오늘의 결론]/[종목] 형식으로 통째로 붙여넣고 '입력 내용 정리'를 누르면 "
                "시장·판단 시점·오늘 요약·종목별 기록이 한 번에 채워집니다. "
                "입력 형식의 '시장 범위:', '브리핑 단계:', '신호 분류:', '[오늘의 결론]' 표기는 "
                "그대로 입력해야 인식됩니다. "
                "종목 줄 구분자는 '/' 이며 세 형식을 지원합니다: "
                "6개 필드(기존) = 종목명 / 종목코드 / 시장 / 판정 / 신호 종류 / 판단 이유, "
                "7개 필드(신규, 매매유형 포함) = 종목명 / 종목코드 / 시장 / 매매유형 / 판정 / 신호 종류 / 판단 이유, "
                "13개 필드(확장, 판단 설명 포함) = 위 7개 필드 + 점수 / 점수 근거 / 1순위 후보 근거 / "
                "감점 이유 / 매수 확정 여부 / 매수 확정 조건."
            )
            quick_text = st.text_area(
                "쉽게 붙여넣는 입력칸",
                key=f"quick_text_{fv}",
                height=220,
                placeholder=(
                    "[기본]\n시장 범위: KR\n브리핑 단계: 08:30 개장 전 예측\n신호 분류: 재확인 신호\n\n"
                    "[오늘의 결론]\n...\n\n[종목]\n"
                    "삼성전자 / 005930.KS / KR / 추천 후보 / 재확인 신호 / 실적 기대\n"
                    "삼성전자 / 005930.KS / KR / 단타 / 보류(선반영) / 재확인 신호 / 장중 고점 대비 밀림"
                ),
            )
            if st.button("입력 내용 정리", key=f"quick_fill_{fv}"):
                parsed = parse_quick_text(quick_text)

                if parsed["market_scope"]:
                    st.session_state[f"market_scope_{fv}"] = parsed["market_scope"]
                if parsed["briefing_stage"]:
                    st.session_state[f"briefing_stage_{fv}"] = parsed["briefing_stage"]
                st.session_state[f"day_conclusion_{fv}"] = parsed["day_conclusion"]
                st.session_state[f"raw_briefing_{fv}"] = quick_text

                st.session_state.draft_items = []
                for item in parsed["items"]:
                    st.session_state.item_seq += 1
                    item_id = st.session_state.item_seq
                    st.session_state.draft_items.append(item_id)
                    prefix = f"item_{fv}_{item_id}_"
                    st.session_state[prefix + "event_title"] = item["event_title"]
                    st.session_state[prefix + "ticker"] = item["ticker"]
                    st.session_state[prefix + "stock_name"] = item["stock_name"]
                    st.session_state[prefix + "market"] = item["market"]
                    st.session_state[prefix + "item_timing_class"] = "(미지정)"
                    st.session_state[prefix + "trade_mode"] = item["trade_mode"]
                    st.session_state[prefix + "verdict"] = item["verdict"]
                    st.session_state[prefix + "signal_type"] = item["signal_type"]
                    st.session_state[prefix + "score"] = item["score"] or 0.0
                    st.session_state[prefix + "score_reason"] = item["score_reason"] or ""
                    st.session_state[prefix + "top_candidate_reason"] = item["top_candidate_reason"] or ""
                    st.session_state[prefix + "penalty_reason"] = item["penalty_reason"] or ""
                    st.session_state[prefix + "buy_confirmed"] = item["buy_confirmed"]
                    st.session_state[prefix + "buy_confirm_condition"] = item["buy_confirm_condition"]

                st.session_state[f"quick_fill_count_{fv}"] = len(parsed["items"])
                st.session_state[f"quick_fill_warnings_{fv}"] = parsed["warnings"]
                st.rerun()

            if st.session_state.get(f"quick_fill_count_{fv}") is not None:
                st.success(f"입력 내용 정리 완료: 종목별 기록 {st.session_state[f'quick_fill_count_{fv}']}개 생성됨")
            for w in st.session_state.get(f"quick_fill_warnings_{fv}", []):
                st.warning(w)

        st.markdown("---")

        market_scope = st.selectbox(
            "시장", db.MARKET_SCOPE_CHOICES, key=f"market_scope_{fv}"
        )
        briefing_stage = st.selectbox(
            "판단 시점", db.BRIEFING_STAGE_CHOICES, key=f"briefing_stage_{fv}"
        )
        day_conclusion = st.text_area(
            "오늘 요약",
            key=f"day_conclusion_{fv}",
            placeholder="예: 오늘은 추천 종목 없음. 관망 권장.",
        )
        raw_briefing = st.text_area(
            "판단 근거", key=f"raw_briefing_{fv}", height=200
        )
        st.caption("장 구분은 저장 시각을 기준으로 자동으로 정해집니다. 직접 입력하지 않습니다.")

        st.markdown("---")

        items_data = []
        remove_id = None
        with st.expander(
            f"고급 수동 입력 ({len(st.session_state.draft_items)}개 종목별 기록, 0개도 저장 가능)",
            expanded=False,
        ):
            st.caption("쉽게 붙여넣는 입력칸으로 자동 채운 종목도 여기서 직접 수정/추가/삭제할 수 있습니다.")

            if st.button("+ 종목별 기록 추가", key=f"add_item_{fv}"):
                st.session_state.item_seq += 1
                st.session_state.draft_items.append(st.session_state.item_seq)
                st.rerun()

            for item_id in st.session_state.draft_items:
                prefix = f"item_{fv}_{item_id}_"

                title_trade_mode = st.session_state.get(prefix + "trade_mode", "공통")
                title_stock_name = (
                    st.session_state.get(prefix + "stock_name")
                    or st.session_state.get(prefix + "ticker")
                    or f"기록 #{item_id}"
                )
                title_verdict_raw = st.session_state.get(prefix + "verdict", db.VERDICT_CHOICES[0])
                title_event = st.session_state.get(prefix + "event_title", "")
                card_title = f"{_trade_mode_badge(title_trade_mode)} {_verdict_badge(title_verdict_raw)} {title_stock_name}"
                if title_event:
                    card_title += f" - {title_event}"

                with st.expander(card_title, expanded=False):
                    header_col, del_col = st.columns([6, 1])
                    header_col.markdown(f"종목별 기록 #{item_id}")
                    if del_col.button("삭제", key=prefix + "delete"):
                        remove_id = item_id

                    c1, c2, c3 = st.columns(3)
                    event_title = c1.text_input("판단 이유", key=prefix + "event_title")
                    ticker = c2.text_input("종목코드", key=prefix + "ticker")
                    stock_name = c3.text_input("종목명", key=prefix + "stock_name")

                    c4, c5 = st.columns(2)
                    market = c4.selectbox("시장", db.ITEM_MARKET_CHOICES, key=prefix + "market")
                    item_timing_class_raw = c5.selectbox(
                        "항목 장 구분 (선택)",
                        ["(미지정)"] + db.TIMING_CLASS_CHOICES,
                        key=prefix + "item_timing_class",
                    )

                    st.caption("주식시장 근거")
                    b1, b2, b3 = st.columns(3)
                    basis_a = b1.text_input(
                        "가격·수급 근거",
                        key=prefix + "basis_a",
                        placeholder="예: 장중 고점 대비 밀림, 시가 위/아래, 프로그램 매수/매도",
                    )
                    basis_b = b2.text_input(
                        "거래대금·시총 근거",
                        key=prefix + "basis_b",
                        placeholder="예: 거래대금 강함, 시총 대비 거래대금 높음, 수급 탄력성",
                    )
                    basis_c = b3.text_input(
                        "섹터·지수 근거",
                        key=prefix + "basis_c",
                        placeholder="예: 자동차 섹터 동반 강세, KOSPI 대비 강함, 반도체 약세",
                    )

                    st.caption("베팅시장(예측시장) 근거")
                    g1, g2, g3 = st.columns(3)
                    basis_ga = g1.text_input(
                        "직접 예측시장 근거",
                        key=prefix + "basis_ga",
                        placeholder="예: Polymarket/Kalshi 확률 변화, 선거·금리·관세 이벤트 확률",
                    )
                    basis_na = g2.text_input(
                        "간접 시장가격 근거",
                        key=prefix + "basis_na",
                        placeholder="예: 나스닥100 선물, SOXX/SMH, 달러원, 금리, 유가, 비트코인",
                    )
                    basis_da = g3.text_input(
                        "이벤트·정책 근거",
                        key=prefix + "basis_da",
                        placeholder="예: 실적 발표, 수주, 정책 발표, 관세, 금리 이벤트",
                    )

                    j1, j2 = st.columns(2)
                    stock_judgment = j1.text_area("주식시장 판단", key=prefix + "stock_judgment")
                    betting_judgment = j2.text_area("베팅시장 판단", key=prefix + "betting_judgment")

                    st.caption("판단 설명 (점수/근거/매수 확정 — 비워두면 기본값으로 저장됩니다)")
                    p1, p2, p3 = st.columns(3)
                    score = p1.number_input("점수", value=0.0, step=1.0, key=prefix + "score")
                    score_reason = p2.text_input(
                        "점수 근거", key=prefix + "score_reason", placeholder="예: 시가 위 유지 + 거래대금 증가"
                    )
                    top_candidate_reason = p3.text_input(
                        "1순위 후보 근거", key=prefix + "top_candidate_reason", placeholder="예: 섹터 내 거래대금 우위"
                    )
                    p4, p5, p6 = st.columns(3)
                    penalty_reason = p4.text_input(
                        "감점 이유", key=prefix + "penalty_reason", placeholder="예: 고점 대비 일부 밀림"
                    )
                    buy_confirmed = p5.selectbox(
                        "매수 확정 여부", ["미확정", "확정"], key=prefix + "buy_confirmed"
                    )
                    buy_confirm_condition = p6.text_input(
                        "매수 확정 조건", key=prefix + "buy_confirm_condition", placeholder="예: 종가 강세 유지 필요"
                    )

                    v1, v2, v3 = st.columns(3)
                    trade_mode = v1.selectbox(
                        "매매유형", db.TRADE_MODE_CHOICES, key=prefix + "trade_mode"
                    )
                    verdict = v2.selectbox("판정", db.VERDICT_CHOICES, key=prefix + "verdict")
                    signal_type = v3.selectbox(
                        "신호 종류", db.SIGNAL_TYPE_CHOICES, key=prefix + "signal_type"
                    )

                    items_data.append(
                        {
                            "event_title": event_title,
                            "ticker": ticker,
                            "stock_name": stock_name,
                            "market": market,
                            "item_timing_class": None if item_timing_class_raw == "(미지정)" else item_timing_class_raw,
                            "stock_market_basis_a": basis_a,
                            "stock_market_basis_b": basis_b,
                            "stock_market_basis_c": basis_c,
                            "betting_basis_ga": basis_ga,
                            "betting_basis_na": basis_na,
                            "betting_basis_da": basis_da,
                            "stock_market_judgment": stock_judgment,
                            "betting_market_judgment": betting_judgment,
                            "verdict": verdict,
                            "signal_type": signal_type,
                            "trade_mode": trade_mode,
                            "score": score or None,
                            "score_reason": score_reason,
                            "top_candidate_reason": top_candidate_reason,
                            "penalty_reason": penalty_reason,
                            "buy_confirmed": buy_confirmed,
                            "buy_confirm_condition": buy_confirm_condition,
                        }
                    )

            if remove_id is not None:
                st.session_state.draft_items.remove(remove_id)
                st.rerun()

        st.markdown("---")
        if st.button("기록 저장", type="primary", key=f"save_{fv}"):
            if not day_conclusion.strip():
                st.error("오늘 요약을 입력해주세요.")
            else:
                final_raw_briefing = raw_briefing if raw_briefing.strip() else day_conclusion
                items_to_save = [
                    item
                    for item in items_data
                    if (item.get("event_title") or "").strip()
                    or (item.get("ticker") or "").strip()
                    or (item.get("stock_name") or "").strip()
                ]
                report_id = db.save_report(
                    market_scope=market_scope,
                    day_conclusion=day_conclusion,
                    raw_briefing=final_raw_briefing,
                    items=items_to_save,
                    briefing_stage=briefing_stage,
                )
                st.success(f"기록 저장 완료: 종목별 기록 {len(items_to_save)}개 저장됨 (report_id={report_id})")
                st.session_state["tab_paste_last_saved_id"] = report_id
                st.session_state.draft_items = []
                st.session_state.form_version += 1
                st.rerun()

        if st.session_state.get("tab_paste_last_saved_id"):
            last_saved_report = db.get_report(st.session_state["tab_paste_last_saved_id"])
            if last_saved_report:
                st.markdown("---")
                st.markdown("#### 방금 저장한 기록")
                render_report_detail(last_saved_report)

    # ---- 0단계 시장 분위기 자동 확인 (한국장 전용, 읽기 전용, 저장 없음) ----
# 기존 "오늘 주가 자동 채우기"와 동일한 price_data.get_snapshot_defaults()를 재사용한다.
# price_data.py 자체는 수정하지 않는다.
KR_MARKET_MOOD_AUTO_TARGETS = [
    ("나스닥100 선물", "NQ=F"),
    ("SOXX", "SOXX"),
    ("SMH", "SMH"),
    ("달러/원", "KRW=X"),
    ("코스피", "^KS11"),
    ("코스닥", "^KQ11"),
]


class _EmptyFetchResult(Exception):
    """조회 실패(빈 결과)를 st.cache_data에 저장하지 않기 위한 신호.

    2026-07-15 사용자 화면에서 확인: 장 시작 전(00:42) 로그인 때 거래대금 상위 조회가
    실패하면 그 빈 결과가 300초 캐시에 저장돼, 이후 재시도해도 계속 기본 종목 일부만
    표시됐다. st.cache_data는 예외가 발생한 호출을 캐시하지 않으므로, 빈 결과일 때
    예외를 던지고 바깥에서 받아 빈 값으로 돌려주면 "실패는 캐시 안 함"이 된다.
    """


@st.cache_data(ttl=300, show_spinner=False)
def _cached_top_kr_stocks_nonempty(n):
    stocks = price_data.get_top_kr_stocks_by_amount(n)
    if not stocks:
        raise _EmptyFetchResult()
    return stocks


def _cached_get_top_kr_stocks_by_amount(n):
    """여러 기기의 로그인에서 KRX 전체 종목표를 반복해서 받지 않게 한다(실패는 캐시 안 함)."""
    try:
        return _cached_top_kr_stocks_nonempty(n)
    except _EmptyFetchResult:
        return []
    except Exception:
        return []


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_top_kr_stocks_by_amount(n):
    return price_data.get_top_kr_stocks_by_amount(n)


# 장 시작 전에는 KRX 거래대금 데이터가 대부분 비어 있어 상위 선정이 서너 종목만
# 반환될 수 있다(2026-07-15 새벽 로그인 화면에서 확인 — "3종목만 나온다").
# 이 개수 미만이면 선정 결과를 불신하고 기존 목록을 유지한다.
MIN_TRUSTED_TOP_STOCKS = 8


def _fetch_top_us_stocks_by_amount(n):
    """US_CANDIDATE_UNIVERSE(유동성 높은 대형주 약 35종목) 안에서 오늘 거래대금
    (근사치 = 거래량×종가) 상위 n개를 골라낸다.

    KRX 전체 종목표 같은 벌크 API가 미국 시장에는 없어서, 전체 시장을 스캔하는 대신
    미리 정한 후보군 안에서만 병렬 조회 후 정렬한다(2026-07-15 사용자 승인 방식).
    조회 실패 종목은 제외하고, 유효한 종목이 하나도 없으면 빈 리스트를 반환한다.
    """
    tickers = tuple(s["ticker"] for s in US_CANDIDATE_UNIVERSE)
    results = _fetch_kr_snapshot_results(tickers)
    ranked = [
        stock for stock in US_CANDIDATE_UNIVERSE
        if (results.get(stock["ticker"]) or {}).get("ok")
        and (results[stock["ticker"]].get("turnover") or 0) > 0
    ]
    ranked.sort(key=lambda stock: results[stock["ticker"]]["turnover"], reverse=True)
    return ranked[:n]


@st.cache_data(ttl=300, show_spinner=False)
def _cached_top_us_stocks_nonempty(n):
    stocks = _fetch_top_us_stocks_by_amount(n)
    if not stocks:
        raise _EmptyFetchResult()
    return stocks


def _cached_get_top_us_stocks_by_amount(n):
    """여러 기기의 로그인에서 미국 후보군 35종목을 반복해서 조회하지 않게 한다(실패는 캐시 안 함)."""
    try:
        return _cached_top_us_stocks_nonempty(n)
    except _EmptyFetchResult:
        return []
    except Exception:
        return []


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_top_us_stocks_by_amount(n):
    return _fetch_top_us_stocks_by_amount(n)


def _fetch_kr_mood_source_results():
    """시장 분위기 원자료를 읽되 Yahoo 종목은 제한된 수로 병렬 조회한다."""
    results = {}
    index_tickers = [ticker for _, ticker in KR_MARKET_MOOD_AUTO_TARGETS if ticker in {"^KS11", "^KQ11"}]
    other_tickers = [ticker for _, ticker in KR_MARKET_MOOD_AUTO_TARGETS if ticker not in {"^KS11", "^KQ11"}]

    for ticker in index_tickers:
        result = _get_kr_index_intraday(ticker)
        if not result.get("ok"):
            result = price_data.get_snapshot_defaults(ticker)
        results[ticker] = result

    with ThreadPoolExecutor(max_workers=min(16, len(other_tickers))) as executor:
        future_to_ticker = {
            executor.submit(price_data.get_snapshot_defaults, ticker): ticker
            for ticker in other_tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ok": False, "error": "시장 자료 조회 실패"}
    return results


@st.cache_data(ttl=60, show_spinner=False)
def _cached_kr_mood_source_results():
    return _fetch_kr_mood_source_results()


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_kr_mood_source_results():
    return _fetch_kr_mood_source_results()


def _fetch_kr_snapshot_results(tickers):
    """종목별 Yahoo 조회를 병렬 처리하고 종목별 실패는 격리한다.

    2026-07-15: 4개씩 배치에서 최대 16개 동시로 확대 — 12종목 기준 3배치(~2.4초)가
    1배치(~0.9초)로 줄어든다. yfinance 건당 응답이 느린 무료 환경에서 체감이 크다.
    """
    tickers = tuple(tickers)
    if not tickers:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=min(16, len(tickers))) as executor:
        future_to_ticker = {
            executor.submit(price_data.get_snapshot_defaults, ticker): ticker
            for ticker in tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ok": False, "error": "종목 자료 조회 실패"}
    return results


@st.cache_data(ttl=90, show_spinner=False)
def _cached_kr_snapshot_results_raw(tickers):
    results = _fetch_kr_snapshot_results(tickers)
    if results and not any((r or {}).get("ok") for r in results.values()):
        raise _EmptyFetchResult()  # 전 종목 실패는 캐시하지 않는다 — 다음 호출에서 재시도
    return results


def _cached_kr_snapshot_results(tickers):
    tickers = tuple(tickers)
    try:
        results = _cached_kr_snapshot_results_raw(tickers)
    except _EmptyFetchResult:
        return {t: {"ok": False, "error": "종목 자료 조회 실패"} for t in tickers}
    except Exception:
        return {t: {"ok": False, "error": "종목 자료 조회 실패"} for t in tickers}
    # 일부 종목만 실패한 캐시 결과는 실패분만 즉시 한 번 더 조회해서 메꾼다 —
    # 로그인 자동 채우기에서 일시 오류로 3종목만 뜨던 문제(2026-07-15) 보정.
    failed = tuple(t for t in tickers if not (results.get(t) or {}).get("ok"))
    if failed and len(failed) < len(tickers):
        retry = _fetch_kr_snapshot_results(failed)
        results = {**results, **{t: r for t, r in retry.items() if (r or {}).get("ok")}}
    return results


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_kr_snapshot_results(tickers):
    return _fetch_kr_snapshot_results(tickers)


def _kr_mood_auto_verdict(name, change_pct):
    """0단계 시장 분위기 자동 확인 전용 판정(참고용, 매수 신호 아님). 달러/원은 별도 문구."""
    if change_pct is None:
        return "확인 불가"
    if name == "달러/원":
        if change_pct >= 0.3:
            return "상승 (원화 약세, 한국장 부담)"
        if change_pct <= -0.3:
            return "하락 (원화 강세, 한국장 우호)"
        return "보합 (환율 중립)"
    if change_pct >= 0.3:
        return "강함 (상승 우세)"
    if change_pct <= -0.3:
        return "약함 (하락 우세)"
    return "보합 (중립)"


def run_kr_mood_auto_check(force_refresh=False):
    """0단계 시장 분위기 자동 확인 공용 조회 함수 (읽기 전용, DB 저장 없음).

    KR_MARKET_MOOD_AUTO_TARGETS를 조회해 기존과 동일한 형식으로
    st.session_state["kr_mood_auto_results"]/["kr_mood_auto_any_ok"]에 저장한다.
    0단계 버튼과 "0→1→2 한 번에 미리보기 생성" 버튼이 모두 이 함수를 호출한다.
    반환: {"status": "ok"/"partial"/"fail", "results": [...], "message": str 또는 None,
    "ok_count": int, "total": int}
    """
    _mood_results = []
    _ok_count = 0
    _mood_source_results = (
        _short_cached_kr_mood_source_results()
        if force_refresh
        else _cached_kr_mood_source_results()
    )
    for _mood_name, _mood_ticker in KR_MARKET_MOOD_AUTO_TARGETS:
        _mood_result = _mood_source_results.get(_mood_ticker) or {
            "ok": False,
            "error": "시장 자료 조회 실패",
        }
        if _mood_result.get("ok"):
            _ok_count += 1
            _mood_change_pct = _safe_pct_diff(_mood_result["current"], _mood_result["prev_close"])
            _mood_results.append(
                {
                    "항목": _mood_name,
                    "등락률(%)": _fmt_signed_pct(_mood_change_pct),
                    "판정": _kr_mood_auto_verdict(_mood_name, _mood_change_pct),
                    "현재값": _mood_result["current"],
                    "출처": _mood_result.get("source") or "자동 조회",
                }
            )
        else:
            _mood_results.append(
                {
                    "항목": _mood_name,
                    "등락률(%)": "-",
                    "판정": "확인 불가",
                    "현재값": "-",
                    "출처": "조회 실패",
                }
            )
    _total = len(KR_MARKET_MOOD_AUTO_TARGETS)
    if _ok_count == 0:
        status, message = "fail", "전체 조회 실패 (네트워크 또는 데이터 제공처 문제)"
    elif _ok_count == _total:
        status, message = "ok", None
    else:
        status, message = "partial", None

    st.session_state["kr_mood_auto_results"] = _mood_results
    st.session_state["kr_mood_auto_any_ok"] = _ok_count > 0

    return {"status": status, "results": _mood_results, "message": message, "ok_count": _ok_count, "total": _total}


def run_kr_snapshot_auto_fill(force_refresh=False):
    """1단계 오늘 주가 자동 채우기 공용 조회 함수 (읽기 전용, DB 저장 없음).

    SNAPSHOT_STOCKS를 조회해 성공한 종목만 session_state 입력값에 반영한다. 실패한 종목은
    session_state를 건드리지 않으므로 기존 입력값이 있으면 그대로 유지된다. 기존과 동일한
    형식으로 st.session_state["snap_auto_fill_results"]에 저장한다. ① 버튼과 "0→1→2 한
    번에 미리보기 생성" 버튼이 모두 이 함수를 호출한다.
    반환: {"status": "ok"/"partial"/"fail", "results": {...}, "message": str 또는 None,
    "ok_count": int, "total": int}
    """
    _snapshot_tickers = tuple(s["ticker"] for s in SNAPSHOT_STOCKS)
    fetch_results = (
        _short_cached_kr_snapshot_results(_snapshot_tickers)
        if force_refresh
        else _cached_kr_snapshot_results(_snapshot_tickers)
    )
    _ok_count = 0
    for s in SNAPSHOT_STOCKS:
        result = fetch_results.get(s["ticker"]) or {"ok": False, "error": "종목 자료 조회 실패"}
        if result.get("ok"):
            _ok_count += 1
            prefix = f"snap_{s['ticker']}_"
            st.session_state[prefix + "current"] = result["current"]
            st.session_state[prefix + "prev_close"] = result["prev_close"]
            st.session_state[prefix + "open"] = result["open"]
            st.session_state[prefix + "high"] = result["high"]
            st.session_state[prefix + "low"] = result["low"]
            st.session_state[prefix + "turnover"] = result["turnover"]
            st.session_state[prefix + "market_cap"] = result["market_cap"] or 0.0
        # 실패 종목은 session_state를 건드리지 않는다 — 기존 입력값이 있으면 그대로 유지된다.
    _total = len(SNAPSHOT_STOCKS)
    if _ok_count == 0:
        status, message = "fail", "전체 조회 실패 (네트워크 또는 데이터 제공처 문제)"
    elif _ok_count == _total:
        status, message = "ok", None
    else:
        status, message = "partial", None

    st.session_state["snap_auto_fill_results"] = fetch_results

    return {"status": status, "results": fetch_results, "message": message, "ok_count": _ok_count, "total": _total}


_AUTO_FETCH_FIELD_LABELS = {
    "current": "현재가", "prev_close": "전일종가", "open": "시가",
    "high": "고가", "low": "저가", "volume": "거래량",
    "turnover": "거래대금", "market_cap": "시가총액",
}


def _render_auto_fetch_status_summary(results, stock_defs, prefix):
    total = len(stock_defs)
    complete = 0
    partial = 0
    failed = []
    details = []
    for stock in stock_defs:
        ticker = stock["ticker"]
        result = results.get(ticker) or {}
        if not result.get("ok"):
            failed.append((stock["name"], ticker, result.get("error") or "데이터 없음"))
            continue
        missing = [
            label for field, label in _AUTO_FETCH_FIELD_LABELS.items()
            if result.get(field) is None
        ]
        if missing:
            partial += 1
            details.append((stock["name"], ticker, "누락: " + ", ".join(missing)))
        else:
            complete += 1
    if partial == 0 and not failed:
        st.success(f"자동조회 완료: {total}개 종목 모두 정상 ({complete}/{total})")
        return
    st.warning(f"자동조회 결과: 전체 {total}개 / 완전 성공 {complete}개 / 일부 누락 {partial}개 / 전체 실패 {len(failed)}개")
    with st.expander("자동조회 누락·실패 상세", expanded=False):
        for name, ticker, reason in details:
            st.caption(f"{name} ({ticker}) — {reason}")
        for name, ticker, reason in failed:
            st.caption(f"{name} ({ticker}) — 전체 실패: {reason}")
    retry_key = f"{prefix}retry_failed_auto_fetch"
    retry_targets = {
        stock["ticker"]
        for stock in stock_defs
        if not (results.get(stock["ticker"]) or {}).get("ok")
        or any(
            (results.get(stock["ticker"]) or {}).get(field) is None
            for field in _AUTO_FETCH_FIELD_LABELS
        )
    }
    if st.button("실패·누락 종목만 다시 조회", key=retry_key):
        changed = False
        for stock in stock_defs:
            ticker = stock["ticker"]
            if ticker not in retry_targets:
                continue
            result = price_data.get_snapshot_defaults(ticker)
            previous = results.get(ticker) or {}
            merged = dict(previous)
            merged.update(result)
            if result.get("ok"):
                state_prefix = f"snap_{ticker}_"
                for field in _AUTO_FETCH_FIELD_LABELS:
                    value = result.get(field)
                    state_key = state_prefix + field
                    existing = st.session_state.get(state_key)
                    if value is not None and existing in (None, "", 0):
                        st.session_state[state_key] = value
                        changed = True
                if merged != previous:
                    changed = True
            elif result != previous:
                changed = True
            results[ticker] = merged
        results_key = "snap_auto_fill_results" if prefix == "kr_" else "us_stock_auto_fill_results"
        st.session_state[results_key] = results
        if changed:
            for key in (
                "kr_quick_preview_rows", "kr_quick_day_conclusion", "kr_quick_basis_text",
                "kr_show_save_preview", "us_swing_preview_rows", "us_swing_day_conclusion",
                "us_swing_basis_text", "us_swing_raw_briefing", "us_show_save_preview",
            ):
                st.session_state.pop(key, None)
        st.rerun()


KR_THEME_WATCH_INITIAL_ROWS = [
    {
        "테마": theme,
        "상태": "확인 필요",
        "대장주": "",
        "대장주상태": "강세유지",
        "후발주": "",
        "추격주의": "",
        "메모": "",
    }
    for theme in [
        "반도체/HBM",
        "전력기기/전력망",
        "원전",
        "방산",
        "조선/해운",
        "자동차/부품",
        "2차전지",
        "바이오",
        "AI/로봇",
        "정유/화학",
        # 2026-07-13(사용자 요청: 테마 20개까지 확장) 추가분
        "게임",
        "엔터테인먼트",
        "화장품",
        "태양광",
        "수소에너지",
        "우주항공",
        "5G/통신장비",
        "사이버보안",
        "의료기기",
        "은행",
    ]
]
KR_THEME_WATCH_DATA_KEY = "kr_theme_watch_rows"
KR_THEME_WATCH_EDITOR_KEY = "kr_theme_watch_editor"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_kr_theme_snapshot():
    """여러 기기의 로그인에서 같은 테마 페이지를 반복해서 읽지 않게 한다."""
    return theme_data.fetch_kr_theme_snapshot()


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_fetch_kr_theme_snapshot():
    return theme_data.fetch_kr_theme_snapshot()


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_fetch_us_sector_snapshot():
    return theme_data.fetch_us_sector_snapshot()


@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)
def _short_cached_fetch_us_theme_indicators():
    return theme_data.fetch_us_theme_indicators()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_us_sector_snapshot():
    """여러 기기의 탭 진입에서 같은 섹터 ETF 조회를 반복하지 않게 한다."""
    return theme_data.fetch_us_sector_snapshot()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_us_theme_indicators():
    """여러 기기의 탭 진입에서 같은 테마 지표 조회를 반복하지 않게 한다."""
    return theme_data.fetch_us_theme_indicators()


def _render_kr_theme_chip_editor():
    """기존 한국장 테마 list[dict]를 단일 session_state 원본으로 편집한다 (DB 미사용)."""
    st.markdown(
        """
        <style>
        .jarvis-m1-theme-title {
            color: #f8fafc;
            font-size: 0.98rem;
            font-weight: 850;
            margin-bottom: 0.35rem;
        }
        .jarvis-m1-theme-status {
            display: inline-block;
            border-radius: 999px;
            padding: 0.22rem 0.58rem;
            margin: 0.15rem 0 0.55rem;
            font-size: 0.74rem;
            font-weight: 800;
        }
        .jarvis-m1-theme-strong { background: #14532d; color: #bbf7d0; }
        .jarvis-m1-theme-watch { background: #713f12; color: #fef08a; }
        .jarvis-m1-theme-normal { background: #1e3a5f; color: #bfdbfe; }
        .jarvis-m1-theme-weak { background: #334155; color: #cbd5e1; }
        .jarvis-m1-theme-check { background: #202938; color: #94a3b8; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    source_rows = st.session_state.get(KR_THEME_WATCH_DATA_KEY)
    if isinstance(source_rows, list):
        theme_rows = [dict(row) for row in source_rows]
    else:
        theme_rows = [dict(row) for row in KR_THEME_WATCH_INITIAL_ROWS]
        legacy_editor_state = st.session_state.get(KR_THEME_WATCH_EDITOR_KEY)
        if isinstance(legacy_editor_state, dict):
            legacy_edits = legacy_editor_state.get("edited_rows") or {}
            for raw_index, changes in legacy_edits.items():
                try:
                    row_index = int(raw_index)
                except (TypeError, ValueError):
                    continue
                if not (0 <= row_index < len(theme_rows)) or not isinstance(changes, dict):
                    continue
                for column, value in changes.items():
                    if column in theme_rows[row_index] and column != "테마":
                        theme_rows[row_index][column] = value

    status_options = ["강함", "감시", "보통", "약함", "확인 필요"]
    status_classes = {
        "강함": "strong",
        "감시": "watch",
        "보통": "normal",
        "약함": "weak",
        "확인 필요": "check",
    }
    field_specs = [
        ("대장주", "kr_theme_leader_"),
        ("후발주", "kr_theme_laggard_"),
        ("추격주의", "kr_theme_chase_warning_"),
        ("메모", "kr_theme_memo_"),
    ]

    st.caption(
        "자동 조회는 네이버 테마별 시세를 참고용으로만 가져옵니다. 점수·판정·DB 저장에는 "
        "반영되지 않으며, 대장주 칸은 이미 입력된 값이 있으면 덮어쓰지 않습니다."
    )
    st.markdown(
        """
        <style>
        .st-key-kr_theme_auto_fetch button {
            background: #facc15 !important;
            color: #1f2937 !important;
            border-color: #eab308 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        .st-key-kr_theme_auto_fetch button p {
            color: #1f2937 !important;
        }
        /* 2026-07-15 사용자 요청: 대장주 등 세부 입력칸 글자가 너무 작았다. */
        [class*="st-key-kr_theme_leader_"] input,
        [class*="st-key-kr_theme_laggard_"] input,
        [class*="st-key-kr_theme_chase_warning_"] input,
        [class*="st-key-kr_theme_memo_"] input {
            font-size: 19px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _kr_theme_manual_fetch = st.button("테마 참고판 자동 조회", key="kr_theme_auto_fetch")
    _kr_theme_auto_fetch = st.session_state.pop("kr_theme_auto_fetch_pending", False)
    if _kr_theme_manual_fetch or _kr_theme_auto_fetch:
        _kr_theme_selected_before_fetch = st.session_state.get("kr_theme_detail_selector")
        _kr_theme_fetch_result = (
            _short_cached_fetch_kr_theme_snapshot()
            if _kr_theme_manual_fetch
            else _cached_fetch_kr_theme_snapshot()
        )
        if not _kr_theme_fetch_result["ok"]:
            st.session_state["kr_theme_auto_fetch_error"] = _kr_theme_fetch_result.get("error") or "조회 실패"
        else:
            st.session_state.pop("kr_theme_auto_fetch_error", None)
            st.session_state["kr_theme_auto_fetch_checked_at"] = _kr_theme_fetch_result["checked_at"]
            for _row in theme_rows:
                _theme_name = _row.get("테마")
                _auto = _kr_theme_fetch_result["themes"].get(_theme_name)
                if not _auto or not _auto.get("ok"):
                    continue
                _row["상태"] = _auto["verdict"]
                _row["_auto_change_pct"] = _auto["change_pct"]
                if not (_row.get("대장주") or "").strip() and _auto.get("top_stock"):
                    _row["대장주"] = _auto["top_stock"]
                    _slug = "_".join(f"u{ord(c):04x}" for c in _theme_name if c.isalnum())
                    st.session_state[f"kr_theme_leader_{_slug}"] = _auto["top_stock"]
            st.session_state[KR_THEME_WATCH_DATA_KEY] = theme_rows
            # 순수 관찰 로그: 오늘 조회한 테마별 강함/보통/약함을 theme_history에 기록한다.
            # 점수·판정·report DB와는 완전히 분리된 테이블이며, 이 기록 자체는 저장/판정에
            # 영향을 주지 않는다.
            theme_history.record_theme_states(
                {
                    theme_name: info["verdict"]
                    for theme_name, info in _kr_theme_fetch_result["themes"].items()
                    if info.get("ok")
                }
            )
        if _kr_theme_selected_before_fetch is not None:
            st.session_state["kr_theme_detail_selector"] = _kr_theme_selected_before_fetch
        st.rerun()
    if st.session_state.get("kr_theme_auto_fetch_error"):
        st.warning(f"테마 자동 조회 실패: {st.session_state['kr_theme_auto_fetch_error']} (네트워크 문제일 수 있습니다)")
    if st.session_state.get("kr_theme_auto_fetch_checked_at"):
        st.caption(f"마지막 자동 조회: {st.session_state['kr_theme_auto_fetch_checked_at']}")

    with st.container(key="kr_theme_reference"):
        theme_columns = st.columns(2, gap="large")
    _theme_detail_options = ["선택 안 함"] + [str(row.get("테마") or "") for row in theme_rows if row.get("테마")]
    # 처음 열었을 때 "선택 안 함"이면 아래 "선택 테마 현재 상태"/"선택 테마 세부 입력"이
    # 통째로 안 보여서 헷갈린다는 지적 — 아직 한 번도 선택한 적 없으면 "강함" 테마 중
    # 첫 번째를 기본으로 선택해둔다(2026-07-13 사용자 요청).
    # 표에서 테마 행을 클릭했을 때(아래 st.dataframe on_select 핸들러)는 위젯이 이미
    # 인스턴스화된 뒤라 session_state["kr_theme_detail_selector"]를 바로 못 바꾼다
    # (StreamlitAPIException). 그래서 클릭 시엔 이 "대기" 키에만 값을 남기고 rerun하며,
    # 다음 실행에서 셀렉트박스가 만들어지기 전인 여기서 대신 반영한다(2026-07-13).
    _kr_theme_pending_select = st.session_state.pop("_kr_theme_pending_select", None)
    if _kr_theme_pending_select:
        st.session_state["kr_theme_detail_selector"] = _kr_theme_pending_select
    elif "kr_theme_detail_selector" not in st.session_state:
        _default_strong_theme = next(
            (row.get("테마") for row in theme_rows if row.get("상태") == "강함" and row.get("테마")),
            None,
        )
        if _default_strong_theme:
            st.session_state["kr_theme_detail_selector"] = _default_strong_theme
    _theme_detail_selected = st.selectbox(
        "세부 입력할 테마 선택",
        _theme_detail_options,
        key="kr_theme_detail_selector",
    )
    def _kr_theme_table_styler(col):
        styles = []
        for val in col:
            if val == "강함":
                styles.append("color: #ff4b4b; font-weight: 800")
            else:
                styles.append("")
        return styles

    def _kr_theme_name_styler(col):
        return ["color: #60a5fa; font-weight: 700" for _ in col]

    def _kr_theme_row_highlight(row):
        if row.get("세부 입력") == "선택됨":
            return ["border: 2px solid #4ade80"] * len(row)
        return [""] * len(row)

    def _kr_theme_leader_auto_status(leader_name):
        """대장주 꺾임 자동 판정(하이브리드). 대장주 이름이 SNAPSHOT_STOCKS(7종목) 안에
        있으면 오늘 주가 자동 채우기로 이미 받아온 고점/현재가로 고점대비 밀림률을 계산해
        -7% 이상 밀렸으면 자동 "꺾임"으로 판정한다. 7종목 밖 대장주면 자동 판정할 수
        없으므로 available=False를 반환하고, 화면에서는 수동 선택으로 넘어간다.
        점수·판정·DB와는 무관한 참고용 계산이다.
        """
        leader_name = (leader_name or "").strip()
        ticker = SNAPSHOT_NAME_TO_TICKER.get(leader_name)
        if not ticker:
            return {"available": False, "verdict": None, "drop_pct": None}
        prefix = f"snap_{ticker}_"
        current = st.session_state.get(prefix + "current")
        high = st.session_state.get(prefix + "high")
        drop_pct = compute_drop_from_high_pct(current, high)
        if drop_pct is None:
            return {"available": False, "verdict": None, "drop_pct": None}
        verdict = "꺾임" if drop_pct >= 7 else "강세유지"
        return {"available": True, "verdict": verdict, "drop_pct": drop_pct}

    def _kr_theme_elapsed_text(theme_name):
        # 순수 관찰 로그(theme_history) 기반 자동 계산. 점수·판정과 무관한 참고 표시.
        elapsed = theme_history.get_theme_elapsed_strong_days(theme_name)
        if elapsed is None:
            # 로그가 아예 없는 테마와, 로그는 있지만 최근이 "강함"이 아닌 테마를 구분한다.
            has_any_log = theme_history.has_theme_log(theme_name)
            return "관찰 시작 1일차" if not has_any_log else "-"
        suffix = " ⚠추격주의" if elapsed >= 4 else ""
        return f"경과 {elapsed}일차{suffix}"

    # 강함 -> 보통 -> 확인 필요 -> 약함 -> 감시 순으로 정렬(2026-07-13 사용자 요청). 네이버
    # 데이터를 그대로 가져오는 구조라 "아주 강함" 단계는 원래 없다(_classify_kr_theme_verdict
    # 참고 — 강함/보통/약함 3단계뿐).
    _KR_THEME_STATUS_PRIORITY = {"강함": 0, "보통": 1, "확인 필요": 2, "약함": 3, "감시": 4}
    _kr_theme_sorted_rows = sorted(
        (row for row in theme_rows if row.get("테마")),
        key=lambda row: _KR_THEME_STATUS_PRIORITY.get(row.get("상태"), 5),
    )
    _kr_theme_df = pd.DataFrame(
        [
            {
                "테마": row.get("테마", ""),
                "현재 상태": row.get("상태", "확인 필요"),
                "참고 지표 또는 대표 종목": row.get("대장주", ""),
                "경과일수": _kr_theme_elapsed_text(row.get("테마", "")),
                "경고": "후발주 청산 검토" if row.get("대장주상태") == "꺾임" else "",
                "세부 입력": "선택됨" if row.get("테마") == _theme_detail_selected else "선택 가능",
            }
            for row in _kr_theme_sorted_rows
        ]
    )

    def _kr_theme_elapsed_styler(col):
        return [
            "color: #f97316; font-weight: 800" if "추격주의" in str(val) else ""
            for val in col
        ]

    def _kr_theme_warning_styler(col):
        return ["color: #ef4444; font-weight: 800" if val else "" for val in col]

    _kr_theme_styled_df = (
        _kr_theme_df.style
        .apply(_kr_theme_name_styler, subset=["테마"])
        .apply(_kr_theme_table_styler, subset=["현재 상태"])
        .apply(_kr_theme_elapsed_styler, subset=["경과일수"])
        .apply(_kr_theme_warning_styler, subset=["경고"])
        .apply(_kr_theme_row_highlight, axis=1)
    )
    st.markdown(
        """
        <style>
        /* st.dataframe(glide-data-grid)은 셀 텍스트를 canvas에 직접 그려서 일반
           font-size CSS가 안 먹는다 — 자체 CSS 변수(--gdg-*)로 폰트를 읽는다. */
        .st-key-kr_theme_table [data-testid="stDataFrame"] {
            --gdg-header-font-style: 700 17px "Source Sans", sans-serif !important;
            --gdg-base-font-style: 400 17px "Source Sans", sans-serif !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="kr_theme_table"):
        # 2026-07-15: key 없이 호출하면 Streamlit이 위젯 정체성(id)을 data 내용까지
        # 해시에 넣어 계산한다(streamlit/elements/lib/utils.py 실측 확인). 이 표의
        # "세부 입력" 열은 선택된 테마가 바뀔 때마다 "선택됨"/"선택 가능" 텍스트가
        # 바뀌므로, 행을 클릭해서 선택할 때마다 표 내용이 달라져 위젯 id가 매번
        # 새로 계산되고, 방금 클릭한 체크 표시가 다음 rerun에서 사라졌다(사용자
        # 반복 지적 — "원전 클릭해도 체크 표시가 안 남는다"). key를 명시하면
        # id 계산에서 data 내용이 빠져 선택 상태가 rerun 사이에 유지된다.
        _kr_theme_table_event = st.dataframe(
            _kr_theme_styled_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="kr_theme_table_df",
            column_config={
                "참고 지표 또는 대표 종목": st.column_config.TextColumn(
                    "참고 지표 또는 대표 종목", width=550
                ),
            },
        )
    # 표에서 테마 행을 직접 클릭해도 "세부 입력할 테마 선택" 드롭다운과 동기화되게 한다
    # (2026-07-13 사용자 요청 — 드롭다운으로만 되고 표 클릭으로는 안 됐던 문제).
    _kr_theme_clicked_rows = (
        _kr_theme_table_event.selection.rows
        if _kr_theme_table_event and _kr_theme_table_event.selection
        else []
    )
    if _kr_theme_clicked_rows:
        _kr_theme_clicked_idx = _kr_theme_clicked_rows[0]
        if 0 <= _kr_theme_clicked_idx < len(_kr_theme_sorted_rows):
            _kr_theme_clicked_name = _kr_theme_sorted_rows[_kr_theme_clicked_idx].get("테마")
            if _kr_theme_clicked_name and st.session_state.get("kr_theme_detail_selector") != _kr_theme_clicked_name:
                st.session_state["_kr_theme_pending_select"] = _kr_theme_clicked_name
                # 2026-07-15: 표 클릭은 이미 이 프래그먼트 안에서 일어나므로, 가능하면
                # 전체 앱이 아니라 이 프래그먼트만 다시 그린다(_fragment_scoped_rerun 참고).
                _fragment_scoped_rerun()
    split_index = (len(theme_rows) + 1) // 2
    updated_rows = [dict(row) for row in theme_rows]

    # 기존 테마별 카드/상태 버튼은 렌더링하지 않고 표만 유지한다.
    for index, row in enumerate([]):
        updated_row = dict(row)
        theme_name = str(row.get("테마") or "")
        if not theme_name:
            updated_rows.append(updated_row)
            continue

        slug = "_".join(f"u{ord(char):04x}" for char in theme_name if char.isalnum())
        status_key = f"kr_theme_status_{slug}"
        initial_status = row.get("상태")
        if initial_status not in status_options:
            initial_status = "확인 필요"
        if status_key not in st.session_state:
            st.session_state[status_key] = initial_status

        target_column = theme_columns[0 if index < split_index else 1]
        with target_column:
            with st.container(border=True):
                st.markdown(f'<div class="jarvis-m1-theme-title">{theme_name}</div>', unsafe_allow_html=True)
                if hasattr(st, "segmented_control"):
                    selected_status = st.segmented_control(
                        f"{theme_name} 상태",
                        status_options,
                        key=status_key,
                        label_visibility="collapsed",
                    )
                else:
                    selected_status = st.radio(
                        f"{theme_name} 상태",
                        status_options,
                        horizontal=True,
                        key=status_key,
                        label_visibility="collapsed",
                    )
                if selected_status not in status_options:
                    selected_status = "확인 필요"
                status_class = status_classes[selected_status]
                st.markdown(
                    f'<span class="jarvis-m1-theme-status jarvis-m1-theme-{status_class}">'
                    f"현재 상태 · {selected_status}</span>",
                    unsafe_allow_html=True,
                )

                detail_values = {}
                if theme_name == _theme_detail_selected:
                    with st.expander("세부 입력", expanded=True):
                        for field_name, key_prefix in field_specs:
                            widget_key = f"{key_prefix}{slug}"
                            if widget_key not in st.session_state:
                                st.session_state[widget_key] = str(row.get(field_name) or "")
                            if field_name == "메모":
                                detail_values[field_name] = st.text_area(field_name, key=widget_key)
                            else:
                                detail_values[field_name] = st.text_input(field_name, key=widget_key)

        if "상태" in updated_row:
            updated_row["상태"] = selected_status
        for field_name, value in detail_values.items():
            if field_name in updated_row:
                updated_row[field_name] = value
        updated_rows.append(updated_row)

    if _theme_detail_selected != "선택 안 함":
        selected_theme_row = next(
            (row for row in theme_rows if row.get("테마") == _theme_detail_selected),
            None,
        )
        if selected_theme_row:
            selected_theme_slug = "_".join(
                f"u{ord(char):04x}" for char in _theme_detail_selected if char.isalnum()
            )
            selected_status_key = f"kr_theme_status_{selected_theme_slug}"
            _leader_status_key = f"kr_theme_leader_status_{selected_theme_slug}"

            # "이 테마 후발주·추격주의·메모 자동 채우기" 버튼(아래 expander 안)이 눌리면
            # 위젯이 이미 인스턴스화된 뒤라 session_state를 바로 못 바꾼다(표 클릭 때와
            # 같은 문제). 그래서 버튼 클릭 시엔 대기 키에만 결과를 남기고 rerun하며,
            # 위젯이 만들어지기 전인 여기서 대신 반영한다(2026-07-13).
            _kr_theme_stock_detail_pending = st.session_state.pop(
                f"_kr_theme_stock_detail_pending_{selected_theme_slug}", None
            )
            if _kr_theme_stock_detail_pending:
                _field_key_prefix = dict(field_specs)
                for _field_name, _value in _kr_theme_stock_detail_pending.items():
                    _key_prefix = _field_key_prefix.get(_field_name)
                    if _key_prefix and _value:
                        st.session_state[f"{_key_prefix}{selected_theme_slug}"] = _value

            # 테마 선택이 바뀔 때마다(드롭다운으로 고르든 표에서 클릭하든) 세부 입력 위젯을
            # 그 테마의 최신 저장값(자동조회로 이미 채워진 대장주 등 포함)으로 강제
            # 동기화한다. 예전엔 위젯을 한 번만 초기화해서, 자동조회가 나중에 값을 채워도
            # 이미 만들어진 위젯엔 반영이 안 돼 "표엔 값이 있는데 세부 입력 칸은 비어있는"
            # 불일치가 생겼다(2026-07-13 사용자 지적).
            if st.session_state.get("kr_theme_detail_synced_theme") != _theme_detail_selected:
                st.session_state[selected_status_key] = (
                    selected_theme_row.get("상태")
                    if selected_theme_row.get("상태") in status_options
                    else status_options[-1]
                )
                for field_name, key_prefix in field_specs:
                    st.session_state[f"{key_prefix}{selected_theme_slug}"] = str(
                        selected_theme_row.get(field_name) or ""
                    )
                _leader_auto_on_switch = _kr_theme_leader_auto_status(selected_theme_row.get("대장주"))
                st.session_state[_leader_status_key] = (
                    _leader_auto_on_switch["verdict"] if _leader_auto_on_switch["available"]
                    else str(selected_theme_row.get("대장주상태") or "강세유지")
                )
                st.session_state["kr_theme_detail_synced_theme"] = _theme_detail_selected

            # 위 "테마가 바뀔 때만" 동기화로는 못 잡는 경우 하나 더 방어한다: 같은 테마를
            # 이미 본 적 있어서(동기화 마커가 안 바뀜) 위 블록을 건너뛰었는데, 그 사이
            # "테마 참고판 자동 조회"가 새로 실행돼서 표(행 데이터)에는 대장주가 채워졌지만
            # 이 위젯은 여전히 예전 빈 값을 들고 있는 경우. 표에는 값이 있는데 입력칸이
            # 비어있으면 테마 전환 여부와 무관하게 항상 바로잡는다(2026-07-13, 반복 지적됨).
            _leader_widget_key = f"kr_theme_leader_{selected_theme_slug}"
            _row_leader_value = str(selected_theme_row.get("대장주") or "").strip()
            _widget_leader_value = str(st.session_state.get(_leader_widget_key, "")).strip()
            if _row_leader_value and not _widget_leader_value:
                st.session_state[_leader_widget_key] = _row_leader_value
                _leader_auto_fix = _kr_theme_leader_auto_status(_row_leader_value)
                st.session_state[_leader_status_key] = (
                    _leader_auto_fix["verdict"] if _leader_auto_fix["available"]
                    else str(selected_theme_row.get("대장주상태") or "강세유지")
                )

            selected_status = st.selectbox(
                "선택 테마 현재 상태",
                status_options,
                key=selected_status_key,
            )
            # 2026-07-15 사용자 요청: 선택된 테마/상태가 셀렉트박스 글자 크기(기본)로만
            # 보여서 눈에 안 띈다는 지적 — "원전 / 강함"처럼 테마명·상태를 색깔 있는
            # 큰 글자(기존 대비 약 4배)로 한 번 더 보여준다. 값 자체는 selectbox와
            # 동일하며, 이 표시는 참고용이고 저장에는 영향을 주지 않는다.
            _selected_status_color = {
                "강함": "#ff4b4b",
                "감시": "#facc15",
                "보통": "#4b9fff",
                "약함": "#94a3b8",
                "확인 필요": "#6b7280",
            }.get(selected_status, "#e5e7eb")
            st.markdown(
                f"<div style='font-size:64px;font-weight:800;line-height:1.2;"
                f"color:{_selected_status_color};margin:0.2rem 0 0.7rem'>"
                f"{html.escape(_theme_detail_selected)} / {html.escape(selected_status)}</div>",
                unsafe_allow_html=True,
            )
            selected_detail_values = {}
            with st.expander("선택 테마 세부 입력", expanded=True):
                # 2026-07-13 추가: 후발주/추격주의/메모가 항상 빈 칸이라는 지적 —
                # 대표 종목별 개별 등락률을 조회해 순위를 매기고(1등 대장주, 2·3등
                # 양전이면 후발주, 4등 이하 추격주의), 테마명으로 뉴스도 1건 찾아
                # 메모에 채운다. 버튼을 눌렀을 때만 조회하며 점수·판정·DB에는
                # 반영하지 않는다(theme_data.fetch_kr_theme_stock_detail 참고).
                if st.button(
                    "이 테마 후발주·추격주의·메모 자동 채우기",
                    key=f"kr_theme_stock_detail_fetch_{selected_theme_slug}",
                ):
                    with st.spinner("종목별 등락률·뉴스 조회 중..."):
                        _stock_detail = theme_data.fetch_kr_theme_stock_detail(_theme_detail_selected)
                        _pending = {}
                        if _stock_detail.get("ok"):
                            if _stock_detail.get("후발주"):
                                _pending["후발주"] = _stock_detail["후발주"]
                            if _stock_detail.get("추격주의"):
                                _pending["추격주의"] = _stock_detail["추격주의"]
                        else:
                            st.session_state[f"_kr_theme_stock_detail_error_{selected_theme_slug}"] = (
                                _stock_detail.get("error") or "조회 실패"
                            )
                        _client_id = st.secrets.get("NAVER_CLIENT_ID")
                        _client_secret = st.secrets.get("NAVER_CLIENT_SECRET")
                        if _client_id and _client_secret:
                            _news_result = news_data.fetch_naver_news(
                                _client_id, _client_secret, f"{_theme_detail_selected} 테마", display=3, sort="date"
                            )
                            _news_items = _news_result.get("data") or []
                            if _news_items:
                                _pending["메모"] = f"[뉴스] {_news_items[0].get('title') or ''}".strip()
                        if _pending:
                            st.session_state[f"_kr_theme_stock_detail_pending_{selected_theme_slug}"] = _pending
                    st.rerun()
                _stock_detail_error = st.session_state.pop(
                    f"_kr_theme_stock_detail_error_{selected_theme_slug}", None
                )
                if _stock_detail_error:
                    st.caption(f"자동 채우기 실패: {_stock_detail_error} — 직접 입력해 주세요.")
                for field_name, key_prefix in field_specs:
                    widget_key = f"{key_prefix}{selected_theme_slug}"
                    if field_name == "메모":
                        selected_detail_values[field_name] = st.text_area(field_name, key=widget_key)
                    else:
                        selected_detail_values[field_name] = st.text_input(field_name, key=widget_key)

                    if field_name == "대장주":
                        _leader_auto = _kr_theme_leader_auto_status(selected_detail_values[field_name])
                        selected_leader_status = st.selectbox(
                            "대장주 상태",
                            ["강세유지", "꺾임"],
                            key=_leader_status_key,
                        )
                        # "SNAPSHOT 종목 밖이라 자동 판정 불가" 안내는 동적 종목 목록 도입
                        # 이후 거의 항상 떠서 불필요한 잡음이라는 지적으로 제거(2026-07-13).
                        # 자동 판정이 실제로 가능한 경우에만 참고 문구를 보여준다.
                        if _leader_auto["available"]:
                            st.caption(
                                f"자동 판정 참고: 고점 대비 {_leader_auto['drop_pct']:.1f}% "
                                "(-7% 이상이면 꺾임). 필요하면 위에서 직접 바꿀 수 있습니다."
                            )
                        if selected_leader_status == "꺾임":
                            st.warning("대장주 꺾임 — 후발주 청산 검토")

            # 위에서 입력한 상태·세부 항목을 요약 표(updated_rows)에도 반영한다 — 이전에는
            # 위젯 값이 각자의 session_state 키에만 저장되고 표로 다시 합쳐지지 않아
            # 테마 참고판 표가 항상 빈 채로 보이는 문제가 있었다.
            for _row in updated_rows:
                if _row.get("테마") == _theme_detail_selected:
                    _row["상태"] = selected_status
                    _row["대장주상태"] = selected_leader_status
                    for field_name, value in selected_detail_values.items():
                        _row[field_name] = value
                    break

    st.session_state[KR_THEME_WATCH_DATA_KEY] = updated_rows
    st.caption("테마 참고판은 session_state에서만 유지되며 DB·점수·판정에는 반영되지 않습니다.")


def _render_kr_primary_actions():
    # ---- 0→1→2 한 번에 미리보기 생성 (자동 저장 아님, DB 미기록) ----
    # 0단계/1단계 버튼과 동일한 조회 로직을 그대로 재사용한다. 실행 결과는 기존 버튼과 같은
    # session_state 키(kr_mood_auto_results, snap_auto_fill_results)에 저장된다.
    if st.session_state.get("kr_auto_preview_running"):
        st.caption("판단 준비 실행 중입니다.")
    elif st.session_state.get("kr_auto_preview_done_at"):
        if st.session_state.get("kr_auto_preview_last_error"):
            st.caption(f"판단 준비 실패: {st.session_state['kr_auto_preview_last_error']} · 문제가 있을 때 단계별 다시 실행을 이용하세요.")
        else:
            st.caption("판단 준비 완료: 시장 분위기 확인 / 오늘 주가 입력 / 미리보기 생성")

    # 2026-07-13 사용자 요청으로 "오늘 판단 준비" 안내 헤더/캡션 제거(자동실행으로 이미
    # 처리되어 안내문이 불필요하다는 지적) — 상태 캡션(실행중/완료/실패)은 실질 정보라 유지.
    action_cols = st.columns(1)
    repair_expander = st.expander("문제가 있을 때 단계별 다시 실행", expanded=False)
    with action_cols[0]:
        if st.button(
            "오늘 종목 판단 준비하기",
            key="kr_auto_preview_run",
            type="primary",
            disabled=bool(st.session_state.get("kr_auto_preview_running")),
        ):
            if st.session_state.get("kr_auto_preview_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_auto_preview_running"] = True

                _stage_status_display = {"ok": "예", "partial": "부분", "fail": "아니오"}

                # 0) 거래대금 상위 종목 재선정 — 장 시작 전 로그인 때 3종목짜리 엉터리
                # 목록이 세션에 박히면 이 버튼을 눌러도 계속 3종목만 보이던 문제
                # (2026-07-15) 수정. 프래그먼트 rerun에서는 모듈 상단의 SNAPSHOT_STOCKS
                # 재계산이 실행되지 않으므로, 이번 실행에서 바로 반영되도록 전역도 갱신한다.
                _kr_reselected = _short_cached_top_kr_stocks_by_amount(12)
                if _kr_reselected and len(_kr_reselected) >= MIN_TRUSTED_TOP_STOCKS:
                    st.session_state["dynamic_snapshot_stocks"] = _kr_reselected
                    st.session_state["dynamic_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    globals()["SNAPSHOT_STOCKS"] = _kr_reselected
                    globals()["SNAPSHOT_NAME_TO_TICKER"] = {s["name"]: s["ticker"] for s in _kr_reselected}

                # 1) 0단계: 시장 분위기 자동 확인 (공용 함수, 일부 실패해도 중단하지 않음)
                _mood_run_result = run_kr_mood_auto_check(force_refresh=True)
                _stage0_status = _stage_status_display[_mood_run_result["status"]]

                # 2) 1단계: 오늘 주가 자동 채우기 (공용 함수, 실패 종목은 건너뛰고 기존 입력값 유지)
                _fill_run_result = run_kr_snapshot_auto_fill(force_refresh=True)
                _stage1_status = _stage_status_display[_fill_run_result["status"]]

                # 3) 2단계: 미리보기 생성 (DB 저장 호출 없음 — build_kr_stage2_preview()는 조회 전용)
                _auto_stage2_preview = build_kr_stage2_preview()
                _stage2_generated = bool(_auto_stage2_preview["rows"])

                st.session_state["kr_auto_preview_stage0_status"] = _stage0_status
                st.session_state["kr_auto_preview_stage1_status"] = _stage1_status
                st.session_state["kr_auto_preview_stage2_generated"] = _stage2_generated
                if _mood_run_result["status"] == "fail" and _fill_run_result["status"] == "fail":
                    st.session_state["kr_auto_preview_last_error"] = (
                        "0단계·1단계 모두 조회 실패 (네트워크 또는 데이터 제공처 문제)"
                    )
                elif not _stage2_generated:
                    st.session_state["kr_auto_preview_last_error"] = "2단계 미리보기를 만들 종목 데이터가 없습니다."
                else:
                    st.session_state["kr_auto_preview_last_error"] = None
                st.session_state["kr_auto_preview_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_auto_preview_running"] = False
    with repair_expander:
        if st.button(
            "0단계 시장 분위기 자동 확인",
            key="snap_mood_auto_check",
            disabled=bool(st.session_state.get("kr_mood_auto_running")),
        ):
            if st.session_state.get("kr_mood_auto_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_mood_auto_running"] = True
                _mood_run_result = run_kr_mood_auto_check(force_refresh=True)
                st.session_state["kr_mood_auto_last_error"] = _mood_run_result["message"]
                st.session_state["kr_mood_auto_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_mood_auto_running"] = False
    with repair_expander:
        if st.button(
            "① 오늘 주가 자동 채우기",
            key="snap_auto_fill",
            disabled=bool(st.session_state.get("kr_snapshot_auto_fill_running")),
        ):
            if st.session_state.get("kr_snapshot_auto_fill_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_snapshot_auto_fill_running"] = True
                _fill_run_result = run_kr_snapshot_auto_fill(force_refresh=True)
                st.session_state["kr_snapshot_auto_fill_last_error"] = _fill_run_result["message"]
                st.session_state["kr_snapshot_auto_fill_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_snapshot_auto_fill_running"] = False

    st.caption(
        "0→1→2 버튼은 미리보기만 만듭니다. DB에 저장하지 않으며, 실제 기록을 남기려면 "
        "아래 '③ 국내장 기록 바로 저장' 버튼을 따로 눌러야 합니다."
    )


def _render_kr_fable_mockup1_preview():
    """기존 한국장 입력·저장 흐름 위에 실제 세션 데이터로 그리는 읽기 전용 안전 미리보기."""
    st.markdown(
        """
        <style>
        .jarvis-m1-stepper {
            display: none !important;
        }
        .jarvis-m1-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 8.5rem), 1fr));
            gap: 0.55rem;
            margin: 0.9rem 0 1.15rem;
        }
        .jarvis-m1-strip-item {
            min-width: 0;
            border: 1px solid #31415d;
            border-radius: 12px;
            padding: 0.7rem 0.75rem;
            background: #0d1524;
        }
        .jarvis-m1-strip-label {
            display: block;
            color: #8ea1bc;
            font-size: 19px;
            font-weight: 700;
        }
        .jarvis-m1-strip-value {
            display: block;
            color: #f8fafc;
            font-size: 22px;
            font-weight: 800;
            margin-top: 0.18rem;
            overflow-wrap: anywhere;
        }
        .jarvis-m1-strip-value.jarvis-m1-up { color: #ff4b4b; }
        .jarvis-m1-strip-value.jarvis-m1-down { color: #4b9fff; }
        .jarvis-m1-stepper {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
            gap: 0.65rem;
            margin-bottom: 0.3rem;
        }
        .jarvis-m1-step {
            border: 1px solid #31415d;
            border-radius: 13px;
            padding: 0.8rem;
            background: #121b2c;
            color: #9fb0c8;
        }
        .jarvis-m1-step-active {
            border-color: #38bdf8;
            background: #102c46;
            box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.22);
            color: #f8fafc;
        }
        .jarvis-m1-step-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            margin-right: 0.35rem;
            background: #25334a;
            color: #bae6fd;
            font-size: 0.78rem;
            font-weight: 850;
        }
        .jarvis-m1-step-title {
            font-weight: 800;
        }
        .jarvis-m1-step-copy {
            display: block;
            margin: 0.45rem 0 0 2.05rem;
            color: #91a3bd;
            font-size: 0.78rem;
        }
        .jarvis-m1-stock-list {
            display: grid;
            gap: 0.5rem;
            margin-top: 0.7rem;
        }
        .jarvis-m1-stock {
            border: 1px solid #31415d;
            border-left-width: 5px;
            border-radius: 11px;
            padding: 0.72rem;
            background: #111827;
        }
        .jarvis-m1-stock-selected {
            box-shadow: 0 0 0 1px #7dd3fc;
            background: #16243a;
        }
        .jarvis-m1-stock-green { border-left-color: #22c55e; }
        .jarvis-m1-stock-yellow { border-left-color: #eab308; }
        .jarvis-m1-stock-orange { border-left-color: #f97316; }
        .jarvis-m1-stock-gray { border-left-color: #94a3b8; }
        .jarvis-m1-stock-red { border-left-color: #ef4444; }
        .jarvis-m1-stock-name {
            color: #f8fafc;
            font-weight: 850;
        }
        .jarvis-m1-stock-meta {
            color: #99abc4;
            font-size: 0.78rem;
            margin-top: 0.2rem;
        }
        .jarvis-m1-chip-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 9rem), 1fr));
            gap: 0.5rem;
        }
        .jarvis-m1-chip {
            border: 1px solid #334155;
            border-radius: 999px;
            padding: 0.55rem 0.7rem;
            background: #111827;
            color: #e2e8f0;
            font-size: 0.78rem;
            text-align: center;
        }
        .jarvis-m1-chip-note {
            display: block;
            color: #8192aa;
            font-size: 0.64rem;
            margin-top: 0.12rem;
        }
        .jarvis-m1-panel {
            border: 1px solid #334155;
            border-radius: 14px;
            padding: 1rem;
            background: #111827;
            color: #e2e8f0;
            min-height: 7rem;
        }
        .jarvis-m1-muted {
            color: #91a3bd;
            font-size: 0.86rem;
        }
        @media (max-width: 720px) {
            .jarvis-m1-strip,
            .jarvis-m1-stepper,
            .jarvis-m1-chip-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    active_step = 2 if st.session_state.get("snap_auto_fill_results") else 1
    steps = [
        (1, "오늘 기록", "시장·주가 자동 채우기"),
        (2, "종목 판단", "점수 확인·리스크 입력"),
        (3, "저장 확인", "보고서·실매매 입력"),
        (4, "복기 / 통계", "태그별·셋업별 성과"),
    ]
    step_html = "".join(
        f'<div class="jarvis-m1-step {"jarvis-m1-step-active" if number == active_step else ""}">'
        f'<span class="jarvis-m1-step-number">{number}</span>'
        f'<span class="jarvis-m1-step-title">{title}</span>'
        f'<span class="jarvis-m1-step-copy">{copy}</span>'
        "</div>"
        for number, title, copy in steps
    )
    st.markdown(f'<div class="jarvis-m1-stepper">{step_html}</div>', unsafe_allow_html=True)

    # 2026-07-13 사용자 요청으로 "오늘 기록 실행" 안내 헤더/캡션 제거 — 로그인 시 자동실행되므로
    # 이제는 안내문 없이 버튼(및 문제 시 재실행용 확장 패널)만 노출한다.
    _render_kr_primary_actions()

    # 미리보기 데이터는 반드시 버튼 처리(_render_kr_primary_actions) 뒤에 계산한다 —
    # 예전에는 버튼보다 먼저 계산해서, 버튼이 거래대금 상위 12종목을 재선정해도 그
    # 실행에서는 여전히 이전 종목(3개)만 보였다(2026-07-15 사용자 반복 지적의 원인).
    # 종목 카드 클릭처럼 입력값이 그대로인 rerun에서는 메모이즈된 결과를 재사용한다.
    stage2_preview = _memoized_kr_stage2_preview()
    rows = stage2_preview["rows"]

    st.markdown("### 종목 판단 미리보기")
    if not rows:
        st.info("0→1→2 미리보기를 실행하면 종목 판단 화면이 표시됩니다.")
    else:
        left_col, right_col = st.columns([0.34, 0.66], gap="large")
        with left_col:
            trade_mode = st.selectbox(
                "매매유형 선택",
                ["전체", "단타", "스윙"],
                key="mockup1_trade_mode",
            )
            show_all_modes = trade_mode == "전체"
            score_key = "swing_score" if trade_mode == "스윙" else "danta_score"
            verdict_key = "swing_verdict" if trade_mode == "스윙" else "danta_verdict"
            if show_all_modes:
                sorted_rows = sorted(
                    rows, key=lambda row: max(row["danta_score"], row["swing_score"]), reverse=True
                )
            else:
                sorted_rows = sorted(rows, key=lambda row: row[score_key], reverse=True)
            rows_by_ticker = {row["ticker"]: row for row in sorted_rows}
            ticker_options = list(rows_by_ticker)
            pending_ticker = st.session_state.pop("mockup1_pending_ticker", None)
            selectbox_index = 0
            if pending_ticker in ticker_options:
                selectbox_index = ticker_options.index(pending_ticker)
                st.session_state["mockup1_selected_ticker"] = pending_ticker
            selected_ticker = st.selectbox(
                "종목 선택",
                ticker_options,
                index=selectbox_index,
                format_func=lambda ticker: rows_by_ticker[ticker]["name"],
                key="mockup1_selected_ticker",
            )

            sector_by_ticker = {stock["ticker"]: stock["sector"] for stock in SNAPSHOT_STOCKS}
            verdict_colors = {
                "추천 후보": "green",
                "감시": "yellow",
                "확인 필요": "orange",
                "보류(선반영)": "gray",
                "제외": "red",
            }
            stock_html = []
            for row in sorted_rows:
                verdict = row[verdict_key]
                color = verdict_colors.get(verdict, "gray")
                selected_class = "jarvis-m1-stock-selected" if row["ticker"] == selected_ticker else ""
                confirmation = "예" if row["needs_confirmation"] else "-"
                stock_html.append(
                    f'<div class="jarvis-m1-stock jarvis-m1-stock-{color} {selected_class}">'
                    f'<div class="jarvis-m1-stock-name">{row["name"]}</div>'
                    f'<div class="jarvis-m1-stock-meta">{sector_by_ticker.get(row["ticker"], "-")} · '
                    f'{_display_verdict_name(verdict)} · {row[score_key]}점</div>'
                    f'<div class="jarvis-m1-stock-meta">확인 필요: {confirmation}</div>'
                    "</div>"
                )
            _candidate_style_rules = [
                '[class*="st-key-mockup1_candidate_"] button, '
                '[class*="st-key-mockup1_candidate_"] button p { font-size: 21px !important; }'
            ]
            for row in sorted_rows:
                if show_all_modes:
                    _verdict_candidates = [
                        _display_verdict_name(row["danta_verdict"]),
                        _display_verdict_name(row["swing_verdict"]),
                    ]
                else:
                    _verdict_candidates = [_display_verdict_name(row[verdict_key])]
                if "1순위 후보" in _verdict_candidates:
                    _candidate_color = "#4ade80"
                elif "관찰 후보" in _verdict_candidates:
                    _candidate_color = "#15803d"
                else:
                    _candidate_color = None
                if _candidate_color:
                    _candidate_style_rules.append(
                        f'[class*="st-key-mockup1_candidate_{row["ticker"]}"] button p '
                        f'{{ color: {_candidate_color} !important; font-weight: 800 !important; }}'
                    )
            st.markdown(f"<style>{''.join(_candidate_style_rules)}</style>", unsafe_allow_html=True)

            _candidate_label_gap = " " * 4
            for row in sorted_rows:
                candidate_key = f"mockup1_candidate_{row['ticker']}"
                if show_all_modes:
                    # st.button 라벨은 st.markdown의 색상 문법(:blue[...]/:green[...])
                    # 일부를 지원한다. Streamlit이 제공하는 색은 정해진 이름(blue/green
                    # 등)뿐이라 "코발트색"/"형광초록색" 같은 정확한 색상은 지정할 수
                    # 없어 가장 가까운 blue/green으로 표시한다.
                    _candidate_label = (
                        f"{row['name']}{_candidate_label_gap}"
                        f":blue[단타 {_display_verdict_name(row['danta_verdict'])} {row['danta_score']}점]"
                        f"{_candidate_label_gap}"
                        f":green[스윙 {_display_verdict_name(row['swing_verdict'])} {row['swing_score']}점]"
                    )
                else:
                    _candidate_label = (
                        f"{row['name']}{_candidate_label_gap}{_display_verdict_name(row[verdict_key])}"
                        f"{_candidate_label_gap}{row[score_key]}점"
                    )
                if st.button(
                    _candidate_label,
                    key=candidate_key,
                    help=f"{sector_by_ticker.get(row['ticker'], '-')} · 확인 필요: {'예' if row['needs_confirmation'] else '아니오'}",
                ):
                    st.session_state["mockup1_pending_ticker"] = row["ticker"]
                    _fragment_scoped_rerun()

        selected_row = rows_by_ticker[selected_ticker]
        selected_verdict = selected_row[verdict_key]
        current_value = _get_snapshot_value(selected_ticker, "current")
        with right_col:
            st.markdown(f"## {selected_row['name']}")
            if show_all_modes:
                st.caption(
                    f"단타 {_display_verdict_name(selected_row['danta_verdict'])} "
                    f"{selected_row['danta_score']}점 · "
                    f"스윙 {_display_verdict_name(selected_row['swing_verdict'])} "
                    f"{selected_row['swing_score']}점"
                )
            else:
                st.caption(
                    f"{trade_mode} · {_display_verdict_name(selected_verdict)} · "
                    f"{selected_row[score_key]}점"
                )
            st.markdown(
                """
                <style>
                .st-key-mockup1_detail_panel [data-testid="stMetricValue"] {
                    font-size: 26px !important;
                }
                .st-key-mockup1_detail_panel [data-testid="stMetricLabel"] {
                    font-size: 17px !important;
                }
                .st-key-mockup1_detail_panel [data-testid="stMarkdownContainer"] p,
                .st-key-mockup1_detail_panel [data-testid="stText"] {
                    font-size: 18px !important;
                    line-height: 1.6 !important;
                }
                .jarvis-m1-pct-card {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    /* 2026-07-15 사용자 지적: 옆의 현재가/시총대비거래대금(st.metric)은
                       테두리 박스가 있는데 시가대비/고점대비만 맨 텍스트라 어긋나
                       보였다 — 같은 stMetric 박스 스타일(테두리·배경·모서리)을 맞춘다. */
                    background-color: rgba(23, 26, 33, 0.92);
                    border: 1px solid #303642;
                    border-radius: 10px;
                    padding: 10px 14px;
                }
                .jarvis-m1-pct-label {
                    font-size: 17px;
                    color: #9aa5b1;
                }
                .jarvis-m1-pct-value {
                    font-size: 26px;
                    font-weight: 700;
                }
                .jarvis-m1-pct-up { color: #ff4b4b; }
                .jarvis-m1-pct-down { color: #4b9fff; }
                .jarvis-m1-score-highlight {
                    font-size: 20px !important;
                    font-weight: 800 !important;
                    color: #facc15 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            _mockup1_detail_container = st.container(key="mockup1_detail_panel")

        def _pct_card_html(label, value):
            if value is None:
                return (
                    f'<div class="jarvis-m1-pct-card">'
                    f'<span class="jarvis-m1-pct-label">{label}</span>'
                    f'<span class="jarvis-m1-pct-value">-</span></div>'
                )
            css_class = "jarvis-m1-pct-up" if value > 0 else "jarvis-m1-pct-down" if value < 0 else ""
            return (
                f'<div class="jarvis-m1-pct-card">'
                f'<span class="jarvis-m1-pct-label">{label}</span>'
                f'<span class="jarvis-m1-pct-value {css_class}">{_fmt_signed_pct(value)}</span></div>'
            )

        with _mockup1_detail_container:
            metric_current, metric_open, metric_high, metric_turnover = st.columns(4)
            metric_current.metric(
                "현재가",
                "-" if current_value is None else f"{current_value:,.0f}",
                delta=(
                    None
                    if selected_row["change_pct"] is None
                    else _fmt_signed_pct(selected_row["change_pct"])
                ),
            )
            with metric_open:
                st.markdown(_pct_card_html("시가 대비", selected_row["open_pos_pct"]), unsafe_allow_html=True)
            with metric_high:
                st.markdown(_pct_card_html("고점 대비", selected_row["high_drop_pct"]), unsafe_allow_html=True)
            metric_turnover.metric(
                "시총 대비 거래대금",
                "-"
                if selected_row["turnover_ratio_pct"] is None
                else f"{selected_row['turnover_ratio_pct']:.2f}%",
            )

            if trade_mode != "스윙":
                # "단타" 또는 "전체"(전체는 단타 기준으로 대표 표시, 아래 "전체 근거"
                # expander에 단타·스윙 둘 다 항상 표시됨)
                selected_score = selected_row["danta_score"]
                selected_score_reason = selected_row["danta_score_reason"]
                selected_top_reason = selected_row["danta_top_candidate_reason"]
                selected_penalty_reason = selected_row["danta_penalty_reason"]
            else:
                selected_score = selected_row["swing_score"]
                selected_score_reason = selected_row["swing_score_reason"]
                selected_top_reason = selected_row["swing_top_candidate_reason"]
                selected_penalty_reason = selected_row["swing_penalty_reason"]

            def _labeled_line(label, value):
                st.markdown(
                    f'<div style="font-size:18px;line-height:1.7;margin:4px 0;">'
                    f'<span style="color:#60a5fa;font-weight:700;">{label}:</span> '
                    f'<span style="color:#4ade80;font-weight:700;">{value}</span></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("#### 핵심 근거")
            st.markdown(
                f'<div class="jarvis-m1-score-highlight">점수: {selected_score}</div>',
                unsafe_allow_html=True,
            )
            _labeled_line("점수 근거", selected_score_reason)
            _labeled_line("1순위 후보 근거", selected_top_reason)
            _labeled_line("감점 이유", selected_penalty_reason)
            _labeled_line("매수 확정 여부", "미확정")

            with st.expander("전체 근거", expanded=False):
                _labeled_line("단타 점수", selected_row["danta_score"])
                _labeled_line("단타 판정", _display_verdict_name(selected_row["danta_verdict"]))
                _labeled_line("단타 점수 근거", selected_row["danta_score_reason"])
                _labeled_line("단타 1순위 후보 근거", selected_row["danta_top_candidate_reason"])
                _labeled_line("단타 감점 이유", selected_row["danta_penalty_reason"])
                _labeled_line("스윙 점수", selected_row["swing_score"])
                _labeled_line("스윙 판정", _display_verdict_name(selected_row["swing_verdict"]))
                _labeled_line("스윙 점수 근거", selected_row["swing_score_reason"])
                _labeled_line("스윙 1순위 후보 근거", selected_row["swing_top_candidate_reason"])
                _labeled_line("스윙 감점 이유", selected_row["swing_penalty_reason"])
                _labeled_line("시가 대비", _fmt_signed_pct(selected_row["open_pos_pct"]))
                _labeled_line("고점 대비", _fmt_signed_pct(selected_row["high_drop_pct"]))
                _labeled_line(
                    "시총 대비 거래대금",
                    "-"
                    if selected_row["turnover_ratio_pct"] is None
                    else f"{selected_row['turnover_ratio_pct']:.2f}%",
                )
                _labeled_line("validation_errors", selected_row["validation_errors"] or "-")
                _labeled_line("단타 매수 확정 조건", selected_row["danta_buy_confirm_condition"])
                _labeled_line("스윙 매수 확정 조건", selected_row["swing_buy_confirm_condition"])

            _render_risk_and_warning_inputs(selected_ticker, "KR", compact=True)

    st.markdown("#### 테마 참고판")
    _render_kr_theme_chip_editor()
    st.caption("등록된 검증 일정이 없습니다.")

    st.caption("실제 자동조회·입력·저장은 아래 기존 화면을 사용합니다.")


def _render_us_stock_judgment_preview():
    """미국장 '종목 판단 미리보기' — 한국장 목업1 미리보기와 같은 레이아웃(종목 선택·
    점수 카드·핵심 근거·리스크 관리)을 미국 스윙 점수 엔진으로 그린다(2026-07-15
    사용자 반복 요청: 캡처의 KR 화면과 동일한 형태). CSS는 KR 목업이 먼저 렌더링하며
    주입한 jarvis-m1-* 클래스를 그대로 재사용한다. DB 저장 없음, 매수 신호 아님.
    """
    stage2_preview = build_us_stage2_preview()
    rows = stage2_preview["rows"]
    st.markdown("### 종목 판단 미리보기")
    if not rows:
        st.info("아직 불러온 종목 데이터가 없습니다. 위 '오늘 미국 종목 판단 준비하기'를 눌러주세요.")
        return

    left_col, right_col = st.columns([0.34, 0.66], gap="large")
    with left_col:
        sorted_rows = sorted(rows, key=lambda row: row["total_score"], reverse=True)
        rows_by_ticker = {row["ticker"]: row for row in sorted_rows}
        ticker_options = list(rows_by_ticker)
        pending_ticker = st.session_state.pop("us_mockup_pending_ticker", None)
        selectbox_index = 0
        if pending_ticker in ticker_options:
            selectbox_index = ticker_options.index(pending_ticker)
            st.session_state["us_mockup_selected_ticker"] = pending_ticker
        selected_ticker = st.selectbox(
            "종목 선택",
            ticker_options,
            index=selectbox_index,
            format_func=lambda ticker: rows_by_ticker[ticker]["name"],
            key="us_mockup_selected_ticker",
        )

        _us_candidate_style_rules = [
            '[class*="st-key-us_mockup_candidate_"] button, '
            '[class*="st-key-us_mockup_candidate_"] button p { font-size: 21px !important; }'
        ]
        for row in sorted_rows:
            if row["verdict"] == "추천 후보":
                _us_candidate_style_rules.append(
                    f'[class*="st-key-us_mockup_candidate_{row["ticker"]}"] button p '
                    '{ color: #4ade80 !important; font-weight: 800 !important; }'
                )
        st.markdown(f"<style>{''.join(_us_candidate_style_rules)}</style>", unsafe_allow_html=True)

        _gap = " " * 4
        for row in sorted_rows:
            if st.button(
                f"{row['name']}{_gap}:green[스윙 {row['verdict']} {row['total_score']:.0f}점]",
                key=f"us_mockup_candidate_{row['ticker']}",
                help=f"{row.get('sector', '-')} · 확인 필요: {'예' if row['needs_confirmation'] else '아니오'}",
            ):
                st.session_state["us_mockup_pending_ticker"] = row["ticker"]
                _fragment_scoped_rerun()

    selected_row = rows_by_ticker[selected_ticker]
    current_value = _get_snapshot_value(selected_ticker, "current")
    with right_col:
        st.markdown(f"## {selected_row['name']}")
        st.caption(f"스윙 {selected_row['verdict']} · 총점 {selected_row['total_score']:.0f}점 ({selected_row['tier_label']})")
        _us_detail_container = st.container(key="us_mockup_detail_panel")

    def _us_pct_card_html(label, value):
        if value is None:
            return (
                f'<div class="jarvis-m1-pct-card">'
                f'<span class="jarvis-m1-pct-label">{label}</span>'
                f'<span class="jarvis-m1-pct-value">-</span></div>'
            )
        css_class = "jarvis-m1-pct-up" if value > 0 else "jarvis-m1-pct-down" if value < 0 else ""
        return (
            f'<div class="jarvis-m1-pct-card">'
            f'<span class="jarvis-m1-pct-label">{label}</span>'
            f'<span class="jarvis-m1-pct-value {css_class}">{_fmt_signed_pct(value)}</span></div>'
        )

    with _us_detail_container:
        metric_current, metric_open, metric_high, metric_turnover = st.columns(4)
        metric_current.metric(
            "현재가",
            "-" if current_value is None else f"{current_value:,.2f}",
            delta=(
                None
                if selected_row["change_pct"] is None
                else _fmt_signed_pct(selected_row["change_pct"])
            ),
        )
        with metric_open:
            st.markdown(_us_pct_card_html("시가 대비", selected_row["open_pos_pct"]), unsafe_allow_html=True)
        with metric_high:
            st.markdown(_us_pct_card_html("고점 대비", selected_row["high_drop_pct"]), unsafe_allow_html=True)
        metric_turnover.metric(
            "시총 대비 거래대금",
            "-"
            if selected_row["turnover_ratio_pct"] is None
            else f"{selected_row['turnover_ratio_pct']:.2f}%",
        )

        def _us_labeled_line(label, value):
            st.markdown(
                f'<div style="font-size:18px;line-height:1.7;margin:4px 0;">'
                f'<span style="color:#60a5fa;font-weight:700;">{label}:</span> '
                f'<span style="color:#4ade80;font-weight:700;">{value}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("#### 핵심 근거")
        st.markdown(
            f'<div class="jarvis-m1-score-highlight">점수: {selected_row["total_score"]:.0f}</div>',
            unsafe_allow_html=True,
        )
        _us_labeled_line(
            "점수 근거",
            f"{selected_row['upside_note']}, {selected_row['close_pos_note']}, {selected_row['momentum_note']}",
        )
        _us_labeled_line("1순위 후보 근거", selected_row["priority_reason"])
        _us_labeled_line("감점 이유", selected_row["deduction_reason"])
        _us_labeled_line("매수 확정 여부", "미확정")

        with st.expander("전체 근거", expanded=False):
            _us_labeled_line("상승률 점수 (0~20)", f"{selected_row['upside_score']:.0f} — {selected_row['upside_note']}")
            _us_labeled_line("종가 위치 점수 (0~20)", f"{selected_row['close_pos_score']:.0f} — {selected_row['close_pos_note']}")
            _us_labeled_line("시장 분위기 (참고, 0~15)", f"{selected_row['mood_score']:.0f} — {selected_row['mood_note']}")
            _us_labeled_line("재료 점수 (0~20)", f"{selected_row['material_score']:.0f} — {selected_row['material_note']}")
            _us_labeled_line("거래/탄력 점수 (0~15)", f"{selected_row['momentum_score']:.0f} — {selected_row['momentum_note']}")
            _us_labeled_line("위험 감점", f"{selected_row['risk_score']:.0f} — {selected_row['risk_note']}")
            _us_labeled_line("시가 대비", _fmt_signed_pct(selected_row["open_pos_pct"]))
            _us_labeled_line("고점 대비", _fmt_signed_pct(selected_row["high_drop_pct"]))
            _us_labeled_line(
                "시총 대비 거래대금",
                "-"
                if selected_row["turnover_ratio_pct"] is None
                else f"{selected_row['turnover_ratio_pct']:.2f}%",
            )
            _us_labeled_line("validation_errors", selected_row["validation_errors"] or "-")
            _us_labeled_line("매수 확정 조건", selected_row["buy_confirm_condition"])

        _render_risk_and_warning_inputs(selected_ticker, "US", compact=True)


def _render_review_tag_editors(saved_item, display_name, trade_mode, key_prefix="tab4_"):
    """Render the existing review tag/filter editors for one report item."""
    item_id = saved_item.get("id")
    if not item_id:
        return
    with st.expander("복기 태그·필터 기록", expanded=False):
        with st.expander(f"필터 무시 기록 - {display_name} ({trade_mode})"):
            fi_key = f"{key_prefix}filterignore_{item_id}"
            fi_options = ["미입력", "아니오", "예"]
            fi_default = {"YES": "예", "NO": "아니오"}.get(saved_item.get("filter_ignored"), "미입력")
            filter_ignored_in = st.selectbox("필터 무시 여부", fi_options, index=fi_options.index(fi_default), key=f"{fi_key}_ignored")
            stored_codes = [c.strip() for c in (saved_item.get("filter_ignore_reason") or "").split(",") if c.strip()]
            stored_tag_codes = [c for c in stored_codes if c in FILTER_IGNORE_TAG_CODE_TO_LABEL]
            stored_emotion_codes = [c for c in stored_codes if c in EMOTION_TAG_CODE_TO_LABEL]
            if filter_ignored_in == "예":
                ignore_tags_in = st.multiselect("필터 무시 태그", [label for _, label in FILTER_IGNORE_TAG_OPTIONS], default=[FILTER_IGNORE_TAG_CODE_TO_LABEL[c] for c in stored_tag_codes], key=f"{fi_key}_tags")
                emotion_options = ["미입력"] + [label for _, label in EMOTION_TAG_OPTIONS]
                emotion_default = EMOTION_TAG_CODE_TO_LABEL.get(stored_emotion_codes[0], "미입력") if stored_emotion_codes else "미입력"
                emotion_in = st.selectbox("감정 태그", emotion_options, index=emotion_options.index(emotion_default), key=f"{fi_key}_emotion")
            else:
                ignore_tags_in = []
                emotion_in = "미입력"
                st.caption("필터 무시 여부를 '예'로 선택하면 태그를 입력할 수 있습니다.")
            memo_in = st.text_input("자유 메모", value=saved_item.get("filter_ignore_memo") or "", key=f"{fi_key}_memo")
            st.caption(f"참고 R수익률(기존 값, 새로 계산하지 않음): {_fmt_result_r(saved_item.get('result_r'))}")
            if st.button("필터 무시 기록 저장", key=f"{fi_key}_save"):
                final_filter_ignored = {"예": "YES", "아니오": "NO"}.get(filter_ignored_in)
                final_tag_codes = [FILTER_IGNORE_TAG_LABEL_TO_CODE[label] for label in ignore_tags_in]
                if emotion_in != "미입력":
                    final_tag_codes.append(EMOTION_TAG_LABEL_TO_CODE[emotion_in])
                db.update_report_item_filter_ignore(
                    item_id,
                    final_filter_ignored,
                    ",".join(final_tag_codes) if final_tag_codes else None,
                    memo_in.strip() or None,
                )
                st.success("필터 무시 기록이 저장되었습니다.")
                st.rerun()
        with st.expander(f"플레이북 태그 - {display_name} ({trade_mode})"):
            pb_key = f"{key_prefix}playbook_{item_id}"
            stored_codes = [c.strip() for c in (saved_item.get("playbook_tags") or "").split(",") if c.strip()]
            pb_tags_in = st.multiselect("플레이북 태그", [label for _, label in PLAYBOOK_TAG_OPTIONS], default=[PLAYBOOK_TAG_CODE_TO_LABEL[c] for c in stored_codes if c in PLAYBOOK_TAG_CODE_TO_LABEL], key=f"{pb_key}_tags")
            if st.button("플레이북 태그 저장", key=f"{pb_key}_save"):
                db.update_report_item_playbook_tags(
                    item_id,
                    ",".join(PLAYBOOK_TAG_LABEL_TO_CODE[label] for label in pb_tags_in) or None,
                )
                st.success("플레이북 태그가 저장되었습니다.")
                st.rerun()
        with st.expander(f"테마 태그 - {display_name} ({trade_mode})"):
            theme_key = f"{key_prefix}themetag_{item_id}"
            theme_stored = db.parse_theme_tags(saved_item.get("theme_tags"))
            st.caption(f"현재 테마 태그: {', '.join(theme_stored) if theme_stored else '없음'}")
            theme_tags_in = st.multiselect("테마 태그", THEME_TAG_OPTIONS, default=[t for t in theme_stored if t in THEME_TAG_OPTIONS], key=f"{theme_key}_tags")
            if st.button("테마 태그 저장", key=f"{theme_key}_save"):
                db.update_report_item_theme_tags(item_id, theme_tags_in)
                st.success("테마 태그가 저장되었습니다.")
                st.rerun()


def _render_risk_plan_preview(stock_name, ticker, risk_fields):
    risk_fields = risk_fields or {}
    def _value(key, price=False):
        value = risk_fields.get(key)
        if value in (None, ""):
            return "미입력"
        if price:
            return _fmt_actual_entry_price_display(value) or "미입력"
        return f"{value}일" if key == "expected_holding_days" else str(value)

    with st.expander(f"진입 계획 확인 — {stock_name} ({ticker})", expanded=False):
        st.write(f"계획 매수가: {_value('entry_price', price=True)}")
        st.write(f"손절가: {_value('stop_loss_price', price=True)}")
        st.write(f"목표가: {_value('target_price', price=True)}")
        st.write(f"예상 보유기간: {_value('expected_holding_days')}")


# ---- 로그인 직후 병렬 워밍업 (2026-07-15 사용자 요청: "순차 실행이 원인이면 순차
# 실행하지 마라") ----
# 예전에는 한국장 체인(시장자료→분위기→종목→테마→도박사)과 미국장 체인이 전부
# 순서대로 실행돼 로그인 후 첫 화면까지 15~20초가 걸렸다. 어차피 전부 캐시 함수라,
# 여기서 한꺼번에 병렬로 데워두면 아래 탭 렌더링은 캐시 히트만 하게 되어 전체 시간이
# "가장 느린 항목 하나"의 시간으로 줄어든다. 실패는 각 항목별로 무시한다(아래 탭
# 렌더링이 어차피 개별 실패를 처리한다).
if not st.session_state.get("parallel_warmup_done"):
    try:
        with ThreadPoolExecutor(max_workers=10) as _warm_executor:
            _warm_phase1 = [
                _warm_executor.submit(_cached_fetch_market_overview, "KR"),
                _warm_executor.submit(_cached_fetch_market_overview, "US"),
                _warm_executor.submit(_cached_kr_mood_source_results),
                _warm_executor.submit(_cached_fetch_kr_theme_snapshot),
                _warm_executor.submit(_cached_fetch_us_sector_snapshot),
                _warm_executor.submit(_cached_fetch_us_theme_indicators),
                _warm_executor.submit(_cached_fetch_bookmaker_snapshot),
            ]
            _warm_kr_top_future = _warm_executor.submit(_cached_get_top_kr_stocks_by_amount, 12)
            _warm_us_top_future = _warm_executor.submit(_cached_get_top_us_stocks_by_amount, 8)
            try:
                _warm_kr_top = _warm_kr_top_future.result()
            except Exception:
                _warm_kr_top = []
            try:
                _warm_us_top = _warm_us_top_future.result()
            except Exception:
                _warm_us_top = []
            _warm_kr_list = (
                _warm_kr_top if (_warm_kr_top and len(_warm_kr_top) >= MIN_TRUSTED_TOP_STOCKS)
                else DEFAULT_SNAPSHOT_STOCKS
            )
            _warm_us_list = (
                _warm_us_top if (_warm_us_top and len(_warm_us_top) >= 5)
                else DEFAULT_US_SNAPSHOT_STOCKS
            )
            _warm_phase2 = [
                _warm_executor.submit(
                    _cached_kr_snapshot_results, tuple(s["ticker"] for s in _warm_kr_list)
                ),
                _warm_executor.submit(
                    _cached_kr_snapshot_results, tuple(s["ticker"] for s in _warm_us_list)
                ),
            ]
            for _warm_future in as_completed(_warm_phase1 + _warm_phase2):
                try:
                    _warm_future.result()
                except Exception:
                    pass
    except Exception:
        pass
    st.session_state["parallel_warmup_done"] = True


KR_AUTO_RUN_VERSION = "2026-07-14-previous-close-v2"

@st.fragment
def _render_tab_kr():
    # 프래그먼트 rerun에서는 모듈 상단의 `SNAPSHOT_STOCKS = session_state or 기본값`
    # 재계산이 실행되지 않아, 버튼 클릭으로 종목 목록이 바뀌어도 다음 클릭까지 옛
    # 목록이 남았다(2026-07-15 "아직도 3종목" 원인 중 하나). 매 프래그먼트 실행마다
    # 세션 기준으로 전역을 다시 맞춘다.
    # 이전 세션/장 시작 전 로그인에서 3종목짜리 불신 목록이 세션에 박혀 있으면 버리고
    # 재선정을 트리거한다(2026-07-15 "아직 3종목" 자가 복구).
    _dyn_kr = st.session_state.get("dynamic_snapshot_stocks")
    if _dyn_kr and len(_dyn_kr) < MIN_TRUSTED_TOP_STOCKS:
        st.session_state.pop("dynamic_snapshot_stocks", None)
        st.session_state["kr_auto_run_stage1_done"] = False
    globals()["SNAPSHOT_STOCKS"] = st.session_state.get("dynamic_snapshot_stocks") or DEFAULT_SNAPSHOT_STOCKS
    globals()["SNAPSHOT_NAME_TO_TICKER"] = {s["name"]: s["ticker"] for s in SNAPSHOT_STOCKS}
    # 로그인 직후 한국장 탭을 열면 "오늘 한국장 자료 불러오기"/"오늘 종목 판단
    # 준비하기"/"테마 참고판 자동 조회" 3개 동작을 세션당 한 번 순서대로 실행한다.
    # 로그인 성공 전환 화면이 떠 있는 실행에서는 조회하지 않고 다음 rerun부터 시작한다.
    # 이미 열려 있던 브라우저 세션도 보정 버전이 달라지면 완료 플래그를 한 번 초기화해
    # 사용자가 버튼을 다시 누르지 않아도 새 기준으로 자동 조회한다.
    if st.session_state.get("kr_auto_run_version") != KR_AUTO_RUN_VERSION:
        st.session_state["kr_auto_run_stage1_done"] = False
        st.session_state["kr_auto_run_stage2_done"] = False
        st.session_state["kr_theme_auto_fetch_pending"] = False
        st.session_state["kr_auto_run_version"] = KR_AUTO_RUN_VERSION
    if not st.session_state.get("kr_auto_run_stage1_done"):
        _kr_auto_run_stocks = _cached_get_top_kr_stocks_by_amount(12)
        if _kr_auto_run_stocks and len(_kr_auto_run_stocks) >= MIN_TRUSTED_TOP_STOCKS:
            st.session_state["dynamic_snapshot_stocks"] = _kr_auto_run_stocks
            st.session_state["dynamic_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 로그인 전환 실행에서는 rerun 없이 같은 실행에서 stage2가 이어지므로,
            # 전역을 즉시 갱신하지 않으면 stage2가 기본 7종목만 채워 첫 화면이
            # 3~4종목이 된다(2026-07-15 사용자 반복 확인 — 초기 로딩만 3종목).
            globals()["SNAPSHOT_STOCKS"] = _kr_auto_run_stocks
            globals()["SNAPSHOT_NAME_TO_TICKER"] = {s["name"]: s["ticker"] for s in _kr_auto_run_stocks}
        st.session_state["kr_auto_run_stage1_done"] = True
        if not _login_transition_pending:
            st.rerun()
    if not st.session_state.get("kr_auto_run_stage2_done"):
        st.session_state["kr_market_overview_result"] = _cached_fetch_market_overview("KR")
        st.session_state["kr_market_overview_checked_at"] = st.session_state["kr_market_overview_result"]["checked_at"]

        _kr_auto_mood_result = run_kr_mood_auto_check()
        _kr_auto_fill_result = run_kr_snapshot_auto_fill()
        _kr_auto_stage2_preview = build_kr_stage2_preview()
        st.session_state["kr_auto_preview_stage0_status"] = {"ok": "예", "partial": "부분", "fail": "아니오"}[
            _kr_auto_mood_result["status"]
        ]
        st.session_state["kr_auto_preview_stage1_status"] = {"ok": "예", "partial": "부분", "fail": "아니오"}[
            _kr_auto_fill_result["status"]
        ]
        st.session_state["kr_auto_preview_stage2_generated"] = bool(_kr_auto_stage2_preview["rows"])
        st.session_state["kr_auto_preview_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        st.session_state["kr_theme_auto_fetch_pending"] = True
        st.session_state["kr_bookmaker_auto_fetch_pending"] = True
        st.session_state["kr_auto_run_stage2_done"] = True
        # 로그인 전환 실행 중에는 테마 조회가 끝나며 발생하는 rerun 뒤에도 전환
        # 오버레이를 한 번 보여준다. 자동 3단계를 즉시 수행하면서 기존 로그인
        # 성공 연출이 사라지지 않게 하는 상태 전달일 뿐 화면 자체는 변경하지 않는다.
        if _login_transition_pending:
            st.session_state["login_transition_pending"] = True
        if not _login_transition_pending:
            st.rerun()

    _render_market_overview("KR")
    st.subheader("한국장")
    _render_kr_fable_mockup1_preview()
    st.markdown("---")
    st.markdown("### 기존 입력·자동조회·저장 화면")
    st.caption("아래 기존 기능은 변경하지 않았습니다. 목업 승인 전까지 실제 입력과 저장은 기존 화면을 사용합니다.")
    # 1. 시장 분위기 (기본값은 전부 "미입력" — 위험해 보이는 강함/상승/순매수 기본값 금지)
    # 이 값은 미국장 탭의 시장 분위기 점수/상한 계산에서도 그대로 사용됩니다.
    st.caption("시장 분위기는 자비스가 먼저 자동 확인합니다. 안 나오거나 부족한 항목만 직접 입력하세요.")
    st.markdown("### 0단계 시장 분위기 입력(선택)")
    st.caption("입력하지 않아도 계산은 가능합니다. 입력값은 매수 신호가 아니라 오늘 판단의 참고값입니다.")
    st.caption("시장 분위기·주가 자동조회·미리보기 실행은 화면 상단에서 진행합니다.")

    if st.session_state.get("kr_mood_auto_results"):
        if not st.session_state.get("kr_mood_auto_any_ok"):
            st.warning(
                "시장 분위기 자동 확인 실패. 네트워크 또는 데이터 제공처 문제일 수 있습니다. "
                "수동 입력 없이도 ① 오늘 주가 자동 채우기는 사용할 수 있습니다."
            )
        else:
            st.markdown("#### 0단계 시장 분위기 자동 확인 결과")
            st.markdown(
                """
                <style>
                .st-key-kr_mood_auto_table [role="row"] {
                    min-height: 24px !important;
                }
                .st-key-kr_mood_auto_table [role="columnheader"],
                .st-key-kr_mood_auto_table [role="gridcell"] {
                    padding-top: 2px !important;
                    padding-bottom: 2px !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            def _mood_change_pct_styler(col):
                styles = []
                for val in col:
                    if isinstance(val, str) and val.startswith("+"):
                        styles.append("color: #ff4b4b")
                    elif isinstance(val, str) and val.startswith("-") and val != "-":
                        styles.append("color: #4b9fff")
                    else:
                        styles.append("")
                return styles

            def _mood_verdict_styler(col):
                styles = []
                for val in col:
                    if isinstance(val, str) and val.startswith("강함"):
                        styles.append("color: #ff4b4b")
                    elif isinstance(val, str) and val.startswith("보합"):
                        styles.append("color: #22c55e")
                    else:
                        styles.append("")
                return styles

            _mood_styled_df = (
                pd.DataFrame(st.session_state["kr_mood_auto_results"])
                .style.apply(_mood_change_pct_styler, subset=["등락률(%)"])
                .apply(_mood_verdict_styler, subset=["판정"])
            )
            st.dataframe(
                _mood_styled_df,
                width="stretch",
                hide_index=True,
                key="kr_mood_auto_table",
            )
            st.caption("SOXX/SMH는 미국 반도체 ETF입니다. 둘 다 강하면 국내 반도체 투자심리에 우호적입니다.")
            _soxx_row = next(
                (r for r in st.session_state["kr_mood_auto_results"] if r["항목"] == "SOXX"), None
            )
            _smh_row = next(
                (r for r in st.session_state["kr_mood_auto_results"] if r["항목"] == "SMH"), None
            )
            if _soxx_row and _smh_row and "확인 불가" not in (_soxx_row["판정"], _smh_row["판정"]):
                _soxx_strong = _soxx_row["판정"].startswith("강함")
                _soxx_weak = _soxx_row["판정"].startswith("약함")
                _smh_strong = _smh_row["판정"].startswith("강함")
                _smh_weak = _smh_row["판정"].startswith("약함")
                if _soxx_strong and _smh_strong:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#1b4332", "#2d6a4f", "#7ee6a8"
                    _mood_verdict_msg = (
                        "반도체 우호 신호 — SOXX와 SMH가 모두 강세입니다. 미국 반도체 투자심리가 "
                        "우호적이므로 삼성전자·SK하이닉스 등 국내 반도체 대형주 분위기에 긍정적입니다."
                    )
                elif _soxx_weak and _smh_weak:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#4a2e05", "#d97706", "#fbbf6a"
                    _mood_verdict_msg = (
                        "반도체 부담 신호 — SOXX와 SMH가 모두 약세입니다. 미국 반도체 투자심리가 "
                        "약하므로 국내 반도체 대형주에는 부담 요인입니다."
                    )
                else:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#1e3a5f", "#3b82f6", "#93c5fd"
                    _mood_verdict_msg = (
                        "반도체 혼조 신호 — SOXX와 SMH 흐름이 엇갈립니다. "
                        "국내 반도체주는 추가 확인이 필요합니다."
                    )
                st.markdown(
                    f"""
                    <div style="background-color:{_mood_verdict_bg};border:2px solid {_mood_verdict_border};
                    border-radius:10px;padding:16px;margin-top:8px;">
                    <span style="font-size:1.15rem;font-weight:800;color:{_mood_verdict_text};">
                    {_mood_verdict_msg}
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


    with st.expander("오늘 거래대금 상위 종목 다시 선정", expanded=False):
        st.caption(
            "코스피/코스닥 전체 종목 중 오늘(가장 최근 완료된 거래일) 거래대금 상위 종목을 "
            "자동으로 뽑아 아래 종목 목록을 대체합니다. 우선주·스팩·관리종목·투자주의환기종목은 "
            "제외합니다. 저장되지 않으며 이 세션에서만 유지됩니다(다시 접속하면 기본 "
            f"{len(DEFAULT_SNAPSHOT_STOCKS)}종목으로 돌아갑니다)."
        )
        _dynamic_top_n = st.number_input(
            "몇 종목?", min_value=5, max_value=30, value=20, step=1, key="dynamic_snapshot_n"
        )
        if st.button("거래대금 상위 종목 다시 불러오기", key="dynamic_snapshot_refresh"):
            _new_stocks = price_data.get_top_kr_stocks_by_amount(int(_dynamic_top_n))
            if _new_stocks:
                st.session_state["dynamic_snapshot_stocks"] = _new_stocks
                st.session_state["dynamic_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"{len(_new_stocks)}개 종목으로 갱신했습니다.")
                st.rerun()
            else:
                st.warning("거래대금 상위 종목 조회 실패(네트워크 문제일 수 있습니다). 기존 목록을 유지합니다.")
        if st.session_state.get("dynamic_snapshot_updated_at"):
            st.caption(
                f"마지막 갱신: {st.session_state['dynamic_snapshot_updated_at']} · "
                f"현재 {len(SNAPSHOT_STOCKS)}종목 추적 중"
            )
        else:
            st.caption(f"아직 갱신 안 함 · 기본 {len(SNAPSHOT_STOCKS)}종목(고정) 사용 중")

    # 2. 간편 스냅샷 입력 (붙여넣기 자동 채우기)
    st.markdown("---")
    with st.expander("① 오늘 주가 채우기 - 직접 붙여넣기", expanded=False):
        st.caption(
            "형식: 종목명 / 현재가 / 전일종가 / 시가 / 장중고가 / 장중저가 / 거래대금 / 시가총액 "
            "(등록된 7개 종목만 인식하며, 숫자에 쉼표가 있어도 처리됩니다. 맨 뒤에 거래량을 "
            "추가한 종목명 / ... / 시가총액 / 거래량(9개 필드) 형식도 지원하며, 거래량 없이 "
            "기존 8개 필드로 붙여넣어도 그대로 동작합니다.)"
        )
        quick_snapshot_text = st.text_area(
            "주가 직접 붙여넣기",
            key="snap_quick_text",
            height=140,
            placeholder=(
                "삼성전자 / 309,000 / 300,000 / 320,000 / 325,000 / 308,000 / 2,500,000,000,000 / 1,840,000,000,000,000\n"
                "기아 / 157,100 / 152,000 / 153,000 / 161,000 / 155,000 / 800,000,000,000 / 61,500,000,000,000"
            ),
        )
        if st.button("붙여넣은 주가 채우기", key="snap_quick_fill"):
            updates, warnings = parse_quick_snapshot_text(quick_snapshot_text)
            for ticker, values in updates.items():
                for field, value in values.items():
                    st.session_state[f"snap_{ticker}_{field}"] = value
            st.session_state["snap_quick_fill_count"] = len(updates)
            st.session_state["snap_quick_fill_warnings"] = warnings
            st.rerun()

        if st.session_state.get("snap_quick_fill_count") is not None:
            st.success(f"붙여넣은 주가 채우기 완료: 종목 {st.session_state['snap_quick_fill_count']}개 반영됨")
        for w in st.session_state.get("snap_quick_fill_warnings", []):
            st.warning(w)

    # 2-1. 기본값 자동 채우기 (yfinance 우선, FinanceDataReader 보조 — 저장 없음)
    st.markdown("---")
    st.caption(
        "아래 버튼은 네이버 등에서 직접 찾아 입력하지 않도록, yfinance(우선)/FinanceDataReader(보조)로 "
        "가장 최근 완료된 거래일 기준 시세를 조회해 채워줍니다. 실시간 시세가 아니며, 거래대금·"
        "시가총액은 근사값입니다. 조회 결과는 저장되지 않고 화면 계산에만 쓰입니다."
    )
    st.caption("시장 분위기·주가 자동조회·미리보기 실행은 화면 상단에서 진행합니다.")

    if st.session_state.get("snap_auto_fill_results"):
        auto_fill_results = st.session_state["snap_auto_fill_results"]
        _render_auto_fetch_status_summary(auto_fill_results, SNAPSHOT_STOCKS, "kr_")
        st.caption("거래대금·시가총액은 근사값입니다 (거래량×현재가, 상장주식수×현재가). 정확한 실제 값이 아닙니다.")

    # 3. 계산 결과 요약표 (입력 카드보다 위에 표시 — session_state를 위젯 생성 전에 미리 읽음)
    st.markdown("---")
    st.markdown("### ② 오늘 주가 계산 결과")
    st.caption(
        "메모는 자동판정이 아니라 참고용 경고 문구입니다 (예: 고점 대비 밀림률이 -3% 이하이면 "
        "'고점 대비 밀림 큼'). 관심 후보/관찰 후보 같은 판정은 이 화면에서 만들지 않습니다."
    )
    st.caption(
        "정렬 기준: 단기 관심점수 높은 순 → 며칠 관심점수 높은 순 → 시총대비 거래대금 높은 순입니다. "
        "점수는 매수 신호가 아니라 관심 후보 정렬 기준입니다."
    )
    st.caption("※ 시가대비·고점대비·저점대비는 모두 오늘 장중 기준입니다. 전일 대비가 아닙니다.")

    result_rows = []
    snapshot_calc_data = []
    for s in SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            # 입력값이 하나도 없는 종목은 계산 결과표에서 제외한다(0으로 나오는 것 방지).
            # 종목별 상세 입력 카드에는 그대로 남아 있어 언제든 입력할 수 있다.
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        low_recover_pct = _safe_pct_diff(current, low)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)

        memos = []
        if high_drop_pct is not None and high_drop_pct <= -3:
            memos.append("고점 대비 밀림 큼")
        if open_pos_pct is not None:
            memos.append("시가 위 유지" if open_pos_pct >= 0 else "시가 아래")
        if turnover_ratio_pct is not None and turnover_ratio_pct >= 5:
            memos.append("시총 대비 거래대금 확인 필요")

        danta_score = compute_snapshot_reference_score(
            "단타", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct
        )
        swing_score = compute_snapshot_reference_score(
            "스윙", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct
        )

        result_rows.append(
            {
                "종목명": s["name"],
                "단기 관심 점수": int(round(danta_score)),
                "며칠 관심 점수": int(round(swing_score)),
                "메모": "; ".join(memos) if memos else "-",
                "현재가": "-" if current is None else f"{current:,.0f}",
                "전일대비(%)": _fmt_signed_pct(change_pct),
                "시가대비(오늘)": _fmt_signed_pct(open_pos_pct),
                "고점대비(오늘)": _fmt_signed_pct(high_drop_pct),
                "저점대비(오늘)": _fmt_signed_pct(low_recover_pct),
                "시총대비 거래대금(%)": _fmt_pct(turnover_ratio_pct),
                "섹터": s["sector"],
                "_sort_key": (
                    danta_score, swing_score,
                    turnover_ratio_pct if turnover_ratio_pct is not None else float("-inf"),
                ),
                "_change_pct_raw": change_pct,
                "_open_pos_raw": open_pos_pct,
                "_high_drop_raw": high_drop_pct,
                "_low_recover_raw": low_recover_pct,
            }
        )
        snapshot_calc_data.append(
            {
                "name": s["name"],
                "ticker": s["ticker"],
                "change_pct": change_pct,
                "open_pos_pct": open_pos_pct,
                "high_drop_pct": high_drop_pct,
                "turnover_ratio_pct": turnover_ratio_pct,
                "memos": memos,
                "danta_score": danta_score,
                "swing_score": swing_score,
                "risk_fields": _collect_risk_fields(ticker),
                "validation_errors": _validate_snapshot_price_inputs(
                    s["name"], current, open_price, high, low,
                    _get_snapshot_value(ticker, "volume"), turnover,
                ),
            }
        )

    result_rows.sort(key=lambda r: r["_sort_key"], reverse=True)
    change_pct_raw_list = [r.get("_change_pct_raw") for r in result_rows]
    open_pos_raw_list = [r.get("_open_pos_raw") for r in result_rows]
    high_drop_raw_list = [r.get("_high_drop_raw") for r in result_rows]
    low_recover_raw_list = [r.get("_low_recover_raw") for r in result_rows]
    for r in result_rows:
        r.pop("_sort_key", None)
        r.pop("_change_pct_raw", None)
        r.pop("_open_pos_raw", None)
        r.pop("_high_drop_raw", None)
        r.pop("_low_recover_raw", None)

    if not result_rows:
        st.info("아직 입력된 종목이 없습니다. 아래 '종목별 상세 입력' 카드나 '주가 직접 붙여넣기'로 값을 넣어주세요.")
    else:
        def _signed_pct_color_styler(raw_list):
            def _apply(col):
                styles = []
                for raw in raw_list:
                    if raw is None or raw == 0:
                        styles.append("")
                    elif raw > 0:
                        styles.append("color: #ff4b4b")
                    else:
                        styles.append("color: #4b9fff")
                return styles
            return _apply

        def _score_tier_styler(col):
            # 2026-07-15 사용자 요청: 관심 점수 칸에 색이 전혀 없어 구분이 안 됐다 —
            # 80점 이상/70점 이상을 단계별 색으로 표시한다(매수 신호 아님, 구분용).
            styles = []
            for val in col:
                try:
                    score = float(val)
                except (TypeError, ValueError):
                    styles.append("")
                    continue
                if score >= 80:
                    styles.append("color: #39ff14; font-weight: 800")
                elif score >= 70:
                    styles.append("color: #facc15; font-weight: 700")
                else:
                    styles.append("")
            return styles

        result_df = pd.DataFrame(result_rows)
        styled_result_df = (
            result_df.style
            .apply(_signed_pct_color_styler(change_pct_raw_list), subset=["전일대비(%)"])
            .apply(_signed_pct_color_styler(open_pos_raw_list), subset=["시가대비(오늘)"])
            .apply(_signed_pct_color_styler(high_drop_raw_list), subset=["고점대비(오늘)"])
            .apply(_signed_pct_color_styler(low_recover_raw_list), subset=["저점대비(오늘)"])
            .apply(_score_tier_styler, subset=["단기 관심 점수", "며칠 관심 점수"])
            .set_properties(
                subset=[
                    "단기 관심 점수", "며칠 관심 점수", "현재가", "전일대비(%)",
                    "시가대비(오늘)", "고점대비(오늘)", "저점대비(오늘)", "시총대비 거래대금(%)",
                ],
                **{"text-align": "right"},
            )
        )
        # 표 안에서 스크롤하지 않고 전체 행이 한 번에 보이도록 행 수에 맞춰 높이를 계산한다
        # (기본 높이는 고정이라 종목이 늘어나면 안에서 스크롤이 생겼다, 2026-07-13 사용자 요청).
        _result_table_height = 38 * (len(result_rows) + 1) + 3
        st.dataframe(
            styled_result_df, width="stretch", hide_index=True, height=_result_table_height
        )
        st.caption("시총 대비 거래대금 '확인 필요' 기준은 5% 이상(1차 버전 임시 기준)입니다.")
        st.caption(
            "점수는 자동매수 신호가 아니라 장중 후보 비교용 참고 점수입니다. 외부 환경과 "
            "종가 품질이 미입력인 경우 최고점은 제한됩니다."
        )

        st.caption("리스크 관리 공통 설정은 화면 상단의 선택 종목 상세에서 진행합니다.")

        # 4. 종목별 상세 입력 카드 (기본 접힘) — 계산 결과 요약표를 먼저 보여준 뒤 아래에 배치한다.
        st.markdown("---")
        st.markdown("### 종목별 상세 입력")
        st.caption("카드를 펼치면 직접 숫자를 입력/수정할 수 있습니다. 0은 '입력 안 함'으로 취급합니다.")

        _kr_detail_options = ["선택 안 함"] + [s["name"] for s in SNAPSHOT_STOCKS]
        _kr_detail_selected = st.selectbox(
            "상세 입력할 종목 선택",
            _kr_detail_options,
            key="kr_snapshot_detail_selector",
        )

        if _kr_detail_selected != "선택 안 함":
            _chart_ticker = SNAPSHOT_NAME_TO_TICKER.get(_kr_detail_selected)
            if _chart_ticker:
                with st.expander(f"{_kr_detail_selected} 일봉 차트 (최근 3개월)", expanded=False):
                    _chart_df = _fetch_kr_chart_history(_chart_ticker)
                    if _chart_df is None or _chart_df.empty:
                        st.info("차트 데이터를 불러오지 못했습니다(네트워크 문제일 수 있습니다).")
                    else:
                        st.line_chart(_chart_df["Close"], height=260)
                        st.caption("종가 기준 최근 3개월 일봉입니다. 참고용이며 점수·판정에는 반영되지 않습니다.")

        for s in SNAPSHOT_STOCKS:
            if _kr_detail_selected != s["name"]:
                continue
            prefix = f"snap_{s['ticker']}_"
            with st.expander(f"{s['name']} / {s['sector']}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                c1.number_input("현재가", value=0.0, step=100.0, key=prefix + "current")
                c2.number_input("전일종가", value=0.0, step=100.0, key=prefix + "prev_close")
                c3.number_input("시가", value=0.0, step=100.0, key=prefix + "open")
                c4.number_input("장중고가", value=0.0, step=100.0, key=prefix + "high")

                c5, c6, c7, c8 = st.columns(4)
                c5.number_input("장중저가", value=0.0, step=100.0, key=prefix + "low")
                c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
                c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")
                c8.number_input("거래량", value=0.0, step=1000.0, key=prefix + "volume")
                _render_snapshot_calc_summary(s["ticker"])
                st.markdown("---")
                st.caption("리스크 입력은 화면 상단의 선택 종목 상세에서 진행합니다.")
                st.caption(
                    "상세 카드는 입력·수정 전용이며 카드 내부에는 저장 실행 버튼이 없습니다. "
                    "최종 저장은 위쪽 ‘▼ 저장 전 확인으로 이동’ 구역에서 진행합니다."
                )

        st.caption("이 문장은 매수 추천이 아니라, 새 기록 입력칸에 붙여넣기 위한 초안입니다. 필요하면 수정 후 저장하세요.")
        if st.button("기록 문장 만들기", key="snap_make_briefing_text"):
            lines = [
                "[기본]",
                "시장 범위: KR",
                "시점 구분: 장중",
                "브리핑 단계: 장중 스냅샷 기반 판단",
                "신호 분류: 재확인 신호",
                "",
                "[오늘의 결론]",
                "오늘 주가 확인 기준: 입력된 종목의 고점 대비 밀림, 시가 대비 위치, 시총 대비 거래대금을 "
                "기준으로 기록 입력용 초안을 생성함. 자동매수 추천이 아님.",
                "",
                "[종목]",
            ]
            for calc in snapshot_calc_data:
                trade_mode, verdict = classify_snapshot_temp(
                    calc["high_drop_pct"], calc["open_pos_pct"], calc["turnover_ratio_pct"]
                )
                if trade_mode == "단타":
                    basis = (
                        f"고점대비 {_fmt_signed_pct(calc['high_drop_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"{calc['memos'][0] if calc['memos'] else '고점 대비 밀림 큼'}"
                    )
                elif trade_mode == "스윙":
                    basis = (
                        f"전일대비 {_fmt_signed_pct(calc['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(calc['turnover_ratio_pct'])}"
                    )
                else:
                    basis = (
                        f"전일대비 {_fmt_signed_pct(calc['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(calc['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(calc['turnover_ratio_pct'])}"
                    )
                lines.append(
                    f"{calc['name']} / {calc['ticker']} / KR / {trade_mode} / {verdict} / 재확인 신호 / {basis}"
                )
            st.session_state["snap_briefing_text"] = "\n".join(lines)

        if st.session_state.get("snap_briefing_text"):
            st.text_area(
                "기록 문장 (복사해서 '새 기록 입력' 탭의 쉽게 붙여넣는 입력칸에 붙여넣으세요)",
                value=st.session_state["snap_briefing_text"],
                height=160,
                key="snap_briefing_text_display",
            )

        st.markdown("---")
        st.markdown("#### 2단계 판단 미리보기 (저장 전, 자동 계산)")
        st.caption(
            "아직 저장하지 않은 상태의 참고용 미리보기입니다. 매수 신호가 아니며, 실제로 기록을 "
            "남기려면 아래 '▼ 저장 전 확인으로 이동' 버튼을 따로 눌러야 합니다. 이 미리보기 자체는 "
            "DB에 아무 것도 저장하지 않습니다."
        )
        _stage2_preview = _memoized_kr_stage2_preview()
        st.caption(
            f"0단계 시장 분위기 반영: {'예' if _stage2_preview['stage0_reflected'] else '아니오 (수동 또는 미실행)'} / "
            f"1단계 오늘 주가 자동 채우기 반영: {'예' if _stage2_preview['stage1_reflected'] else '아니오 (수동 입력 값 기준)'}"
        )
        if not _stage2_preview["rows"]:
            st.info("아직 입력된 종목이 없어 2단계 판단 미리보기를 만들 수 없습니다.")
        else:
            _stage2_rows_sorted = sorted(
                _stage2_preview["rows"],
                key=lambda r: (r["danta_score"] + r["swing_score"]) / 2,
                reverse=True,
            )

            def _stage2_verdict_styler(col):
                styles = []
                for val in col:
                    if val == "보류":
                        styles.append("color: #4b9fff")
                    elif val == "재확인":
                        styles.append("color: #facc15")
                    elif val == "관찰 후보":
                        styles.append("color: #4b9fff")
                    elif isinstance(val, str) and val.startswith("1순위"):
                        styles.append("color: #39ff14; font-weight: 800")
                    else:
                        styles.append("")
                return styles

            def _stage2_dim_styler(col):
                # 이 컬럼들은 "② 오늘 주가 계산 결과" 표에도 이미 나오는 값이라
                # 여기서는 흐리게 표시해 이 표에서만 새로 보이는 정보와 구분한다.
                return ["color: #64748b"] * len(col)

            def _stage2_confirm_styler(col):
                return [
                    "color: #f97316; font-weight: 800" if val == "예" else ""
                    for val in col
                ]

            _stage2_df = pd.DataFrame(
                [
                    {
                        "종목명": r["name"],
                        "단기 관심 점수": int(round(r["danta_score"])),
                        "며칠 관심 점수": int(round(r["swing_score"])),
                        "단타 판단": _display_verdict_name(r["danta_verdict"]),
                        "스윙 판단": _display_verdict_name(r["swing_verdict"]),
                        "확인 필요": "예" if r["needs_confirmation"] else "-",
                    }
                    for r in _stage2_rows_sorted
                ]
            )
            _stage2_styled_df = (
                _stage2_df.style
                .apply(_stage2_dim_styler, subset=["종목명", "단기 관심 점수", "며칠 관심 점수"])
                .apply(_stage2_verdict_styler, subset=["단타 판단"])
                .apply(_stage2_confirm_styler, subset=["확인 필요"])
            )
            st.dataframe(_stage2_styled_df, width="stretch", hide_index=True)
            st.markdown("종목별 1순위 근거 / 감점 이유 (미리보기)")
            for r in _stage2_rows_sorted:
                with st.expander(
                    f"{r['name']} — 단타 {_display_verdict_name(r['danta_verdict'])} / "
                    f"스윙 {_display_verdict_name(r['swing_verdict'])}"
                ):
                    st.write(f"단타 1순위 근거: {r['danta_top_candidate_reason']}")
                    st.write(f"단타 감점 이유: {r['danta_penalty_reason']}")
                    st.write(f"스윙 1순위 근거: {r['swing_top_candidate_reason']}")
                    st.write(f"스윙 감점 이유: {r['swing_penalty_reason']}")
                    if r["validation_errors"]:
                        st.warning("확인 필요: " + "; ".join(r["validation_errors"]))

        with st.expander("참고자료 · 공시·뉴스", expanded=False):
            st.caption("종목 판단을 보조하는 참고자료입니다. 펼친 뒤 버튼을 눌렀을 때만 조회합니다.")
            _render_kr_dart_disclosure_panel()
            _render_market_naver_news_panel(
                "KR",
                SNAPSHOT_STOCKS,
                "📰 한국장 최근 뉴스 자동 확인",
                "kr_naver_news_check_button",
                "kr_naver_news_results",
                "kr_naver_news_checked_at",
            )

        # 3-2. 국내장 기록 바로 저장 (새 기록 입력 화면을 거치지 않고 이 화면에서 바로 저장)
        # 한국 종목(SNAPSHOT_STOCKS)만 대상으로 한다 — 미국 종목은 여기 나오지 않는다.
        st.markdown("---")
        st.markdown("### 국내장 기록 바로 저장")
        st.caption(
            "현재 저장 기능을 유지한 확인 구역입니다. 첫 버튼은 즉시 저장하지 않고 저장 전 확인만 엽니다. "
            "실제 DB 저장은 확인 내용 아래의 최종 저장 버튼에서만 실행됩니다."
        )
        st.caption(
            "위 표의 한국 종목 7개만 대상으로 시장 KR / 단타·스윙을 함께 저장합니다. "
            "버튼을 누르면 바로 저장하지 않고 먼저 저장 전 확인 미리보기를 보여줍니다."
        )
        if st.button("▼ 저장 전 확인으로 이동", key="kr_quick_save", disabled=not snapshot_calc_data):
          st.session_state["kr_show_save_preview"] = True
          st.session_state.pop("kr_quick_preview_rows", None)
          st.session_state.pop("kr_quick_day_conclusion", None)
          st.session_state.pop("kr_quick_basis_text", None)
          all_kr_validation_errors = [e for calc in snapshot_calc_data for e in calc["validation_errors"]]
          if all_kr_validation_errors:
            st.error("입력값 오류로 저장할 수 없습니다:\n" + "\n".join(f"- {e}" for e in all_kr_validation_errors))
          else:
            # 미리보기(build_kr_stage2_preview())와 같은 판단 계산값을 재사용한다 — 미리보기와
            # 저장 결과가 서로 다른 값으로 보이는 사고를 막기 위함. 저장 흐름(items_to_save 구성,
            # db.save_report() 호출)은 그대로 두고, 판단 계산 부분만 대체한다.
            _stage2_preview_for_save = _memoized_kr_stage2_preview()
            _stage2_rows_by_ticker = {r["ticker"]: r for r in _stage2_preview_for_save["rows"]}

            kr_preview_rows = []
            for calc in snapshot_calc_data:
                _s2row = _stage2_rows_by_ticker.get(calc["ticker"])
                if _s2row is not None:
                    danta_score = _s2row["danta_score"]
                    swing_score = _s2row["swing_score"]
                    danta_verdict = _s2row["danta_verdict"]
                    swing_verdict = _s2row["swing_verdict"]
                    danta_score_reason = _s2row["danta_score_reason"]
                    danta_penalty_reason = _s2row["danta_penalty_reason"]
                    swing_score_reason = _s2row["swing_score_reason"]
                    swing_penalty_reason = _s2row["swing_penalty_reason"]
                    danta_top_candidate_reason = _s2row["danta_top_candidate_reason"]
                    swing_top_candidate_reason = _s2row["swing_top_candidate_reason"]
                else:
                    # 방어적 대비책: 미리보기에 해당 종목이 없는 예외적인 경우 기존 방식대로 직접 계산한다.
                    danta_score = calc["danta_score"]
                    swing_score = calc["swing_score"]
                    danta_verdict = _kr_danta_verdict(danta_score)
                    swing_verdict = _kr_swing_verdict(swing_score)
                    danta_score_reason, danta_penalty_reason = _kr_preview_reasons(
                        calc["change_pct"], calc["open_pos_pct"], calc["high_drop_pct"], calc["turnover_ratio_pct"], "단타"
                    )
                    swing_score_reason, swing_penalty_reason = _kr_preview_reasons(
                        calc["change_pct"], calc["open_pos_pct"], calc["high_drop_pct"], calc["turnover_ratio_pct"], "스윙"
                    )
                    danta_top_candidate_reason = _kr_top_candidate_reason_text(
                        "단타", danta_score, _display_verdict_name(danta_verdict)
                    )
                    swing_top_candidate_reason = _kr_top_candidate_reason_text(
                        "스윙", swing_score, _display_verdict_name(swing_verdict)
                    )
                _preview_source_row = _s2row or {}
                change_pct = _preview_source_row.get("change_pct", calc["change_pct"])
                open_pos_pct = _preview_source_row.get("open_pos_pct", calc["open_pos_pct"])
                high_drop_pct = _preview_source_row.get("high_drop_pct", calc["high_drop_pct"])
                turnover_ratio_pct = _preview_source_row.get("turnover_ratio_pct", calc["turnover_ratio_pct"])
                turnover = _preview_source_row.get("turnover", _get_snapshot_value(calc["ticker"], "turnover"))
                risk_fields = _preview_source_row.get("risk_fields", calc["risk_fields"])
                danta_buy_confirm_condition = _preview_source_row.get(
                    "danta_buy_confirm_condition", _auto_buy_confirm_condition("단타", "KR")
                )
                swing_buy_confirm_condition = _preview_source_row.get(
                    "swing_buy_confirm_condition", _auto_buy_confirm_condition("스윙", "KR")
                )
                kr_preview_rows.append(
                    {
                        "name": calc["name"],
                        "ticker": calc["ticker"],
                        "danta_score": danta_score,
                        "swing_score": swing_score,
                        "danta_verdict": danta_verdict,
                        "swing_verdict": swing_verdict,
                        "change_pct": change_pct,
                        "open_pos_pct": open_pos_pct,
                        "high_drop_pct": high_drop_pct,
                        "turnover_ratio_pct": turnover_ratio_pct,
                        "turnover": turnover,
                        "danta_score_reason": danta_score_reason,
                        "danta_penalty_reason": danta_penalty_reason,
                        "swing_score_reason": swing_score_reason,
                        "swing_penalty_reason": swing_penalty_reason,
                        "danta_top_candidate_reason": danta_top_candidate_reason,
                        "swing_top_candidate_reason": swing_top_candidate_reason,
                        "danta_buy_confirm_condition": danta_buy_confirm_condition,
                        "swing_buy_confirm_condition": swing_buy_confirm_condition,
                        "risk_fields": risk_fields,
                    }
                )
            danta_counts = {"감시": 0, "확인 필요": 0, "보류(선반영)": 0}
            swing_counts = {"추천 후보": 0, "감시": 0, "보류(선반영)": 0}
            for row in kr_preview_rows:
                danta_counts[row["danta_verdict"]] = danta_counts.get(row["danta_verdict"], 0) + 1
                swing_counts[row["swing_verdict"]] = swing_counts.get(row["swing_verdict"], 0) + 1
            kr_day_conclusion = (
                f"오늘 주가 확인 기반 국내장 자동 기록: 총 {len(kr_preview_rows)}종목. "
                f"단타 {_display_verdict_name('감시')} {danta_counts['감시']}개/"
                f"{_display_verdict_name('확인 필요')} {danta_counts['확인 필요']}개/"
                f"{_display_verdict_name('보류(선반영)')} {danta_counts['보류(선반영)']}개, "
                f"스윙 {_display_verdict_name('추천 후보')} {swing_counts['추천 후보']}개/"
                f"{_display_verdict_name('감시')} {swing_counts['감시']}개/"
                f"{_display_verdict_name('보류(선반영)')} {swing_counts['보류(선반영)']}개. "
                "점수는 자동매수 신호가 아니라 오늘 주가 확인 표를 바탕으로 한 참고용 판단입니다."
            )
            kr_basis_text = "\n".join(
                f"{row['name']}: 단기 관심 점수 {row['danta_score']}점 -> 단타 {_display_verdict_name(row['danta_verdict'])}, "
                f"며칠 관심 점수 {row['swing_score']}점 -> 스윙 {_display_verdict_name(row['swing_verdict'])}"
                for row in kr_preview_rows
            )
            st.session_state["kr_quick_preview_rows"] = kr_preview_rows
            st.session_state["kr_quick_day_conclusion"] = kr_day_conclusion
            st.session_state["kr_quick_basis_text"] = kr_basis_text

        if st.session_state.get("kr_show_save_preview") and st.session_state.get("kr_quick_preview_rows"):
            kr_preview_rows = st.session_state["kr_quick_preview_rows"]
            preview_timing_class = db.classify_timing_class(datetime.now())
            st.markdown("#### 저장 전 확인 → 최종 저장")
            st.caption("이 구역의 최종 버튼 1개에서만 실제 DB 저장이 실행됩니다.")
            st.write("시장: KR")
            st.write(f"장 구분: {preview_timing_class}")
            st.write("판단 시점: 오늘 주가 확인 기반 국내장 판단")
            st.write(f"오늘 요약: {st.session_state['kr_quick_day_conclusion']}")
            st.write("판단 근거:")
            st.code(st.session_state["kr_quick_basis_text"])
            for _risk_row in kr_preview_rows:
                _render_risk_plan_preview(
                    _risk_row["name"], _risk_row["ticker"], _risk_row.get("risk_fields")
                )

            st.markdown("저장될 종목 목록 (자동계산 미리보기)")
            kr_danta_rank = _rank_scores([(row["ticker"], row["danta_score"]) for row in kr_preview_rows])
            kr_swing_rank = _rank_scores([(row["ticker"], row["swing_score"]) for row in kr_preview_rows])
            # 정렬: 1순위 후보(단타 또는 스윙)가 최우선, 그 다음 단기 관심점수 -> 며칠 관심점수 ->
            # 시총대비 거래대금 순으로 내림차순. 단타/스윙 둘 다 1순위 후보인 종목이 맨 위로 온다.
            kr_preview_rows_sorted = sorted(
                kr_preview_rows,
                key=lambda row: (
                    1 if (row["danta_verdict"] == "추천 후보" or row["swing_verdict"] == "추천 후보") else 0,
                    row["danta_score"],
                    row["swing_score"],
                    row["turnover_ratio_pct"] if row["turnover_ratio_pct"] is not None else float("-inf"),
                ),
                reverse=True,
            )
            kr_preview_open_pos_raw_list = [row["open_pos_pct"] for row in kr_preview_rows_sorted]
            kr_preview_high_drop_disp_raw_list = [
                (-row["high_drop_pct"] if row["high_drop_pct"] is not None else None)
                for row in kr_preview_rows_sorted
            ]

            def _preview_signed_pct_color_styler(raw_list):
                def _apply(col):
                    styles = []
                    for raw in raw_list:
                        if raw is None or raw == 0:
                            styles.append("")
                        elif raw > 0:
                            styles.append("color: #ff4b4b")
                        else:
                            styles.append("color: #4b9fff")
                    return styles
                return _apply

            kr_preview_df = pd.DataFrame(
                [
                    {
                        "종목명": row["name"],
                        "단타 판단": _display_verdict_name(row["danta_verdict"]),
                        "스윙 판단": _display_verdict_name(row["swing_verdict"]),
                        "단기 관심 점수": int(round(row["danta_score"])),
                        "며칠 관심 점수": int(round(row["swing_score"])),
                        "단타 순위": kr_danta_rank.get(row["ticker"], "미평가"),
                        "스윙 순위": kr_swing_rank.get(row["ticker"], "미평가"),
                        "현재가": f"{_get_snapshot_value(row['ticker'], 'current'):,.0f}",
                        "시가대비 등락률(%)": _fmt_signed_pct(row["open_pos_pct"]),
                        "고점 대비 밀림률(%)": _fmt_signed_pct(
                            -row["high_drop_pct"] if row["high_drop_pct"] is not None else None
                        ),
                        "거래대금": f"{row['turnover']:,.0f}원" if row["turnover"] else "-",
                        "시총 대비 거래대금(%)": _fmt_pct(row["turnover_ratio_pct"]),
                    }
                    for row in kr_preview_rows_sorted
                ]
            )
            kr_preview_styled_df = (
                kr_preview_df.style
                .apply(_preview_signed_pct_color_styler(kr_preview_open_pos_raw_list), subset=["시가대비 등락률(%)"])
                .apply(_preview_signed_pct_color_styler(kr_preview_high_drop_disp_raw_list), subset=["고점 대비 밀림률(%)"])
                .set_properties(
                    subset=[
                        "단기 관심 점수", "며칠 관심 점수", "현재가",
                        "시가대비 등락률(%)", "고점 대비 밀림률(%)", "거래대금", "시총 대비 거래대금(%)",
                    ],
                    **{"text-align": "right"},
                )
            )
            st.dataframe(kr_preview_styled_df, width="stretch", hide_index=True)

            st.caption(
                "점수는 자동매수 신호가 아닙니다. 직접 입력한 score가 없으므로 이 화면의 모든 점수는 "
                "'자동계산'입니다(직접 score를 입력할 수 있는 화면이 아닙니다)."
            )
            st.markdown("종목별 자동계산 근거 (단타/스윙 각각)")
            for row in kr_preview_rows:
                danta_label = kr_danta_rank.get(row["ticker"], "미평가")
                with st.expander(
                    f"[단타 {danta_label}] {row['name']} / {row['danta_score']:.0f}점 (자동계산)"
                ):
                    st.markdown(
                        f"**[단타 {danta_label}] {row['name']} / {row['danta_score']:.0f}점 (자동계산)**"
                    )
                    st.write(f"점수 근거: {row['danta_score_reason']}")
                    st.write(f"1순위 후보 근거: {row['danta_top_candidate_reason']}")
                    st.write(f"감점 이유: {row['danta_penalty_reason']}")
                    st.write("매수 확정 여부: 미확정")
                    st.write(f"매수 확정 조건: {row['danta_buy_confirm_condition']}")
                swing_label = kr_swing_rank.get(row["ticker"], "미평가")
                with st.expander(
                    f"[스윙 {swing_label}] {row['name']} / {row['swing_score']:.0f}점 (자동계산)"
                ):
                    st.markdown(
                        f"**[스윙 {swing_label}] {row['name']} / {row['swing_score']:.0f}점 (자동계산)**"
                    )
                    st.write(f"점수 근거: {row['swing_score_reason']}")
                    st.write(f"1순위 후보 근거: {row['swing_top_candidate_reason']}")
                    st.write(f"감점 이유: {row['swing_penalty_reason']}")
                    st.write("매수 확정 여부: 미확정")
                    st.write(f"매수 확정 조건: {row['swing_buy_confirm_condition']}")

            kcol1, kcol2 = st.columns(2)
            if kcol1.button("이 내용으로 최종 저장", type="primary", key="kr_quick_confirm_save"):
                items_to_save = []
                judged_at = datetime.now().isoformat(timespec="seconds")
                for row in kr_preview_rows:
                    basis_a = (
                        f"전일대비 {_fmt_signed_pct(row['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(row['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(row['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(row['turnover_ratio_pct'])}"
                    )
                    danta_verdict_display = _display_verdict_name(row["danta_verdict"])
                    swing_verdict_display = _display_verdict_name(row["swing_verdict"])
                    # 미리보기 단계에서 이미 계산한 근거를 그대로 재사용한다(미리보기와 저장 결과가
                    # 서로 다르게 보이지 않도록).
                    items_to_save.append(
                        {
                            "event_title": (
                                f"{row['name']} 단기 관심 점수 {row['danta_score']}점 - "
                                f"단타 {danta_verdict_display}"
                            ),
                            "ticker": row["ticker"],
                            "stock_name": row["name"],
                            "market": "KR",
                            "stock_market_basis_a": basis_a,
                            "stock_market_judgment": (
                                f"단기 관심 점수 {row['danta_score']}점 -> 단타 {danta_verdict_display}"
                            ),
                            "verdict": row["danta_verdict"],
                            "signal_type": "재확인 신호",
                            "trade_mode": "단타",
                            "score": row["danta_score"],
                            "score_reason": row["danta_score_reason"],
                            "top_candidate_reason": row["danta_top_candidate_reason"],
                            "penalty_reason": row["danta_penalty_reason"],
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": row["danta_buy_confirm_condition"],
                            "judged_at": judged_at,
                            **row["risk_fields"],
                        }
                    )
                    items_to_save.append(
                        {
                            "event_title": (
                                f"{row['name']} 며칠 관심 점수 {row['swing_score']}점 - "
                                f"스윙 {swing_verdict_display}"
                            ),
                            "ticker": row["ticker"],
                            "stock_name": row["name"],
                            "market": "KR",
                            "stock_market_basis_a": basis_a,
                            "stock_market_judgment": (
                                f"며칠 관심 점수 {row['swing_score']}점 -> 스윙 {swing_verdict_display}"
                            ),
                            "verdict": row["swing_verdict"],
                            "signal_type": "재확인 신호",
                            "trade_mode": "스윙",
                            "score": row["swing_score"],
                            "score_reason": row["swing_score_reason"],
                            "top_candidate_reason": row["swing_top_candidate_reason"],
                            "penalty_reason": row["swing_penalty_reason"],
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": row["swing_buy_confirm_condition"],
                            "judged_at": judged_at,
                            **row["risk_fields"],
                        }
                    )
                kr_report_id = db.save_report(
                    market_scope="KR",
                    day_conclusion=st.session_state["kr_quick_day_conclusion"],
                    raw_briefing=st.session_state["kr_quick_basis_text"],
                    items=items_to_save,
                    briefing_stage="오늘 주가 확인 기반 국내장 판단",
                )
                st.session_state.pop("kr_quick_preview_rows", None)
                st.session_state.pop("kr_quick_day_conclusion", None)
                st.session_state.pop("kr_quick_basis_text", None)
                st.session_state.pop("kr_show_save_preview", None)
                st.success(
                    "국내장 기록 저장 완료. 오늘 저장 요약, 지난 기록 보기, 저장 결과 확인에서 확인할 수 있습니다. "
                    f"(report_id={kr_report_id})"
                )
            if kcol2.button("취소", key="kr_quick_cancel_preview"):
                st.session_state.pop("kr_quick_preview_rows", None)
                st.session_state.pop("kr_quick_day_conclusion", None)
                st.session_state.pop("kr_quick_basis_text", None)
                st.session_state.pop("kr_show_save_preview", None)
                st.rerun()

with tab_kr:
    _render_tab_kr()


US_AUTO_RUN_VERSION = "2026-07-15-v1"

@st.fragment
def _render_tab_us():
    # 프래그먼트 rerun에서는 모듈 상단의 US_SNAPSHOT_STOCKS 재계산이 실행되지 않는다
    # — KR 탭과 같은 이유로 매 프래그먼트 실행마다 세션 기준으로 전역을 다시 맞춘다.
    _dyn_us = st.session_state.get("dynamic_us_snapshot_stocks")
    if _dyn_us and len(_dyn_us) < 5:
        st.session_state.pop("dynamic_us_snapshot_stocks", None)
        st.session_state["us_auto_run_stage1_done"] = False
    globals()["US_SNAPSHOT_STOCKS"] = st.session_state.get("dynamic_us_snapshot_stocks") or DEFAULT_US_SNAPSHOT_STOCKS
    # 2026-07-15 사용자 요청: 미국장 탭도 한국장 탭과 동일하게 로그인(탭 진입) 후
    # "종목 자동 선정" → "시장자료/섹터ETF/테마지표/종목 스냅샷 불러오기"를 세션당 한 번
    # 자동으로 순서대로 실행한다. 한국장(stage1=종목선정 → stage2=상세조회)과 동일한
    # 2단계 구조 — stage1에서 US_CANDIDATE_UNIVERSE 안에서 거래대금 상위 8종목을 뽑아
    # dynamic_us_snapshot_stocks에 저장하고 rerun해야, 모듈 상단의 US_SNAPSHOT_STOCKS가
    # 그 새 목록을 반영한 채로 stage2가 실행된다. 기존 버튼들은 그대로 남겨두고, 같은
    # session_state 키에 결과를 채워 넣어 버튼을 다시 눌러도 정상 동작하게 한다.
    if st.session_state.get("us_auto_run_version") != US_AUTO_RUN_VERSION:
        st.session_state["us_auto_run_stage1_done"] = False
        st.session_state["us_auto_run_stage2_done"] = False
        st.session_state["us_auto_run_version"] = US_AUTO_RUN_VERSION
    if not st.session_state.get("us_auto_run_stage1_done"):
        _us_auto_run_stocks = _cached_get_top_us_stocks_by_amount(8)
        if _us_auto_run_stocks and len(_us_auto_run_stocks) >= 5:
            st.session_state["dynamic_us_snapshot_stocks"] = _us_auto_run_stocks
            st.session_state["dynamic_us_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # KR stage1과 같은 이유 — 로그인 전환 실행에서 stage2가 같은 실행에서
            # 이어지므로 전역을 즉시 갱신한다.
            globals()["US_SNAPSHOT_STOCKS"] = _us_auto_run_stocks
        st.session_state["us_auto_run_stage1_done"] = True
        if not _login_transition_pending:
            st.rerun()
    if not st.session_state.get("us_auto_run_stage2_done"):
        st.session_state["us_market_overview_result"] = _cached_fetch_market_overview("US")
        st.session_state["us_market_overview_checked_at"] = st.session_state["us_market_overview_result"]["checked_at"]

        st.session_state["us_sector_auto_fetch_result"] = _cached_fetch_us_sector_snapshot()
        st.session_state["us_theme_indicators_result"] = _cached_fetch_us_theme_indicators()

        _us_auto_tickers = [s["ticker"] for s in US_SNAPSHOT_STOCKS]
        _us_auto_fetch_results = _cached_kr_snapshot_results(_us_auto_tickers)
        for _us_ticker, _us_result in _us_auto_fetch_results.items():
            if _us_result.get("ok"):
                _us_prefix = f"snap_{_us_ticker}_"
                st.session_state[_us_prefix + "current"] = _us_result["current"]
                st.session_state[_us_prefix + "prev_close"] = _us_result["prev_close"]
                st.session_state[_us_prefix + "open"] = _us_result["open"]
                st.session_state[_us_prefix + "high"] = _us_result["high"]
                st.session_state[_us_prefix + "low"] = _us_result["low"]
                st.session_state[_us_prefix + "turnover"] = _us_result["turnover"]
                st.session_state[_us_prefix + "market_cap"] = _us_result["market_cap"] or 0.0
        st.session_state["us_stock_auto_fill_results"] = _us_auto_fetch_results

        st.session_state["us_bookmaker_auto_fetch_pending"] = True
        st.session_state["us_auto_run_stage2_done"] = True
        # KR 자동실행 단계와 동일하게, 로그인 직후 전환 연출이 떠 있는 실행에서는
        # 즉시 rerun하지 않고 그 실행 안에서 계속 이어간다. KR 쪽 테마 자동조회가
        # 이미 자체 rerun으로 전환 오버레이를 다시 세워 보여주므로(위 kr_theme_auto_fetch_pending
        # 처리부), 여기서는 다시 세우지 않는다 — 다시 세우면 이 실행이 마지막 패스가 될 때
        # login_transition_pending이 아무도 소비하지 않은 채 세션에 남는다.
        if not _login_transition_pending:
            st.rerun()

    _render_market_overview("US")
    st.subheader("미국장")
    st.caption(
        "스윙 전용 흐름 — 유동성 높은 대형주 약 35종목 후보군 중 오늘 거래대금 상위 8종목을 "
        "자동 선정합니다(현재: " + ", ".join(s["name"] for s in US_SNAPSHOT_STOCKS) + "). "
        "한국 종목은 다루지 않으며, "
        "시장 분위기는 한국장 탭 입력값을 그대로 사용합니다. 입력값은 저장되지 않으며, "
        "③ 스윙 기록 바로 저장을 눌렀을 때만 저장되어 오늘 저장 요약/지난 기록에 반영됩니다."
    )

    # 미국장 시장 분위기 요약 — 한국장 탭의 수동 입력값이 있으면 그것을, 없으면
    # 0단계 자동 확인 결과(kr_mood_auto_results)로 채운다. 예전에는 수동 입력값만
    # 읽어서 자동조회가 끝나도 "0.00% / 미입력"으로만 보였다(2026-07-15 사용자 지적).
    st.markdown("### 0단계 미국장 시장 분위기 확인")
    _kr_mood_rows = {row["항목"]: row for row in (st.session_state.get("kr_mood_auto_results") or [])}

    def _us_mood_direction_from_auto(name):
        _pct_text = str((_kr_mood_rows.get(name) or {}).get("등락률(%)") or "")
        if _pct_text.startswith("+"):
            return "상승"
        if _pct_text.startswith("-"):
            return "하락"
        return "미입력"

    _us_nq_change = st.session_state.get("snap_nq_change", 0.0)
    if not _us_nq_change:
        try:
            _us_nq_change = float(
                str((_kr_mood_rows.get("나스닥100 선물") or {}).get("등락률(%)") or "0").replace("%", "").replace("+", "")
            )
        except (TypeError, ValueError):
            _us_nq_change = 0.0
    _us_soxx_dir = st.session_state.get("snap_soxx_dir", "미입력")
    if _us_soxx_dir == "미입력":
        _us_soxx_dir = _us_mood_direction_from_auto("SOXX")
        if _us_soxx_dir != "미입력":
            _us_soxx_dir += " (자동 조회)"
    _us_usdkrw_dir = st.session_state.get("snap_usdkrw_dir", "미입력")
    if _us_usdkrw_dir == "미입력":
        _us_usdkrw_dir = _us_mood_direction_from_auto("달러/원")
        if _us_usdkrw_dir != "미입력":
            _us_usdkrw_dir += " (자동 조회)"
    st.markdown(
        f"""
        <div style="background-color:#171a21;border:1px solid #303642;border-radius:10px;padding:14px;margin-top:8px;">
        <b>미국장 시장 분위기 입력값 확인</b><br>
        - 나스닥100 선물: {_us_nq_change:+.2f}%<br>
        - SOXX/SMH 방향: {_us_soxx_dir}<br>
        - 달러/원 방향: {_us_usdkrw_dir}<br>
        - 미국장 판단 기준: 실시간 단타 아님, 스윙 후보 확인용
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("미국장은 한국시간 밤에 실시간 단타로 보지 않고, 전일 종가와 스윙 후보를 확인하는 용도입니다.")

    # 2026-07-15 사용자 요청: 한국장의 "오늘 종목 판단 준비하기"처럼, 미국장도 시장자료·
    # 섹터ETF·테마지표·8종목 스냅샷을 한 번에 다시 불러오는 버튼을 만든다(탭 진입 시
    # 이미 자동으로 한 번 실행되며, 이 버튼은 그 결과를 강제로 새로고침할 때 쓴다).
    if st.button("오늘 미국 종목 판단 준비하기", key="us_auto_preview_run", type="primary"):
        with st.spinner("미국장 자료 새로고침 중..."):
            _us_reselected = _short_cached_top_us_stocks_by_amount(8)
            if _us_reselected and len(_us_reselected) >= 5:
                st.session_state["dynamic_us_snapshot_stocks"] = _us_reselected
                st.session_state["dynamic_us_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 이번 실행에서 바로 반영되도록 전역도 갱신(프래그먼트 rerun은 모듈
                # 상단 재계산을 건너뛴다).
                globals()["US_SNAPSHOT_STOCKS"] = _us_reselected
            else:
                _us_reselected = None
            st.session_state["us_market_overview_result"] = _short_cached_fetch_market_overview("US")
            st.session_state["us_market_overview_checked_at"] = st.session_state["us_market_overview_result"]["checked_at"]
            st.session_state["us_sector_auto_fetch_result"] = _short_cached_fetch_us_sector_snapshot()
            st.session_state["us_theme_indicators_result"] = _short_cached_fetch_us_theme_indicators()
            _us_refresh_stocks = _us_reselected or US_SNAPSHOT_STOCKS
            _us_refresh_tickers = [s["ticker"] for s in _us_refresh_stocks]
            _us_refresh_results = _short_cached_kr_snapshot_results(_us_refresh_tickers)
            for _us_ticker, _us_result in _us_refresh_results.items():
                if _us_result.get("ok"):
                    _us_prefix = f"snap_{_us_ticker}_"
                    st.session_state[_us_prefix + "current"] = _us_result["current"]
                    st.session_state[_us_prefix + "prev_close"] = _us_result["prev_close"]
                    st.session_state[_us_prefix + "open"] = _us_result["open"]
                    st.session_state[_us_prefix + "high"] = _us_result["high"]
                    st.session_state[_us_prefix + "low"] = _us_result["low"]
                    st.session_state[_us_prefix + "turnover"] = _us_result["turnover"]
                    st.session_state[_us_prefix + "market_cap"] = _us_result["market_cap"] or 0.0
            st.session_state["us_stock_auto_fill_results"] = _us_refresh_results
        st.session_state["us_auto_preview_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if st.session_state.get("us_auto_preview_done_at"):
        st.caption(f"판단 준비 완료: {st.session_state['us_auto_preview_done_at']}")

    # 2026-07-15 사용자 반복 요청: 한국장 목업1과 동일한 "종목 판단 미리보기"(종목 선택·
    # 점수 카드·핵심 근거·리스크 관리)를 미국장에도 그린다.
    _render_us_stock_judgment_preview()

    # 한국장의 "2단계 판단 미리보기"와 동일한 형태의 요약 표. 점수 엔진은 새로 만들지
    # 않고 기존 compute_us_swing_breakdown()을 build_us_stage2_preview()로 재사용한다.
    st.markdown("#### 2단계 판단 미리보기 (저장 전, 자동 계산)")
    st.caption(
        "아직 저장하지 않은 상태의 참고용 미리보기입니다. 매수 신호가 아니며, 실제로 기록을 "
        "남기려면 아래 '③ 미국장 스윙 기록 바로 저장'을 따로 눌러야 합니다. 이 미리보기 자체는 "
        "DB에 아무 것도 저장하지 않습니다."
    )
    _us_stage2_preview = build_us_stage2_preview()
    if not _us_stage2_preview["rows"]:
        st.info("아직 입력된 종목이 없어 미국 종목 판단 미리보기를 만들 수 없습니다.")
    else:
        _us_stage2_rows_sorted = sorted(
            _us_stage2_preview["rows"], key=lambda r: r["total_score"], reverse=True,
        )

        def _us_stage2_verdict_styler(col):
            # KR 2단계 표와 같은 색 규칙: 추천(초록)·감시(노랑)·보류(파랑).
            styles = []
            for val in col:
                if val == "추천 후보":
                    styles.append("color: #39ff14; font-weight: 800")
                elif val == "감시":
                    styles.append("color: #facc15")
                elif val == "보류(선반영)":
                    styles.append("color: #4b9fff")
                else:
                    styles.append("")
            return styles

        def _us_stage2_confirm_styler(col):
            return [
                "color: #f97316; font-weight: 800" if val == "예" else ""
                for val in col
            ]

        _us_stage2_df = pd.DataFrame(
            [
                {
                    "종목명": r["name"],
                    "총점": int(round(r["total_score"])),
                    "판단": r["verdict"],
                    "확인 필요": "예" if r["needs_confirmation"] else "-",
                }
                for r in _us_stage2_rows_sorted
            ]
        )
        _us_stage2_styled_df = (
            _us_stage2_df.style
            .apply(_us_stage2_verdict_styler, subset=["판단"])
            .apply(_us_stage2_confirm_styler, subset=["확인 필요"])
        )
        # 컬럼이 4개뿐이라 화면 전체로 늘리면 칸이 지나치게 넓어진다(2026-07-15 지적)
        # — 내용 폭에 맞춘다.
        st.dataframe(_us_stage2_styled_df, width="content", hide_index=True)
        st.markdown("종목별 1순위 근거 / 감점 이유 (미리보기)")
        for r in _us_stage2_rows_sorted:
            with st.expander(f"{r['name']} — {r['verdict']} (총점 {r['total_score']:.0f}점)"):
                st.write(f"1순위 근거: {r['priority_reason']}")
                st.write(f"감점 이유: {r['deduction_reason']}")
                if r["validation_errors"]:
                    st.warning("확인 필요: " + "; ".join(r["validation_errors"]))

    with st.expander("오늘 거래대금 상위 종목 다시 선정(미국)", expanded=False):
        st.caption(
            f"후보군 {len(US_CANDIDATE_UNIVERSE)}종목(유동성 높은 대형주) 중 오늘 거래대금 상위 "
            "종목을 자동으로 뽑아 아래 스윙 계산 대상 목록을 대체합니다. 저장되지 않으며 이 "
            f"세션에서만 유지됩니다(다시 접속하면 기본 {len(DEFAULT_US_SNAPSHOT_STOCKS)}종목으로 돌아갑니다)."
        )
        _dynamic_us_top_n = st.number_input(
            "몇 종목?", min_value=5, max_value=len(US_CANDIDATE_UNIVERSE), value=8, step=1,
            key="dynamic_us_snapshot_n",
        )
        if st.button("미국 거래대금 상위 종목 다시 불러오기", key="dynamic_us_snapshot_refresh"):
            _new_us_stocks = _short_cached_top_us_stocks_by_amount(int(_dynamic_us_top_n))
            if _new_us_stocks:
                st.session_state["dynamic_us_snapshot_stocks"] = _new_us_stocks
                st.session_state["dynamic_us_snapshot_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"{len(_new_us_stocks)}개 종목으로 갱신했습니다.")
                st.rerun()
            else:
                st.warning("거래대금 상위 종목을 찾지 못했습니다(네트워크 문제일 수 있습니다).")
        if st.session_state.get("dynamic_us_snapshot_updated_at"):
            st.caption(f"마지막 선정: {st.session_state['dynamic_us_snapshot_updated_at']}")

    # ---- 미국장 테마 참고판 (수기 참고용, 저장/점수/판단 미반영) ----
    # 2026-07-15 사용자 반복 요청: 한국장 테마 참고판(노란 버튼 + 표 + 세부 입력)과 같은
    # 형태로 재구성. 기존 접힌 expander("테마 레이더")를 없애고 항상 펼쳐 보여준다.
    st.markdown("#### 테마 참고판 (미국)")
    st.markdown(
        """
        <style>
        .st-key-us_theme_auto_fetch button {
            background: #facc15 !important;
            color: #1f2937 !important;
            border-color: #eab308 !important;
        }
        .st-key-us_theme_auto_fetch button p { color: #1f2937 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("테마 참고판 자동 조회", key="us_theme_auto_fetch"):
        st.session_state["us_sector_auto_fetch_result"] = _short_cached_fetch_us_sector_snapshot()
        st.session_state["us_theme_indicators_result"] = _short_cached_fetch_us_theme_indicators()
        st.rerun()
    if st.session_state.get("us_sector_auto_fetch_result", {}).get("checked_at"):
        st.caption(f"마지막 자동 조회: {st.session_state['us_sector_auto_fetch_result']['checked_at']}")
    st.caption("탭 진입 시 자동 조회 · 참고용 표시일 뿐이며 점수·판정·DB 저장에는 반영되지 않습니다.")

    _us_theme_watch_rows = [
        {
            "테마": theme,
            "현재 상태": "확인 필요",
            "참고 지표": indicators,
            "대장주": "",
            "후발주": "",
            "추격주의": "",
            "메모": "",
        }
        for theme, indicators in [
            ("AI/반도체", "SOXX, SMH, NVDA, AVGO, AMD"),
            ("금리/성장주", "QQQ, VIX, 미국 10년물, DXY"),
            ("전력망/원전", "XLU, GRID, URA"),
            ("방산/전쟁", "ITA, XAR, LMT, NOC"),
            ("에너지/유가", "WTI, XLE, XOP"),
            ("자동차/전기차", "TSLA, LIT"),
            ("바이오", "XBI, IBB"),
        ]
    ]
    # 섹터/지표 자동 조회 결과가 있으면 7개 테마 전부 등락률 기준으로 상태를 자동 채우고,
    # 대장주/후발주 칸도 그날 등락률 상위 지표 티커로 자동 채운다(2026-07-15 지적:
    # "대장주 후발주 내용이 없다" — 미국장은 네이버 테마 같은 종목명 소스가 없어
    # 참고 지표 티커 중 강한 순서로 채우는 참고용 표기다).
    _us_indicators_result = st.session_state.get("us_theme_indicators_result")
    if _us_indicators_result and _us_indicators_result["ok"]:
        _us_indicator_values = _us_indicators_result["values"]
        for _row in _us_theme_watch_rows:
            _tickers = theme_data.US_THEME_INDICATOR_MAPPING.get(_row["테마"])
            if not _tickers:
                continue
            _vals = [
                _us_indicator_values[t]
                for t in _tickers
                if _us_indicator_values.get(t) is not None
            ]
            if not _vals:
                continue
            _avg_change = sum(_vals) / len(_vals)
            if _avg_change >= 1.0:
                _row["현재 상태"] = "강함"
            elif _avg_change <= -1.0:
                _row["현재 상태"] = "약함"
            else:
                _row["현재 상태"] = "보통"
            _ranked_tickers = sorted(
                (t for t in _tickers if _us_indicator_values.get(t) is not None),
                key=lambda t: _us_indicator_values[t],
                reverse=True,
            )
            if _ranked_tickers and not _row["대장주"]:
                _row["대장주"] = f"{_ranked_tickers[0]} ({_us_indicator_values[_ranked_tickers[0]]:+.2f}%)"
            if len(_ranked_tickers) > 1 and not _row["후발주"]:
                _row["후발주"] = ", ".join(
                    f"{t} ({_us_indicator_values[t]:+.2f}%)" for t in _ranked_tickers[1:3]
                )
            if not _row["메모"]:
                _row["메모"] = f"자동조회 참고: {'/'.join(_tickers)} 평균 {_avg_change:+.2f}%"
    # 세부 입력(대장주/후발주/추격주의/메모/상태)은 테마별 session_state 키에 저장되어
    # rerun에도 유지되고, 표에도 다시 반영한다 — 한국장 테마 참고판과 같은 동작.
    def _us_theme_slug(theme_name):
        return "_".join(f"u{ord(c):04x}" for c in theme_name if c.isalnum())

    for _row in _us_theme_watch_rows:
        _slug = _us_theme_slug(_row["테마"])
        for _field, _key_prefix in (
            ("대장주", "us_theme_leader_"),
            ("후발주", "us_theme_laggard_"),
            ("추격주의", "us_theme_chase_warning_"),
            ("메모", "us_theme_memo_"),
        ):
            _saved = st.session_state.get(f"{_key_prefix}{_slug}")
            if _saved:
                _row[_field] = _saved
        _saved_status = st.session_state.get(f"us_theme_status_{_slug}")
        if _saved_status:
            _row["현재 상태"] = _saved_status

    def _us_theme_status_styler(col):
        # KR 테마 참고판과 같은 색 규칙: 강함(빨강)·감시(노랑)·보통(파랑)·약함(회색).
        styles = []
        for val in col:
            if val == "강함":
                styles.append("color: #ff4b4b; font-weight: 800")
            elif val == "감시":
                styles.append("color: #facc15; font-weight: 700")
            elif val == "보통":
                styles.append("color: #4b9fff")
            elif val == "약함":
                styles.append("color: #94a3b8")
            else:
                styles.append("color: #6b7280")
        return styles

    _us_theme_df = pd.DataFrame(_us_theme_watch_rows)
    st.dataframe(
        _us_theme_df.style.apply(_us_theme_status_styler, subset=["현재 상태"]),
        width="stretch",
        height=308,
        row_height=38,
        hide_index=True,
    )

    _us_theme_names = [row["테마"] for row in _us_theme_watch_rows]
    _us_theme_detail_selected = st.selectbox(
        "세부 입력할 테마 선택", _us_theme_names, key="us_theme_detail_selector"
    )
    _us_selected_slug = _us_theme_slug(_us_theme_detail_selected)
    _us_selected_row = next(r for r in _us_theme_watch_rows if r["테마"] == _us_theme_detail_selected)
    _us_status_options = ["강함", "감시", "보통", "약함", "확인 필요"]
    st.selectbox(
        "선택 테마 현재 상태",
        _us_status_options,
        index=_us_status_options.index(_us_selected_row["현재 상태"])
        if _us_selected_row["현재 상태"] in _us_status_options else 4,
        key=f"us_theme_status_{_us_selected_slug}",
    )
    with st.expander("선택 테마 세부 입력", expanded=True):
        st.text_input("대장주", key=f"us_theme_leader_{_us_selected_slug}")
        st.text_input("후발주", key=f"us_theme_laggard_{_us_selected_slug}")
        st.text_input("추격주의", key=f"us_theme_chase_warning_{_us_selected_slug}")
        st.text_input("메모", key=f"us_theme_memo_{_us_selected_slug}")
    st.caption("테마 참고판은 session_state에서만 유지되며 DB·점수·판정에는 반영되지 않습니다.")

    _us_today_loss_r = st.session_state.get("risk_today_loss_r", 0.0)
    if _us_today_loss_r <= -2:
        st.error("금일 신규 판단 중지 - 당일 손실 -2R 도달")

    # 1. 미국장 기본 종목 불러오기 (TSLA/AMD/AVGO/META/GOOGL/AAPL/NVDA/MSFT — 저장 없음)
    st.markdown("---")
    st.caption(
        "미국장 스윙 기록 바로 저장에 쓸 미국 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT) "
        "시세를 yfinance(우선)/FinanceDataReader(보조)로 불러옵니다. 조회 결과는 저장되지 않고 화면 계산에만 쓰입니다."
    )
    if st.button("① 미국장 기본 종목 불러오기", key="us_stock_auto_fill"):
        us_fetch_results = {}
        for s in US_SNAPSHOT_STOCKS:
            result = price_data.get_snapshot_defaults(s["ticker"])
            us_fetch_results[s["ticker"]] = result
            if result.get("ok"):
                prefix = f"snap_{s['ticker']}_"
                st.session_state[prefix + "current"] = result["current"]
                st.session_state[prefix + "prev_close"] = result["prev_close"]
                st.session_state[prefix + "open"] = result["open"]
                st.session_state[prefix + "high"] = result["high"]
                st.session_state[prefix + "low"] = result["low"]
                st.session_state[prefix + "turnover"] = result["turnover"]
                st.session_state[prefix + "market_cap"] = result["market_cap"] or 0.0
        st.session_state["us_stock_auto_fill_results"] = us_fetch_results
        st.rerun()

    if st.session_state.get("us_stock_auto_fill_results"):
        us_auto_fill_results = st.session_state["us_stock_auto_fill_results"]
        _render_auto_fetch_status_summary(us_auto_fill_results, US_SNAPSHOT_STOCKS, "us_")
    # 2. 미국장 스윙 기록 바로 저장 (새 기록 입력 화면을 거치지 않고 이 화면에서 바로 저장)
    # 한국 종목(SNAPSHOT_STOCKS)과는 별도로, 미국장 기본 종목(US_SNAPSHOT_STOCKS)만 대상으로 한다.
    us_snapshot_calc_data = []
    for s in US_SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)
        material_memo = (st.session_state.get(f"snap_{ticker}_material_memo", "") or "").strip()

        breakdown = compute_us_swing_breakdown(
            s["name"], change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, material_memo
        )
        breakdown["ticker"] = ticker
        breakdown["change_pct"] = change_pct
        breakdown["open_pos_pct"] = open_pos_pct
        breakdown["high_drop_pct"] = high_drop_pct
        breakdown["turnover_ratio_pct"] = turnover_ratio_pct
        breakdown["turnover"] = turnover
        breakdown["risk_fields"] = _collect_risk_fields(ticker)
        breakdown["validation_errors"] = _validate_snapshot_price_inputs(
            s["name"], current, open_price, high, low, _get_snapshot_value(ticker, "volume"), turnover,
        )
        us_snapshot_calc_data.append(breakdown)

    st.markdown("---")
    st.markdown("### ② 미국장 스윙 계산 결과")
    st.caption(
        "정렬 기준: 총점 높은 순 → 거래/탄력 점수 높은 순 → 위험 감점 작은 순입니다. "
        "점수는 매수 신호가 아니라 관심 후보 정렬 기준입니다."
    )
    if not us_snapshot_calc_data:
        st.info("아직 불러온 종목 데이터가 없습니다. 위 '① 미국장 기본 종목 불러오기'를 먼저 눌러주세요.")
    else:
        _us_calc_rank = _rank_scores([(r["ticker"], r["total_score"]) for r in us_snapshot_calc_data])
        # 정렬: 스윙 판단이 1순위 후보인 종목이 최우선, 그 다음 총점 -> 거래/탄력 점수 ->
        # 위험 감점(작은 순=0에 가까운 순) 내림차순.
        _us_calc_sorted = sorted(
            us_snapshot_calc_data,
            key=lambda r: (
                1 if r["verdict"] == "추천 후보" else 0,
                r["total_score"], r["momentum_score"], r["risk_score"],
            ),
            reverse=True,
        )
        def _us_rank_styler(col):
            styles = []
            for val in col:
                if val == "1순위 후보":
                    styles.append("color: #39ff14; font-weight: 800")
                elif val == "2순위":
                    styles.append("color: #facc15")
                elif val == "3순위":
                    styles.append("color: #4b9fff")
                else:
                    styles.append("")
            return styles

        _us_calc_df = pd.DataFrame(
            [
                {
                    "종목명": r["name"],
                    "티커": r["ticker"],
                    "스윙 순위": _us_calc_rank.get(r["ticker"], "미평가"),
                    "총점": r["total_score"],
                    "판단": r["tier_label"],
                    "현재가": (
                        "-"
                        if _get_snapshot_value(r["ticker"], "current") is None
                        else f"{_get_snapshot_value(r['ticker'], 'current'):,.2f}"
                    ),
                    "전일대비(%)": "-" if r["change_pct"] is None else _fmt_signed_pct(r["change_pct"]),
                    "시가대비(오늘)": "-" if r["open_pos_pct"] is None else _fmt_signed_pct(r["open_pos_pct"]),
                    "고점대비(오늘)": "-" if r["high_drop_pct"] is None else _fmt_signed_pct(r["high_drop_pct"]),
                    "시총 대비 거래대금(%)": (
                        "-" if r["turnover_ratio_pct"] is None else f"{r['turnover_ratio_pct']:.2f}"
                    ),
                    "거래/탄력 점수": r["momentum_score"],
                    "위험 감점": r["risk_score"],
                    "1순위 근거": r["priority_reason"],
                }
                for r in _us_calc_sorted
            ]
        )
        _us_calc_styled_df = _us_calc_df.style.apply(_us_rank_styler, subset=["스윙 순위"])
        st.dataframe(
            _us_calc_styled_df,
            width="stretch",
            hide_index=True,
        )

    with st.expander("참고자료 · 뉴스", expanded=False):
        st.caption("종목 판단을 보조하는 참고자료입니다. 펼친 뒤 버튼을 눌렀을 때만 조회합니다.")
        _render_market_naver_news_panel(
            "US",
            US_SNAPSHOT_STOCKS,
            "📰 미국장 최근 뉴스 자동 확인",
            "us_naver_news_check_button",
            "us_naver_news_results",
            "us_naver_news_checked_at",
        )

    with st.expander("리스크 관리 설정(v1.1) — 필요할 때 펼치기", expanded=False):
        _us_risk_account_size = st.session_state.get("risk_account_size", 0.0)
        _us_risk_percent = st.session_state.get("risk_percent_setting", 1.0)
        st.caption(
            f"한국장 탭에서 입력한 값입니다: 계좌금액 {_us_risk_account_size:,.0f} / "
            f"1회 리스크 {_us_risk_percent:.1f}%"
        )

    st.markdown("---")
    st.markdown("### ③ 미국장 스윙 기록 바로 저장")
    st.caption(
        "미국장 기본 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT)만 대상으로 전부 "
        "시장 US / 스윙으로 저장합니다 (단타는 만들지 않습니다). 버튼을 누르면 바로 저장하지 않고 "
        "먼저 저장 전 확인 미리보기(점수 근거표 포함)를 보여줍니다."
    )
    if not us_snapshot_calc_data:
        st.info("미국장 스윙 기록을 저장하려면 먼저 미국장 종목 데이터를 불러와야 합니다.")
    if st.button("③ 미국장 스윙 기록 바로 저장", key="us_swing_quick_save", disabled=not us_snapshot_calc_data):
      st.session_state["us_show_save_preview"] = True
      st.session_state.pop("us_swing_preview_rows", None)
      st.session_state.pop("us_swing_day_conclusion", None)
      st.session_state.pop("us_swing_basis_text", None)
      st.session_state.pop("us_swing_raw_briefing", None)
      all_us_validation_errors = [e for calc in us_snapshot_calc_data for e in calc["validation_errors"]]
      if all_us_validation_errors:
        st.error("입력값 오류로 저장할 수 없습니다:\n" + "\n".join(f"- {e}" for e in all_us_validation_errors))
      else:
        preview_rows = sorted(
            us_snapshot_calc_data,
            key=lambda r: (r["total_score"], r["momentum_score"]),
            reverse=True,
        )
        counts = {"추천 후보": 0, "감시": 0, "보류(선반영)": 0}
        for row in preview_rows:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        day_conclusion_text = (
            f"미국장 마감 후 스윙 판단 자동 기록: 총 {len(preview_rows)}종목 "
            f"({_display_verdict_name('추천 후보')} {counts['추천 후보']}개, "
            f"{_display_verdict_name('감시')} {counts['감시']}개, "
            f"{_display_verdict_name('보류(선반영)')} {counts['보류(선반영)']}개). "
            "점수는 자동매수 신호가 아니라 종목별 점수 근거표를 바탕으로 한 참고용 판단입니다."
        )
        basis_text = "\n".join(
            f"{row['name']}: 총점 {row['total_score']:.0f}점 -> {row['tier_label']} "
            f"(저장 판정: {_display_verdict_name(row['verdict'])})"
            for row in preview_rows
        )
        st.session_state["us_swing_preview_rows"] = preview_rows
        st.session_state["us_swing_day_conclusion"] = day_conclusion_text
        st.session_state["us_swing_basis_text"] = basis_text
        st.session_state["us_swing_raw_briefing"] = "\n\n".join(
            _us_swing_narrative_text(row) for row in preview_rows
        )

    if st.session_state.get("us_show_save_preview") and st.session_state.get("us_swing_preview_rows"):
        preview_rows = st.session_state["us_swing_preview_rows"]
        st.markdown("#### 저장 전 확인 미리보기")
        st.write("시장: US")
        st.write("장 구분: 장마감")
        st.write("판단 시점: 미국장 마감 후 스윙 판단")
        st.write(f"오늘 요약: {st.session_state['us_swing_day_conclusion']}")
        st.write("판단 근거:")
        st.code(st.session_state["us_swing_basis_text"])
        with st.expander("실제 저장될 미국장 상세 브리핑", expanded=False):
            st.code(st.session_state.get("us_swing_raw_briefing") or "미리보기를 다시 생성하세요.")
        for _risk_row in preview_rows:
            _render_risk_plan_preview(
                _risk_row["name"], _risk_row["ticker"], _risk_row.get("risk_fields")
            )

        st.markdown("저장될 종목 목록 (자동계산 미리보기)")
        us_swing_rank = _rank_scores([(row["ticker"], row["total_score"]) for row in preview_rows])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "종목명": row["name"],
                        "티커": row["ticker"],
                        "시장": "US",
                        "매매유형": "스윙",
                        "총점": row["total_score"],
                        "스윙 순위": us_swing_rank.get(row["ticker"], "미평가"),
                        "판단": row["tier_label"],
                        "상승률 점수": row["upside_score"],
                        "종가 위치 점수": row["close_pos_score"],
                        "시장 분위기 점수": row["mood_score"],
                        "재료 점수": row["material_score"],
                        "거래/탄력 점수": row["momentum_score"],
                        "위험 감점": row["risk_score"],
                        "1순위 근거": row["priority_reason"],
                        "감점 이유": row["deduction_reason"],
                        "매수 확정 여부": row["buy_confirmed"],
                        "매수 확정 조건": row["buy_confirm_condition"],
                        "시가 대비 등락률(%)": _fmt_pct(row["open_pos_pct"]),
                        "고점 대비 밀림률(%)": _fmt_pct(
                            -row["high_drop_pct"] if row["high_drop_pct"] is not None else None
                        ),
                        "거래대금": f"{row['turnover']:,.0f}" if row["turnover"] else "-",
                        "시총 대비 거래대금(%)": _fmt_pct(row["turnover_ratio_pct"]),
                    }
                    for row in preview_rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "점수는 자동매수 신호가 아닙니다. 직접 입력한 score가 없으므로 이 화면의 모든 점수는 "
            "'자동계산'입니다(직접 score를 입력할 수 있는 화면이 아닙니다)."
        )

        st.markdown("종목별 점수 근거 문장")
        for row in preview_rows:
            rank_label = us_swing_rank.get(row["ticker"], "미평가")
            with st.expander(f"[스윙 {rank_label}] {row['name']} / {row['total_score']:.0f}점 (자동계산)"):
                st.markdown(f"**[스윙 {rank_label}] {row['name']} / {row['total_score']:.0f}점 (자동계산)**")
                st.text(_us_swing_narrative_text(row))

        pcol1, pcol2 = st.columns(2)
        if pcol1.button("이 내용으로 미국장 최종 저장", type="primary", key="us_final_save"):
            us_judged_at = datetime.now().isoformat(timespec="seconds")
            items_to_save = [
                {
                    "event_title": f"{row['name']} 총점 {row['total_score']:.0f}점 - {row['tier_label']}",
                    "ticker": row["ticker"],
                    "stock_name": row["name"],
                    "market": "US",
                    "stock_market_basis_a": (
                        f"전일대비 {_fmt_signed_pct(row['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(row['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(row['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(row['turnover_ratio_pct'])}"
                    ),
                    "stock_market_basis_b": (
                        f"상승률 {row['upside_score']:.0f}/20, 종가 위치 {row['close_pos_score']:.0f}/20, "
                        f"시장 분위기 {row['mood_score']:.0f}/15, 재료 {row['material_score']:.0f}/20, "
                        f"거래/탄력 {row['momentum_score']:.0f}/15, 위험 감점 {row['risk_score']:.0f}, "
                        f"총점 {row['total_score']:.0f}/100"
                    ),
                    "stock_market_judgment": _us_swing_narrative_text(row),
                    "verdict": row["verdict"],
                    "signal_type": "재확인 신호",
                    "trade_mode": "스윙",
                    "score": row["total_score"],
                    "score_reason": f"{row['upside_note']} + {row['close_pos_note']} + {row['momentum_note']}",
                    "top_candidate_reason": row["priority_reason"],
                    "penalty_reason": row["deduction_reason"],
                    "buy_confirmed": "미확정",
                    "buy_confirm_condition": row["buy_confirm_condition"],
                    "judged_at": us_judged_at,
                    **row["risk_fields"],
                }
                for row in preview_rows
            ]
            us_raw_briefing = st.session_state.get("us_swing_raw_briefing")
            if not us_raw_briefing:
                st.warning("미리보기를 다시 생성하세요.")
                st.stop()
            us_report_id = db.save_report(
                market_scope="US",
                day_conclusion=st.session_state["us_swing_day_conclusion"],
                raw_briefing=us_raw_briefing,
                items=items_to_save,
                briefing_stage="미국장 마감 후 스윙 판단",
                timing_class="장마감",
            )
            st.session_state.pop("us_swing_preview_rows", None)
            st.session_state.pop("us_swing_day_conclusion", None)
            st.session_state.pop("us_swing_basis_text", None)
            st.session_state.pop("us_swing_raw_briefing", None)
            st.session_state.pop("us_show_save_preview", None)
            st.success(f"미국장 스윙 기록 저장 완료 (report_id={us_report_id})")
        if pcol2.button("취소", key="us_cancel_save_preview"):
            st.session_state.pop("us_swing_preview_rows", None)
            st.session_state.pop("us_swing_day_conclusion", None)
            st.session_state.pop("us_swing_basis_text", None)
            st.session_state.pop("us_swing_raw_briefing", None)
            st.session_state.pop("us_show_save_preview", None)
            st.rerun()

    # 3. 종목별 상세 입력 카드 (기본 접힘)
    st.markdown("---")
    st.markdown("### 종목별 상세 입력")
    st.caption("카드를 펼치면 직접 숫자를 입력/수정할 수 있습니다. 0은 '입력 안 함'으로 취급합니다.")

    _us_detail_options = ["선택 안 함"] + [s["name"] for s in US_SNAPSHOT_STOCKS]
    _us_detail_selected = st.selectbox(
        "상세 입력할 종목 선택",
        _us_detail_options,
        key="us_snapshot_detail_selector",
    )

    for s in US_SNAPSHOT_STOCKS:
        if _us_detail_selected != s["name"]:
            continue
        prefix = f"snap_{s['ticker']}_"
        with st.expander(f"{s['name']} / {s['sector']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.number_input("현재가", value=0.0, step=1.0, key=prefix + "current")
            c2.number_input("전일종가", value=0.0, step=1.0, key=prefix + "prev_close")
            c3.number_input("시가", value=0.0, step=1.0, key=prefix + "open")
            c4.number_input("장중고가", value=0.0, step=1.0, key=prefix + "high")

            c5, c6, c7, c8 = st.columns(4)
            c5.number_input("장중저가", value=0.0, step=1.0, key=prefix + "low")
            c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
            c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")
            c8.number_input("거래량", value=0.0, step=1000.0, key=prefix + "volume")
            _render_snapshot_calc_summary(s["ticker"])
            st.text_input(
                "재료 메모 (선택, 없으면 재료 점수는 낮은 기본값으로 처리됩니다)",
                key=prefix + "material_memo",
                placeholder="예: 로보택시 기대감, AI 실적 발표, 신제품 발표 등",
            )
            st.markdown("---")
            # 리스크 관리(진입가/손절가 등) 위젯은 위 "종목 판단 미리보기"의 선택 종목
            # 패널에서 같은 세션 키(snap_{ticker}_entry_price 등)로 생성된다 — 같은
            # 종목을 두 곳에서 동시에 만들면 DuplicateWidgetID로 화면 전체가 죽어서
            # (2026-07-15 확인) 이 카드에서는 안내만 남긴다. 한국장 상세 카드와 동일한 구조.
            st.caption("진입가·손절가 등 리스크 관리 입력은 위 '종목 판단 미리보기'에서 해당 종목을 선택해 진행하세요.")

with tab_us:
    _render_tab_us()


def _render_judgment_outcome_save_button(selected_report_id, perf_rows_all, key_prefix=""):
    _item_lookup = _build_item_judgment_lookup()
    _eval_by_item_id = {}
    for _row in perf_rows_all:
        if _row["report_id"] != selected_report_id:
            continue
        _item = _item_lookup.get(
            (_row["report_id"], _row["ticker"], _row["trade_mode"]), {}
        )
        if _item.get("id"):
            _eval_by_item_id[_item["id"]] = _row

    _candidate_rows = []
    for _item_id, _eval_result in _eval_by_item_id.items():
        _candidate_rows.extend(
            performance.build_judgment_outcome_rows(_item_id, _eval_result)
        )

    st.caption(
        f"저장 가능: 종목 {len(_eval_by_item_id)}개 / "
        f"성과 {len(_candidate_rows)}건"
    )

    if st.button("판단 성과 저장", key=f"{key_prefix}judgment_outcome_save_button"):
        if not _candidate_rows:
            st.info("저장 가능한 완료 성과가 없습니다.")
        else:
            try:
                _saved_count = db.upsert_report_item_outcomes(_candidate_rows)
            except Exception as _save_err:
                st.error(f"판단 성과 저장 중 오류가 발생했습니다: {_save_err}")
            else:
                st.success(f"판단 성과 {_saved_count}건을 저장·갱신했습니다.")
                _after_save = db.get_report_outcomes(selected_report_id)
                _judgment_after_save = [
                    o for o in _after_save if o["entry_basis"] == "judgment"
                ]
                _horizons = sorted(
                    {o["horizon_sessions"] for o in _judgment_after_save}
                )
                _horizons_display = (
                    "·".join(f"{h}거래일" for h in _horizons)
                    if _horizons else "-"
                )
                st.caption(
                    f"저장 상태: judgment {len(_judgment_after_save)}건 / "
                    f"{_horizons_display}"
                )


def _render_actual_outcome_save_section(selected_report_id, key_prefix="") -> None:
    _actual_save_all_items = db.get_report_items(selected_report_id)
    _actual_save_target_items = [
        _ai
        for _ai in _actual_save_all_items
        if _ai.get("actual_action") == "매수"
        and _ai.get("actual_entry_price") is not None
        and _ai.get("actual_entry_date") is not None
    ]

    st.caption(f"실매매 기록 완료: {len(_actual_save_target_items)}종목")

    if st.button("실매매 성과 저장", key=f"{key_prefix}actual_outcome_save_button"):
        if not _actual_save_target_items:
            st.info("저장 가능한 완료 실매매 성과가 없습니다.")
        else:
            # 종목당 가격 조회 1회(ticker 기준 캐시). 같은 종목이 단타/스윙 등으로 서로
            # 다른 실제 매수일에 여러 건 있을 수 있으므로, 벤치마크와 동일하게 종목별
            # 최소~최대 매수일을 먼저 합친 뒤 그 범위로 심볼당 1회만 조회한다(horizon별
            # 재조회 없음). 매수일 하나만 기준으로 좁게 캐시하면 같은 종목의 다른 매수
            # 건이 그 범위 밖 날짜를 필요로 할 때 조용히 데이터 없음/오답이 되는 문제가
            # 있어(2026-07-13 전체 코드검사에서 발견) 벤치마크 캐시 방식과 통일했다.
            _actual_ticker_ranges = {}
            for _ai in _actual_save_target_items:
                _ticker = (_ai.get("ticker") or "").strip()
                if not _ticker:
                    continue
                _entry_dt = datetime.strptime(_ai["actual_entry_date"], "%Y-%m-%d")
                _t_range = _actual_ticker_ranges.setdefault(
                    _ticker, {"min": _entry_dt, "max": _entry_dt}
                )
                _t_range["min"] = min(_t_range["min"], _entry_dt)
                _t_range["max"] = max(_t_range["max"], _entry_dt)

            _actual_price_df_cache = {}
            for _ticker, _t_range in _actual_ticker_ranges.items():
                _start = (_t_range["min"] - timedelta(days=10)).strftime("%Y-%m-%d")
                _end = (_t_range["max"] + timedelta(days=45)).strftime("%Y-%m-%d")
                _actual_price_df_cache[_ticker] = price_data.get_price_history(
                    _ticker, _start, _end
                )

            _actual_bench_ranges = {}
            for _ai in _actual_save_target_items:
                _bench_symbol = performance.determine_benchmark(
                    _ai.get("market"), _ai.get("ticker")
                )
                if _bench_symbol is None:
                    continue
                _entry_dt = datetime.strptime(_ai["actual_entry_date"], "%Y-%m-%d")
                _range = _actual_bench_ranges.setdefault(
                    _bench_symbol, {"min": _entry_dt, "max": _entry_dt}
                )
                _range["min"] = min(_range["min"], _entry_dt)
                _range["max"] = max(_range["max"], _entry_dt)

            _actual_bench_df_cache = {}
            for _bench_symbol, _range in _actual_bench_ranges.items():
                _start = (_range["min"] - timedelta(days=10)).strftime("%Y-%m-%d")
                _end = (_range["max"] + timedelta(days=45)).strftime("%Y-%m-%d")
                _actual_bench_df_cache[_bench_symbol] = price_data.get_benchmark_history(
                    _bench_symbol, _start, _end
                )

            _actual_save_candidate_rows = []
            _actual_save_failed = []
            for _ai in _actual_save_target_items:
                _ticker = (_ai.get("ticker") or "").strip()
                _price_df = _actual_price_df_cache.get(_ticker)
                _bench_symbol = performance.determine_benchmark(
                    _ai.get("market"), _ai.get("ticker")
                )
                _bench_df = (
                    _actual_bench_df_cache.get(_bench_symbol)
                    if _bench_symbol is not None
                    else None
                )
                try:
                    _actual_eval_result = performance.evaluate_actual_item(
                        _ai, _price_df, _bench_df
                    )
                    _rows_for_item = performance.build_actual_outcome_rows(
                        _ai["id"], _actual_eval_result
                    )
                except ValueError as _actual_calc_err:
                    _actual_save_failed.append(
                        (
                            _ai.get("stock_name") or _ai.get("ticker") or f"id={_ai['id']}",
                            str(_actual_calc_err),
                        )
                    )
                    continue
                _actual_save_candidate_rows.extend(_rows_for_item)

            for _fail_name, _fail_reason in _actual_save_failed:
                st.error(f"{_fail_name}: {_fail_reason}")

            if not _actual_save_candidate_rows:
                st.info("저장 가능한 완료 실매매 성과가 없습니다.")
            else:
                try:
                    _actual_saved_count = db.upsert_report_item_outcomes(
                        _actual_save_candidate_rows
                    )
                except Exception as _actual_save_err:
                    st.error(f"실매매 성과 저장 중 오류가 발생했습니다: {_actual_save_err}")
                else:
                    st.success(f"실매매 성과 {_actual_saved_count}건을 저장·갱신했습니다.")
                    _actual_after_save = db.get_report_outcomes(
                        selected_report_id
                    )
                    _actual_outcomes_after_save = [
                        o for o in _actual_after_save if o["entry_basis"] == "actual"
                    ]
                    _actual_horizons_after_save = sorted(
                        {o["horizon_sessions"] for o in _actual_outcomes_after_save}
                    )
                    _actual_horizons_display = (
                        "·".join(f"{h}거래일" for h in _actual_horizons_after_save)
                        if _actual_horizons_after_save
                        else "-"
                    )
                    st.caption(
                        f"저장 상태: actual {len(_actual_outcomes_after_save)}건 / "
                        f"{_actual_horizons_display}"
                    )

    # 저장된 실매매 성과 조회 전용 표시 (evaluate_actual_item()/evaluate_item() 재호출,
    # 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE 전혀 없음). get_report_outcomes()가
    # 반환하는 DB 스냅샷을 entry_basis='actual'만 걸러서 그대로 보여준다 — 임의로 행을
    # 만들지 않는다. judgment 표("저장된 판단 성과 보기")와는 완전히 별도 expander로
    # 유지하며 한 표에 섞지 않는다.


with tab_review:
    st.subheader("④ 복기·통계")
    st.markdown("<div style='font-size:17px;line-height:1.5;color:#CBD5E1'>복기할 종목을 선택해 결과·실수·태그를 기록하세요.</div>", unsafe_allow_html=True)
    st.caption("저장된 판단과 실제 행동·거래 종료 결과를 조회하고 복기 진행 상태를 확인하는 화면입니다.")

    _tab4_reports = db.list_reports()
    _tab4_report_saved_at = {report["id"]: report.get("saved_at") or "-" for report in _tab4_reports}
    _tab4_items = []
    _tab4_seen_ids = set()
    for _tab4_report in _tab4_reports:
        for _tab4_item in db.get_report_items(_tab4_report["id"]):
            _tab4_item_id = _tab4_item.get("id")
            if _tab4_item_id in _tab4_seen_ids:
                continue
            _tab4_seen_ids.add(_tab4_item_id)
            _tab4_items.append(_tab4_item)

    _tab4_pending_count = sum(1 for item in _tab4_items if item.get("review_done") not in (1, True))
    _tab4_done_count = sum(1 for item in _tab4_items if item.get("review_done") in (1, True))
    _tab4_closed_count = sum(
        1 for item in _tab4_items if _classify_actual_trade_status(item) == "청산 완료"
    )
    _tab4_summary_cols = st.columns(4)
    _tab4_summary_cols[0].metric("전체 종목 수", len(_tab4_items))
    _tab4_summary_cols[1].metric("복기 대기 수", _tab4_pending_count)
    _tab4_summary_cols[2].metric("복기 완료 수", _tab4_done_count)
    _tab4_summary_cols[3].metric("청산 완료 수", _tab4_closed_count)

    _tab4_market = st.selectbox(
        "시장", ["전체", "KR", "US"], key="tab4_market_filter"
    )
    _tab4_review_status = st.selectbox(
        "복기 상태", ["복기 대기", "복기 완료", "전체"], key="tab4_review_status_filter"
    )

    _tab4_filtered_items = []
    for _tab4_item in _tab4_items:
        if _classify_actual_trade_status(_tab4_item) not in ("청산 완료", "보류", "제외"):
            continue
        if _tab4_market != "전체" and _tab4_item.get("market") != _tab4_market:
            continue
        _tab4_item_review_status = (
            "복기 완료" if _tab4_item.get("review_done") in (1, True) else "복기 대기"
        )
        if _tab4_review_status != "전체" and _tab4_item_review_status != _tab4_review_status:
            continue
        _tab4_filtered_items.append(_tab4_item)

    st.caption(f"필터 결과: {len(_tab4_filtered_items)}건 / 전체 {len(_tab4_items)}건")
    with st.expander("복기 진행 현황 보기", expanded=False):
        st.caption(
            "이 표는 어떤 보고서에 테마·실제 행동·성과 기록이 부족한지 확인하는 복기 "
            "진행 현황입니다."
        )

        _review_statuses = db.get_report_review_status()

        def _classify_review_status(s):
            if s["theme_tagged_count"] == 0 and s["action_recorded_count"] == 0:
                return "기록 전"
            if s["action_recorded_count"] < s["item_count"]:
                return "기록 중"
            if s["judgment_outcome_count"] == 0:
                return "성과 저장 대기"
            if s["judgment_item_count"] < s["item_count"]:
                return "복기 중"
            return "복기 데이터 있음"

        _review_total_judgment_outcomes = sum(
            s["judgment_outcome_count"] for s in _review_statuses
        )
        _review_total_actual_outcomes = sum(
            s["actual_outcome_count"] for s in _review_statuses
        )
        if _review_total_judgment_outcomes == 0 and _review_total_actual_outcomes == 0:
            st.caption(
                "아직 저장된 성과가 없습니다. 날짜가 충분히 지난 과거 보고서를 선택해 "
                "판단 성과부터 저장해야 합니다."
            )

        _review_status_filter_in = st.selectbox(
            "상태 필터",
            ["전체", "기록 전", "기록 중", "성과 저장 대기", "복기 중", "복기 데이터 있음"],
            key="tab4_progress_status_filter",
        )

        _review_rows_with_status = [
            {**s, "_status": _classify_review_status(s)} for s in _review_statuses
        ]
        if _review_status_filter_in != "전체":
            _review_rows_with_status = [
                s for s in _review_rows_with_status
                if s["_status"] == _review_status_filter_in
            ]

        if not _review_rows_with_status:
            st.info("이 조건에 해당하는 보고서가 없습니다.")
        else:
            _review_table_rows = [
                {
                    "보고서 ID": s.get("report_id"),
                    "저장일": s.get("saved_at") or "-",
                    "시장": s.get("market_scope") or "-",
                    "브리핑 단계": s.get("briefing_stage") or "-",
                    "시점 구분": s.get("timing_class") or "-",
                    "종목 수": s.get("item_count"),
                    "테마 기록": s.get("theme_tagged_count"),
                    "행동 기록": s.get("action_recorded_count"),
                    "실제 매수": s.get("actual_buy_count"),
                    "실매매 준비": s.get("actual_ready_count"),
                    "판단 성과 행": s.get("judgment_outcome_count"),
                    "실매매 성과 행": s.get("actual_outcome_count"),
                    "판단 성과 종목": s.get("judgment_item_count"),
                    "실매매 성과 종목": s.get("actual_item_count"),
                    "현재 상태": s.get("_status"),
                }
                for s in _review_rows_with_status
            ]
            st.dataframe(
                pd.DataFrame(_review_table_rows), width="stretch", hide_index=True,
            )

    with st.expander("성과 계산·저장(관리)", expanded=False):
        _tab4_outcome_reports = sorted(
            _tab4_reports,
            key=lambda report: report.get("saved_at") or "",
            reverse=True,
        )
        _tab4_outcome_options = {
            f"#{report['id']} ({report.get('saved_at') or '-'})": report["id"]
            for report in _tab4_outcome_reports
        }
        if _tab4_outcome_options:
            _tab4_outcome_label = st.selectbox(
                "성과 저장 대상 보고서",
                list(_tab4_outcome_options.keys()),
                key="tab4_outcome_report_select",
            )
            _tab4_outcome_report_id = _tab4_outcome_options[_tab4_outcome_label]
            _tab4_outcome_items = db.get_report_items(_tab4_outcome_report_id)
            _tab4_saved_outcomes = db.get_report_outcomes(_tab4_outcome_report_id)
            _tab4_judgment_saved = sum(1 for o in _tab4_saved_outcomes if o.get("entry_basis") == "judgment")
            _tab4_actual_saved = sum(1 for o in _tab4_saved_outcomes if o.get("entry_basis") == "actual")
            _tab4_actual_buys = [i for i in _tab4_outcome_items if i.get("actual_action") == "매수"]
            _tab4_actual_ready = [
                i for i in _tab4_actual_buys
                if i.get("actual_entry_price") is not None and i.get("actual_entry_date") is not None
            ]
            st.caption(
                f"선택 보고서: 전체 {len(_tab4_outcome_items)}종목 / "
                f"저장된 판단 성과 {_tab4_judgment_saved}건 / 저장된 실매매 성과 {_tab4_actual_saved}건 / "
                f"실제 매수 기록 {len(_tab4_actual_buys)}건 / 계산 준비 {len(_tab4_actual_ready)}건"
            )
            if not _tab4_saved_outcomes:
                st.info("아직 저장된 성과 데이터가 없습니다. 오류가 아닙니다.")
            if not _tab4_judgment_saved:
                st.caption("판단 성과 저장을 실행하면 보유기간별 가격 성과를 계산합니다.")
            if not _tab4_actual_buys:
                st.caption("③에서 실제 매수 기록을 입력해야 실매매 성과를 계산할 수 있습니다.")
            elif len(_tab4_actual_ready) < len(_tab4_actual_buys):
                _tab4_missing = []
                for _item in _tab4_actual_buys:
                    _missing = []
                    if _item.get("actual_entry_price") is None:
                        _missing.append("실제 매수가")
                    if _item.get("actual_entry_date") is None:
                        _missing.append("실제 매수일")
                    if _missing:
                        _tab4_missing.append(f"{_item.get('stock_name') or _item.get('ticker')}: {', '.join(_missing)}")
                st.caption("입력 부족: " + " / ".join(_tab4_missing))
            _tab4_performance_ready = _render_performance_data_load_gate("tab4_performance_data_load_button")
            _tab4_verification_rows = (
                _cached_verification_rows(_reports_signature())
                if _tab4_performance_ready
                else []
            )
            _render_judgment_outcome_save_button(
                _tab4_outcome_report_id,
                _tab4_verification_rows,
                key_prefix="tab4_",
            )
            _render_actual_outcome_save_section(
                _tab4_outcome_report_id,
                key_prefix="tab4_",
            )
        else:
            st.info("성과 저장 대상 보고서가 없습니다.")

    st.markdown("---")
    with st.expander("탈락 종목 기록", expanded=False):
        st.caption("자비스가 걸러낸(또는 사용자가 스스로 제외한) 종목을 report와 별도로 기록합니다.")
        rc1, rc2, rc3 = st.columns(3)
        rej_market = rc1.selectbox("시장", ["KR", "US"], key="tab4_rej_market")
        rej_ticker = rc2.text_input("종목코드", key="tab4_rej_ticker")
        rej_stock_name = rc3.text_input("종목명", key="tab4_rej_stock_name")

        rc4, rc5 = st.columns(2)
        rej_trade_mode = rc4.selectbox("매매유형", ["단타", "스윙", "미정"], key="tab4_rej_trade_mode")
        rej_assumed_entry_price = rc5.number_input(
            "가정 진입가(선택)", value=0.0, min_value=0.0, step=100.0, key="tab4_rej_assumed_entry_price"
        )

        rej_reason = st.text_input("탈락 사유", key="tab4_rej_reason")
        rej_note = st.text_input("메모(선택)", key="tab4_rej_note")

        _rej_report_options = ["연결 안 함"] + [
            f"#{r['id']} {r['saved_at']} {r['market_scope']}" for r in db.list_reports()
        ]
        _rej_report_label_to_id = {
            f"#{r['id']} {r['saved_at']} {r['market_scope']}": r["id"] for r in db.list_reports()
        }
        rej_report_choice = st.selectbox("연결 report(선택)", _rej_report_options, key="tab4_rej_source_report")

        if st.button("탈락 종목 저장", key="tab4_rej_save"):
            if not rej_ticker.strip() and not rej_stock_name.strip():
                st.warning("종목코드 또는 종목명 중 하나는 반드시 입력해야 합니다.")
            else:
                _now_str = datetime.now().isoformat(timespec="seconds")
                _source_report_id = _rej_report_label_to_id.get(rej_report_choice)
                db.insert_rejected_item(
                    _now_str,
                    rej_market,
                    rej_ticker.strip() or None,
                    rej_stock_name.strip() or None,
                    rej_trade_mode,
                    rej_reason.strip() or None,
                    rej_assumed_entry_price or None,
                    rej_note.strip() or None,
                    _source_report_id,
                    _now_str,
                )
                st.success("탈락 종목 기록 저장 완료")
                st.rerun()

        st.markdown("#### 최근 탈락 기록 (최대 10건)")
        _recent_rejected = db.list_recent_rejected(limit=10)
        if not _recent_rejected:
            st.info("아직 기록된 탈락 종목이 없습니다.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "rejected_at": r["rejected_at"],
                            "market": r["market"],
                            "ticker": r["ticker"],
                            "stock_name": r["stock_name"],
                            "trade_mode": r["trade_mode"],
                            "reject_reason": r["reject_reason"],
                            "assumed_entry_price": r["assumed_entry_price"],
                            "source_report_id": r["source_report_id"],
                        }
                        for r in _recent_rejected
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


    _tab4_table_rows = []
    for _tab4_item in _tab4_filtered_items:
        _tab4_table_rows.append(
            {
                "보고서 날짜": _tab4_report_saved_at.get(_tab4_item.get("report_id"), "-"),
                "보고서 ID": _tab4_item.get("report_id") or "-",
                "시장": _tab4_item.get("market") or "-",
                "종목명": _tab4_item.get("stock_name") or "-",
                "티커": _tab4_item.get("ticker") or "-",
                "실제 행동": db.normalize_actual_action(_tab4_item.get("actual_action")),
                "거래 진행 상태": _classify_actual_trade_status(_tab4_item),
                "result_r": _fmt_result_r(_tab4_item.get("result_r")),
                "복기 상태": "복기 완료" if _tab4_item.get("review_done") in (1, True) else "복기 대기",
                "복기 메모": "있음" if (_tab4_item.get("review_memo") or "").strip() else "없음",
            }
        )
    if _tab4_table_rows:
        st.dataframe(pd.DataFrame(_tab4_table_rows), width="stretch", hide_index=True)
    else:
        st.info("조건에 맞는 복기 대상 종목이 없습니다.")

    _tab4_item_options = {
        item["id"]: (
            f"#{item['id']} · {_tab4_report_saved_at.get(item.get('report_id'), '-')} · "
            f"{item.get('market') or '-'} · {item.get('ticker') or '-'} · "
            f"{_classify_actual_trade_status(item)}"
        )
        for item in _tab4_filtered_items
        if _classify_actual_trade_status(item) in ("청산 완료", "보류", "제외")
    }
    if st.session_state.get("tab4_selected_item_id") not in [None, *list(_tab4_item_options.keys())]:
        st.session_state.pop("tab4_selected_item_id", None)
    _tab4_selected_id = st.selectbox(
        "상세 복기할 report_item 선택",
        options=[None, *list(_tab4_item_options.keys())],
        format_func=lambda item_id: "선택하지 않음" if item_id is None else _tab4_item_options[item_id],
        key="tab4_selected_item_id",
    )
    _tab4_selected_item = next(
        (item for item in _tab4_filtered_items if item.get("id") == _tab4_selected_id), None
    )
    if _tab4_selected_item is not None:
        _tab4_item = _tab4_selected_item
        _tab4_item_status = _classify_actual_trade_status(_tab4_item)
        _tab4_item_id = _tab4_item["id"]
        _tab4_review_done_key = f"tab4_review_done_{_tab4_item_id}"
        _tab4_review_memo_key = f"tab4_review_memo_{_tab4_item_id}"
        if _tab4_item_status in ("청산 완료", "보류", "제외"):
            with st.expander(
                f"복기 입력 — {_tab4_item.get('stock_name') or '-'} ({_tab4_item.get('market') or '-'})",
                expanded=False,
            ):
                _tab4_review_done_in = st.checkbox(
                    "복기 완료",
                    value=_tab4_item.get("review_done") in (1, True),
                    key=_tab4_review_done_key,
                )
                _tab4_review_memo_in = st.text_area(
                    "복기 메모",
                    value=_tab4_item.get("review_memo") or "",
                    key=_tab4_review_memo_key,
                )
                if st.button("복기 저장", key=f"tab4_review_save_{_tab4_item_id}"):
                    try:
                        _tab4_review_saved = db.update_report_item_review(
                            _tab4_item_id,
                            1 if _tab4_review_done_in else 0,
                            _tab4_review_memo_in,
                        )
                    except ValueError as _tab4_review_err:
                        st.error(f"복기 저장 실패: {_tab4_review_err}")
                    else:
                        if _tab4_review_saved:
                            st.success("복기가 저장되었습니다.")
                            st.rerun()
                        else:
                            st.error("복기 저장 실패: 대상 기록을 찾지 못했습니다.")
        else:
            st.caption(
                f"{_tab4_item.get('stock_name') or '-'}: 거래 상태 확정 후 복기 가능 "
                f"({_tab4_item_status})"
            )
        _render_review_tag_editors(
            _tab4_item,
            _tab4_item.get("stock_name") or "-",
            _tab4_item.get("trade_mode") or "-",
            key_prefix="tab4_",
        )


if _saved_view == "지난 기록":
    with tab_saved:
        st.subheader("지난 기록 보기")

        with st.expander("찾아보기", expanded=False):
            fcol1, fcol2 = st.columns(2)
            filter_date_from = fcol1.date_input(
                "시작 날짜", value=None, key="filter_date_from"
            )
            filter_date_to = fcol2.date_input(
                "끝 날짜", value=None, key="filter_date_to"
            )

            filter_market_scope = st.multiselect(
                "시장", db.MARKET_SCOPE_CHOICES, key="filter_market_scope", placeholder="선택하세요"
            )
            filter_timing_class = st.multiselect(
                "장 구분", db.TIMING_CLASS_CHOICES, key="filter_timing_class", placeholder="선택하세요"
            )
            filter_verdict = st.multiselect(
                "판단", VERDICT_ORDER, format_func=_display_verdict_name, key="filter_verdict", placeholder="선택하세요"
            )
            filter_briefing_stage = st.multiselect(
                "판단 시점", db.BRIEFING_STAGE_CHOICES, key="filter_briefing_stage", placeholder="선택하세요"
            )
            filter_signal_type = st.multiselect(
                "신호 종류", db.SIGNAL_TYPE_CHOICES, format_func=_display_signal_type, key="filter_signal_type", placeholder="선택하세요"
            )
            filter_day_conclusion_kw = st.text_input(
                "오늘 요약 검색", key="filter_day_conclusion"
            )
            filter_raw_briefing_kw = st.text_input(
                "판단 근거 검색", key="filter_raw_briefing"
            )

            if st.button("검색 조건 지우기", key="filter_reset"):
                for k in (
                    "filter_date_from",
                    "filter_date_to",
                    "filter_market_scope",
                    "filter_timing_class",
                    "filter_verdict",
                    "filter_briefing_stage",
                    "filter_signal_type",
                    "filter_day_conclusion",
                    "filter_raw_briefing",
                ):
                    st.session_state.pop(k, None)
                st.rerun()

        reports = db.search_reports(
            date_from=filter_date_from.isoformat() if filter_date_from else None,
            date_to=filter_date_to.isoformat() if filter_date_to else None,
            market_scopes=filter_market_scope or None,
            timing_classes=filter_timing_class or None,
            verdicts=filter_verdict or None,
            day_conclusion_keyword=filter_day_conclusion_kw or None,
            raw_briefing_keyword=filter_raw_briefing_kw or None,
            briefing_stages=filter_briefing_stage or None,
            signal_types=filter_signal_type or None,
        )

        total_all = len(db.list_reports())
        st.caption(f"전체 {total_all}건 중 {len(reports)}건 표시")

        if not reports:
            st.info("조건에 맞는 기록이 없습니다.")
        else:
            options = {
                r["id"]: f"{r['saved_at']} | {r['market_scope']} | {r['timing_class']} | "
                f"{(r['day_conclusion'] or '')[:30]}"
                for r in reports
            }

            # reports는 saved_at 기준 최신순으로 정렬되어 있으므로 첫 항목이 (현재 필터 기준) 최신이다.
            newest_in_view_id = next(iter(options))

            # DB 전체 기준 최신 report id. 저장 직후 이 값이 바뀌면 자동으로 그 report를 선택한다.
            global_latest = db.get_latest_report()
            global_latest_id = global_latest["id"] if global_latest else None
            prev_global_latest_id = st.session_state.get("archive_prev_global_latest_id")

            if "archive_select" not in st.session_state or st.session_state.get("archive_select") not in options:
                # 최초 진입, 혹은 필터링으로 기존 선택이 더 이상 옵션에 없음 -> 현재 목록의 최신으로
                st.session_state["archive_select"] = newest_in_view_id
            elif global_latest_id is not None and global_latest_id != prev_global_latest_id and global_latest_id in options:
                # 새 report가 저장됨(전역 최신 id가 바뀜) -> 그 report로 자동 전환
                st.session_state["archive_select"] = global_latest_id

            st.session_state["archive_prev_global_latest_id"] = global_latest_id

            selected_id = st.selectbox(
                "지난 기록 선택",
                options=list(options.keys()),
                format_func=lambda rid: options[rid],
                key="archive_select",
            )
            selected_report = db.get_report(selected_id)
            st.markdown("---")
            render_report_detail(selected_report, show_raw_briefing=True)

def _render_actual_trade_entry_inputs(saved_item, key_prefix=""):
    """실제 행동·매수 입력 및 저장 UI를 렌더링한다."""
    if not saved_item.get("id"):
        return

    _item_name = saved_item.get("stock_name") or "-"
    with st.expander("실제 행동·매수 입력", expanded=False):
        st.markdown("---")
        _action_key = f"{key_prefix}actualaction_{saved_item['id']}"
        _action_options = ["미기록", "매수", "보류", "제외"]
        _action_stored = db.normalize_actual_action(saved_item.get("actual_action"))
        _action_in = st.selectbox(
            "실제 행동",
            _action_options,
            index=_action_options.index(_action_stored),
            key=f"{_action_key}_select",
        )
        if st.button("실제 행동 저장", key=f"{_action_key}_save"):
            _final_action = None if _action_in == "미기록" else _action_in
            try:
                _action_ok = db.update_report_item_actual_action(saved_item["id"], _final_action)
            except ValueError as _action_err:
                st.error(f"{_item_name}: {_action_err}")
            else:
                if _action_ok:
                    st.success("실제 행동이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"실제 행동 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        st.markdown("---")
        _price_key = f"{key_prefix}actualentryprice_{saved_item['id']}"
        _price_default_text = _fmt_actual_entry_price_display(saved_item.get("actual_entry_price"))
        _price_text_in = st.text_input(
            "실제 평균 체결가",
            value=_price_default_text,
            key=f"{_price_key}_input",
            help=(
                "실제로 매수한 평균 체결가입니다. 실제 행동이 '매수'일 때만 "
                "저장할 수 있습니다."
            ),
        )
        if st.button("실제 체결가 저장", key=f"{_price_key}_save"):
            _parsed_price, _parse_error = _parse_actual_entry_price_text(_price_text_in)
            if _parse_error:
                st.error(f"{_item_name}: {_parse_error}")
            else:
                try:
                    _price_ok = db.update_report_item_actual_entry_price(
                        saved_item["id"], _parsed_price
                    )
                except ValueError as _price_err:
                    st.error(f"{_item_name}: {_price_err}")
                else:
                    if _price_ok:
                        st.success("실제 체결가가 저장되었습니다.")
                        st.rerun()
                    else:
                        st.error(
                            f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                            f"(id={saved_item['id']})."
                        )

        st.markdown("---")
        _entry_date_key = f"{key_prefix}actualentrydate_{saved_item['id']}"
        _entry_date_default_text = saved_item.get("actual_entry_date") or ""
        _entry_date_text_in = st.text_input(
            "실제 매수 거래일",
            value=_entry_date_default_text,
            key=f"{_entry_date_key}_input",
            placeholder="2026-07-10",
            help=(
                "실제 매수한 거래소 기준 거래일입니다. 미국장은 한국시간 "
                "날짜가 아니라 미국 현지 거래일을 입력합니다."
            ),
        )
        if st.button("실제 매수일 저장", key=f"{_entry_date_key}_save"):
            try:
                _entry_date_ok = db.update_report_item_actual_entry_date(
                    saved_item["id"], _entry_date_text_in
                )
            except ValueError as _entry_date_err:
                st.error(f"{_item_name}: {_entry_date_err}")
            else:
                if _entry_date_ok:
                    st.success("실제 매수 거래일이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        _quantity_key = f"{key_prefix}quantity_{saved_item['id']}"
        _quantity_in = st.number_input(
            "매수 수량",
            value=saved_item.get("quantity"),
            min_value=1,
            step=1,
            format="%d",
            key=f"{_quantity_key}_input",
        )
        if st.button("매수 수량 저장", key=f"{_quantity_key}_save"):
            try:
                _quantity_ok = db.update_report_item_quantity(
                    saved_item["id"], _quantity_in
                )
            except ValueError as _quantity_err:
                st.error(f"{_item_name}: {_quantity_err}")
            else:
                if _quantity_ok:
                    st.success("매수 수량이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        _fee_key = f"{key_prefix}actualfee_{saved_item['id']}"
        st.caption("실제 수수료와 세금을 합산한 금액을 직접 입력합니다. 0원과 미입력은 구분됩니다.")
        _fee_in = st.number_input(
            "실제 수수료·세금 합계",
            value=saved_item.get("actual_fee"),
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=f"{_fee_key}_input",
        )
        if st.button("실제 수수료·세금 합계 저장", key=f"{_fee_key}_save"):
            try:
                _fee_ok = db.update_report_item_actual_fee(saved_item["id"], _fee_in)
            except ValueError as _fee_err:
                st.error(f"{_item_name}: {_fee_err}")
            else:
                if _fee_ok:
                    st.success("실제 수수료·세금 합계가 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        if (saved_item.get("market") == "US") and (saved_item.get("trade_mode") == "스윙"):
            st.markdown("---")
            _earnings_key = f"{key_prefix}earningscheck_{saved_item['id']}"
            _earnings_checked_in = st.checkbox(
                "실적 발표일 확인함",
                value=bool(saved_item.get("earnings_check_done")),
                key=f"{_earnings_key}_checkbox",
            )
            if st.button("실적 발표일 확인 저장", key=f"{_earnings_key}_save"):
                db.update_report_item_earnings_check(saved_item["id"], _earnings_checked_in)
                st.success("실적 발표일 확인 여부가 저장되었습니다.")
                st.rerun()
            if not _earnings_checked_in:
                st.caption("실적 발표 전 진입은 진입 회피를 권장합니다 (차단하지 않는 참고용 경고).")

        if saved_item.get("actual_action") == "매수":
            if (
                saved_item.get("actual_entry_price") is not None
                and saved_item.get("actual_entry_date") is not None
            ):
                st.caption("실매매 성과 계산 준비 완료")
            else:
                st.caption(
                    "실매매 성과 계산에는 실제 평균 체결가와 실제 매수 "
                    "거래일이 모두 필요합니다."
                )
            if saved_item.get("entry_time"):
                st.caption(f"자동 기록된 진입 시각: {saved_item['entry_time']}")
            if saved_item.get("auto_loss_streak_flag") == "YES":
                st.warning(
                    "손실직후 자동 태그 — 직전 손절 2건이 오늘/어제 안에 있습니다 "
                    "(복구매매 주의, 차단하지 않는 참고용 경고)"
                )
            _todays_buy_count = db.count_todays_actual_buys()
            _daily_entry_threshold = db.get_daily_entry_warning_threshold()
            if _todays_buy_count > _daily_entry_threshold:
                st.warning(
                    f"오늘 신규 진입 {_todays_buy_count}건 — 경고 기준({_daily_entry_threshold}건) "
                    "초과 (차단하지 않는 참고용 경고)"
                )


def _render_trade_exit_inputs(saved_item, key_prefix=""):
    """청산 결과 입력·수정 및 저장 UI를 렌더링한다."""
    if not saved_item.get("id"):
        return

    _item_name = saved_item.get("stock_name") or "-"
    _trade_mode = saved_item.get("trade_mode") or "-"
    with st.expander(f"청산 결과 입력 / 수정 — {_item_name} ({_trade_mode})"):
        _exit_key = f"{key_prefix}exit_{saved_item['id']}"
        _exit_price_in = st.number_input(
            "실제 청산가", value=float(saved_item.get("actual_exit_price") or 0.0),
            min_value=0.0, step=100.0, key=f"{_exit_key}_price",
        )
        _exit_date_default = None
        if saved_item.get("actual_exit_date"):
            try:
                _exit_date_default = datetime.strptime(
                    saved_item["actual_exit_date"], "%Y-%m-%d"
                ).date()
            except ValueError:
                _exit_date_default = None
        _exit_date_in = st.date_input(
            "실제 청산일", value=_exit_date_default, key=f"{_exit_key}_date",
        )
        _plan_followed_options = ["미입력", "예", "아니오", "부분"]
        _plan_followed_default = saved_item.get("plan_followed") or "미입력"
        if _plan_followed_default not in _plan_followed_options:
            _plan_followed_default = "미입력"
        _plan_followed_in = st.selectbox(
            "계획 준수 여부", _plan_followed_options,
            index=_plan_followed_options.index(_plan_followed_default),
            key=f"{_exit_key}_plan_followed",
        )
        _exit_reason_options = [
            "미입력", "손절", "목표가", "시간청산", "조기매도",
            "손절지연", "복구매매", "감정매매", "뉴스변경", "기타",
        ]
        _exit_reason_default = saved_item.get("exit_reason") or "미입력"
        if _exit_reason_default not in _exit_reason_options:
            _exit_reason_default = "미입력"
        _exit_reason_in = st.selectbox(
            "청산 사유", _exit_reason_options,
            index=_exit_reason_options.index(_exit_reason_default),
            key=f"{_exit_key}_reason",
        )

        _r_basis_price = saved_item.get("actual_entry_price") or saved_item.get("entry_price")
        _r_basis_is_plan = (
            not saved_item.get("actual_entry_price") and bool(saved_item.get("entry_price"))
        )
        _preview_result_r = _compute_result_r(
            _r_basis_price, saved_item.get("stop_loss_price"), _exit_price_in or None,
        )
        _r_preview_suffix = "(계획가 기준)" if _r_basis_is_plan else ""
        st.caption(f"R수익률 미리보기: {_fmt_result_r(_preview_result_r)} {_r_preview_suffix}".rstrip())

        if st.button("청산 결과 저장", key=f"{_exit_key}_save"):
            _final_exit_price = _exit_price_in or None
            _final_exit_date = _exit_date_in.isoformat() if _exit_date_in else None
            _final_plan_followed = None if _plan_followed_in == "미입력" else _plan_followed_in
            _final_exit_reason = None if _exit_reason_in == "미입력" else _exit_reason_in
            _final_result_r = _compute_result_r(
                _r_basis_price, saved_item.get("stop_loss_price"), _final_exit_price,
            )
            _final_verification_status = _compute_verification_status(
                _final_exit_price, _final_exit_date
            )
            try:
                _exit_ok = db.update_report_item_trade_exit(
                    saved_item["id"],
                    _final_exit_price,
                    _final_exit_date,
                    _final_plan_followed,
                    _final_exit_reason,
                    _final_result_r,
                    _final_verification_status,
                )
            except ValueError as _exit_err:
                st.error(f"{_item_name}: {_exit_err}")
            else:
                if _exit_ok:
                    _cached_verification_rows.clear()
                    st.success("청산 결과가 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )


with tab_action:
    st.subheader("③ 실제 행동·거래 종료")
    st.markdown("<div style='font-size:20px;font-weight:800;line-height:1.5;color:#F3F4F6;margin-top:8px'>오늘 진행 상태</div>", unsafe_allow_html=True)
    _render_today_progress_status_strip()
    st.markdown("<div style='font-size:17px;line-height:1.5;color:#CBD5E1'>저장한 종목을 선택해 실제 매수·보류·제외 또는 청산을 기록하세요.</div>", unsafe_allow_html=True)
    st.caption("저장된 판단 이후 실제 행동과 거래 종료를 기록하는 화면입니다.")

    _tab3_market = st.selectbox(
        "시장", ["전체", "KR", "US"], key="tab3_market_filter"
    )
    _tab3_status = st.selectbox(
        "진행 상태",
        ["행동 미입력", "보유 중", "거래 종료", "전체"],
        key="tab3_status_filter",
    )

    _tab3_reports = db.list_reports()
    _tab3_report_saved_at = {report["id"]: report.get("saved_at") or "-" for report in _tab3_reports}
    _tab3_items = []
    _tab3_seen_ids = set()
    for _tab3_report in _tab3_reports:
        for _tab3_item in db.get_report_items(_tab3_report["id"]):
            _tab3_item_id = _tab3_item.get("id")
            if _tab3_item_id in _tab3_seen_ids:
                continue
            _tab3_seen_ids.add(_tab3_item_id)
            _tab3_items.append(_tab3_item)

    _tab3_filtered_items = []
    for _tab3_item in _tab3_items:
        if _tab3_market != "전체" and _tab3_item.get("market") != _tab3_market:
            continue
        _tab3_item_status = _classify_actual_trade_status(_tab3_item)
        if _tab3_status != "전체" and (
            _tab3_item_status != _tab3_status
            and not (_tab3_status == "거래 종료" and _tab3_item_status == "청산 완료")
        ):
            continue
        _tab3_filtered_items.append(_tab3_item)

    st.caption(f"필터 결과: {len(_tab3_filtered_items)}건 / 전체 {len(_tab3_items)}건")
    _tab3_item_options = {
        item["id"]: (
            f"#{item['id']} · {_tab3_report_saved_at.get(item.get('report_id'), '-')} · "
            f"{item.get('market') or '-'} · {item.get('ticker') or '-'} · "
            f"{_classify_actual_trade_status(item)}"
        )
        for item in _tab3_filtered_items
    }
    if st.session_state.get("tab3_selected_item_id") not in [None, *list(_tab3_item_options.keys())]:
        st.session_state.pop("tab3_selected_item_id", None)
    _tab3_selected_id = st.selectbox(
        "상세 입력할 report_item 선택",
        options=[None, *list(_tab3_item_options.keys())],
        format_func=lambda item_id: "선택하지 않음" if item_id is None else _tab3_item_options[item_id],
        key="tab3_selected_item_id",
    )
    _tab3_selected_item = next(
        (item for item in _tab3_filtered_items if item.get("id") == _tab3_selected_id), None
    )
    if _tab3_selected_item is not None:
        _tab3_item = _tab3_selected_item
        _tab3_item_status = _classify_actual_trade_status(_tab3_item)
        st.caption(
            f"{_tab3_item.get('market') or '-'} · {_tab3_item_status} · "
            f"{_tab3_item.get('stock_name') or '-'} ({_tab3_item.get('trade_mode') or '-'})"
        )
        _render_actual_trade_entry_inputs(_tab3_item, key_prefix="tab3_")
        if db.normalize_actual_action(_tab3_item.get("actual_action")) == "매수":
            _render_trade_exit_inputs(_tab3_item, key_prefix="tab3_")
        if _tab3_item_status == "청산 완료":
            _actual_fee = _tab3_item.get("actual_fee")
            _actual_entry_price = _tab3_item.get("actual_entry_price")
            _actual_pnl = None
            if _actual_entry_price is None:
                _pnl_text = "실제 매수가 미입력 · 계산 불가"
                _return_text = "실제 매수가 미입력 · 계산 불가"
            else:
                if _actual_fee is None:
                    _pnl_text = "비용 미입력 · 계산 불가"
                else:
                    _actual_pnl = _compute_realized_pnl(
                        _actual_entry_price,
                        _tab3_item.get("actual_exit_price"),
                        _tab3_item.get("quantity"),
                        _actual_fee,
                    )
                    if _actual_pnl is None:
                        _pnl_text = "입력값 부족 · 계산 불가"
                    else:
                        _pnl_text = f"{_actual_pnl:,.2f}"

                _return_pct = None
                if _actual_pnl is not None:
                    _return_pct = _compute_realized_return_pct(
                        _actual_pnl,
                        _actual_entry_price,
                        _tab3_item.get("quantity"),
                    )
                _return_text = (
                    "입력값 부족 · 계산 불가"
                    if _return_pct is None
                    else f"{_return_pct:+.2f}%"
                )

            _holding_days = _compute_holding_days(
                _tab3_item.get("actual_entry_date"),
                _tab3_item.get("actual_exit_date"),
            )
            if _holding_days is not None:
                _holding_text = f"{_holding_days}일"
            elif _tab3_item.get("actual_entry_date") and _tab3_item.get("actual_exit_date"):
                _holding_text = "날짜 확인 필요"
            else:
                _holding_text = "입력값 부족 · 계산 불가"

            _summary_cols = st.columns(3)
            _summary_cols[0].metric("실현손익", _pnl_text)
            _summary_cols[1].metric("실현수익률", _return_text)
            _summary_cols[2].metric("보유일", _holding_text)




if _saved_view == "저장 결과":
    with tab_saved:
        st.subheader("결과 확인")
        st.caption("저장한 종목 판단이 며칠 뒤 실제 수익률로 어떻게 나왔는지 확인하는 화면입니다.")
        st.caption(
            "승률보다 R수익률과 기대값이 중요합니다. 손절을 지키면 승률은 낮아져도 계좌는 좋아질 수 있습니다."
        )

        st.markdown("---")

        _perf_performance_ready = _render_performance_data_load_gate("perf_performance_data_load_button")
        perf_rows_all = (
            _cached_verification_rows(_reports_signature())
            if _perf_performance_ready
            else []
        )

        if not perf_rows_all:
            st.info("종목코드가 있는 종목별 기록이 없습니다.")
        else:
            # 1. 보기 범위 (기본값 "오늘 저장한 기록 전체" — "방금 저장한 기록만"은 최신 report 1건만
            # 보여줘서 한국장/미국장을 같은 날 둘 다 저장해도 한쪽만 보이는 것처럼 보일 수 있다.
            # 기본값을 오늘 저장한 기록 전체로 넓혀 두 시장이 함께 보이게 한다.)
            view_scope = st.radio(
                "볼 기록 범위",
                ["방금 저장한 기록만", "오늘 저장한 기록 전체", "모든 지난 기록"],
                horizontal=True,
                index=1,
                key="perf_view_scope",
            )
            latest_report = db.get_latest_report()
            latest_report_id = latest_report["id"] if latest_report else None
            today_str = datetime.now().strftime("%Y-%m-%d")

            if view_scope == "방금 저장한 기록만":
                scoped_rows = [row for row in perf_rows_all if row["report_id"] == latest_report_id]
            elif view_scope == "오늘 저장한 기록 전체":
                scoped_rows = [row for row in perf_rows_all if row["saved_at"].startswith(today_str)]
            else:
                scoped_rows = perf_rows_all

            # 종목명이 "-"인 행(제목 없이 저장된 항목)은 기본 화면에서 숨긴다.
            scoped_rows = [row for row in scoped_rows if row["stock_name"] and row["stock_name"] != "-"]

            # 판단 성과 저장 (report_id 1건만 대상, 명시적 버튼 클릭 시에만 저장 —
            # evaluate_item()/build_judgment_outcome_rows()로 이미 계산된 결과를 재사용하고
            # 저장을 위해 별도로 다시 평가하지 않는다. 매매유형/판정 표시 필터와는 무관하게,
            # 선택한 report_id에 속한 종목 전체(티커가 있는 항목)를 대상으로 한다 — 아래 표시용
            # 필터(단기/며칠 구분, 판단 구분)에 저장 대상이 좌우되지 않게 하기 위함이다.
            # actual 성과·pending/unavailable/error 행은 이 화면에서 만들지 않는다.
            if scoped_rows:
                st.markdown("#### 판단 성과 저장")
                st.caption(
                    "선택한 보고서 1건의 정상 계산된 판단(judgment) 성과만 report_item_outcomes에 "
                    "저장합니다. 자동 저장되지 않으며, 아래 버튼을 눌러야 저장됩니다."
                )

                _outcome_save_reports = []
                _outcome_save_seen_report_ids = set()
                for _osr_row in scoped_rows:
                    if _osr_row["report_id"] not in _outcome_save_seen_report_ids:
                        _outcome_save_seen_report_ids.add(_osr_row["report_id"])
                        _outcome_save_reports.append((_osr_row["report_id"], _osr_row["saved_at"]))
                _outcome_save_reports.sort(key=lambda pair: pair[1], reverse=True)

                _outcome_save_report_options = {
                    f"#{_rid} ({_saved_at})": _rid for _rid, _saved_at in _outcome_save_reports
                }
                _outcome_save_report_label = st.selectbox(
                    "저장 대상 보고서 선택",
                    list(_outcome_save_report_options.keys()),
                    key="judgment_outcome_save_report_select",
                )
                _outcome_save_target_report_id = _outcome_save_report_options[_outcome_save_report_label]

                # 저장된 판단 성과 조회 전용 표시 (evaluate_item() 재호출/가격·벤치마크 네트워크
                # 조회/DB INSERT·UPDATE 전혀 없음). get_report_outcomes()가 반환하는 DB 스냅샷을
                # entry_basis='judgment'만 걸러서 그대로 보여준다 — 임의로 행을 만들지 않는다.
                with st.expander("저장된 판단 성과 보기", expanded=False):
                    st.caption(
                        "이 표는 계산 화면의 실시간 값이 아니라, 저장 버튼을 눌렀을 때 DB에 "
                        "기록된 판단 성과입니다."
                    )
                    _saved_outcomes = db.get_report_outcomes(_outcome_save_target_report_id)
                    _saved_judgment_outcomes = [
                        o for o in _saved_outcomes if o["entry_basis"] == "judgment"
                    ]
                    if not _saved_judgment_outcomes:
                        st.info("아직 저장된 판단 성과가 없습니다.")
                    else:
                        _saved_judgment_outcomes = sorted(
                            _saved_judgment_outcomes,
                            key=lambda o: (o["report_item_id"], o["horizon_sessions"]),
                        )
                        _outcome_status_display = {
                            "evaluated": "완료",
                            "pending": "대기",
                            "unavailable": "데이터 없음",
                            "error": "오류",
                        }
                        _saved_outcome_table_rows = [
                            {
                                "종목명": o.get("item_name") or "-",
                                "티커": o.get("ticker") or "-",
                                "시장": o.get("market") or "-",
                                "거래일수": o.get("horizon_sessions"),
                                "기준가격": _fmt_actual_entry_price_display(o.get("entry_price_used")) or "-",
                                "목표일": o.get("target_date") or "-",
                                "종가": _fmt_actual_entry_price_display(o.get("close_price")) or "-",
                                "수익률(%)": _fmt_pct(o.get("return_pct")),
                                "벤치마크": o.get("benchmark_symbol") or "-",
                                "벤치마크 수익률(%)": _fmt_pct(o.get("benchmark_return_pct")),
                                "초과수익률(%)": _fmt_pct(o.get("excess_return_pct")),
                                "상태": _outcome_status_display.get(o.get("status"), o.get("status") or "-"),
                                "평가시각": o.get("evaluated_at") or "-",
                            }
                            for o in _saved_judgment_outcomes
                        ]
                        st.dataframe(
                            pd.DataFrame(_saved_outcome_table_rows), width="stretch", hide_index=True
                        )
                st.markdown("---")

                # 실매매 성과 저장 (판단 성과 저장 바로 아래, 같은 선택 report_id 1건만 대상,
                # 명시적 버튼 클릭 시에만 계산·저장). actual_action='매수'이고
                # actual_entry_price/actual_entry_date가 모두 채워진 종목만 대상으로 한다.
                # evaluate_item()/build_verification_rows()는 원시 price_df/benchmark_df를
                # 보존·노출하지 않으므로(가공된 결과만 반환) 재사용이 불가능하다 — 버튼을 누른
                # 뒤에만 기존 price_data.py 조회 함수로 새로 가져온다. judgment 성과(위 섹션,
                # entry_basis='judgment')는 이 섹션에서 전혀 건드리지 않는다.
                st.markdown("#### 실매매 성과 저장")
                st.caption(
                    "선택한 보고서에서 실제 행동이 '매수'이고 실제 체결가·실제 매수 거래일이 "
                    "모두 입력된 종목만 대상으로 실매매(actual) 성과를 계산해 저장합니다. "
                    "자동 저장되지 않으며, 아래 버튼을 눌러야 계산·저장됩니다."
                )

                with st.expander("저장된 실매매 성과 보기", expanded=False):
                    st.caption(
                        "이 표는 실제 평균 체결가와 실제 매수 거래일을 기준으로 계산해 DB에 "
                        "저장한 실매매 성과입니다."
                    )
                    st.caption("수수료·세금·매수 수량은 아직 반영되지 않았습니다.")
                    _saved_actual_outcomes_raw = db.get_report_outcomes(_outcome_save_target_report_id)
                    _saved_actual_outcomes = [
                        o for o in _saved_actual_outcomes_raw if o["entry_basis"] == "actual"
                    ]
                    if not _saved_actual_outcomes:
                        st.info("아직 저장된 실매매 성과가 없습니다.")
                    else:
                        _saved_actual_outcomes = sorted(
                            _saved_actual_outcomes,
                            key=lambda o: (o["report_item_id"], o["horizon_sessions"]),
                        )
                        _actual_outcome_status_display = {
                            "evaluated": "완료",
                            "pending": "대기",
                            "unavailable": "데이터 없음",
                            "error": "오류",
                        }
                        _saved_actual_outcome_table_rows = [
                            {
                                "종목명": o.get("item_name") or "-",
                                "티커": o.get("ticker") or "-",
                                "시장": o.get("market") or "-",
                                "실제 매수일": o.get("actual_entry_date") or "-",
                                "실제 기준가격": (
                                    _fmt_actual_entry_price_display(o.get("entry_price_used")) or "-"
                                ),
                                "거래일수": o.get("horizon_sessions"),
                                "목표일": o.get("target_date") or "-",
                                "종가": _fmt_actual_entry_price_display(o.get("close_price")) or "-",
                                "실매매 수익률(%)": _fmt_pct(o.get("return_pct")),
                                "벤치마크": o.get("benchmark_symbol") or "-",
                                "벤치마크 수익률(%)": _fmt_pct(o.get("benchmark_return_pct")),
                                "초과수익률(%)": _fmt_pct(o.get("excess_return_pct")),
                                "상태": _actual_outcome_status_display.get(
                                    o.get("status"), o.get("status") or "-"
                                ),
                                "평가시각": o.get("evaluated_at") or "-",
                            }
                            for o in _saved_actual_outcomes
                        ]
                        st.dataframe(
                            pd.DataFrame(_saved_actual_outcome_table_rows),
                            width="stretch",
                            hide_index=True,
                        )

                # 판단(judgment) 대 실매매(actual) 비교 조회 전용 표시. evaluate_item()/
                # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE
                # 전혀 없음 — db.get_report_outcomes()의 DB 스냅샷을
                # performance.build_judgment_actual_comparison_rows()에 그대로 넘겨 이미
                # 완성된 judgment+actual 쌍만 보여준다. 위 두 expander와 완전히 별도로 둔다.
                with st.expander("판단과 실매매 차이 보기", expanded=False):
                    st.caption(
                        "양수는 실제 진입 성과가 판단 기준보다 좋았다는 뜻이고, 음수는 실제 "
                        "진입이 더 불리했다는 뜻입니다."
                    )
                    _comparison_outcome_rows = db.get_report_outcomes(_outcome_save_target_report_id)
                    _comparison_rows = performance.build_judgment_actual_comparison_rows(
                        _comparison_outcome_rows
                    )
                    if not _comparison_rows:
                        st.info("비교 가능한 판단 성과와 실매매 성과가 아직 없습니다.")
                    else:
                        _comparison_rows = sorted(
                            _comparison_rows,
                            key=lambda c: (c["report_item_id"], c["horizon_sessions"]),
                        )
                        _comparison_table_rows = [
                            {
                                "종목명": c.get("종목명") or "-",
                                "티커": c.get("ticker") or "-",
                                "시장": c.get("market") or "-",
                                "거래일수": c.get("horizon_sessions"),
                                "판단 기준가격": (
                                    _fmt_actual_entry_price_display(c.get("judgment_entry_price"))
                                    or "-"
                                ),
                                "실제 기준가격": (
                                    _fmt_actual_entry_price_display(c.get("actual_entry_price"))
                                    or "-"
                                ),
                                "판단 수익률(%)": _fmt_pct(c.get("judgment_return_pct")),
                                "실매매 수익률(%)": _fmt_pct(c.get("actual_return_pct")),
                                "수익률 차이(%p)": _fmt_pct(c.get("return_gap_pct")),
                                "판단 초과수익률(%)": _fmt_pct(c.get("judgment_excess_return_pct")),
                                "실매매 초과수익률(%)": _fmt_pct(c.get("actual_excess_return_pct")),
                                "초과수익률 차이(%p)": _fmt_pct(c.get("excess_return_gap_pct")),
                            }
                            for c in _comparison_rows
                        ]
                        st.dataframe(
                            pd.DataFrame(_comparison_table_rows),
                            width="stretch",
                            hide_index=True,
                        )

                # 판단 잔차 원자료 조회 전용 표시. evaluate_item()/evaluate_actual_item() 재호출,
                # 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE 전혀 없음 — 위 "판단과 실매매
                # 차이 보기" expander에서 이미 조회한 _comparison_outcome_rows(동일 report_id의
                # db.get_report_outcomes() 결과)를 그대로 재사용해 같은 report_id를 중복 조회하지
                # 않는다. 자동 성공/실패 판정이나 점수는 표시하지 않는다.
                with st.expander("판단 잔차 원자료 보기", expanded=False):
                    st.caption(
                        "진입 효과가 양수면 실제 진입 성과가 판단 기준보다 유리했고, 음수면 "
                        "불리했다는 뜻입니다."
                    )
                    st.caption(
                        "보류·제외 종목의 미매수 수익률은 당시 판단 이후 종목이 얼마나 "
                        "움직였는지 보여주는 원자료입니다. 아직 성공·실패나 실수로 자동 "
                        "판정하지 않습니다."
                    )
                    _residual_rows = performance.build_decision_residual_rows(
                        _comparison_outcome_rows
                    )
                    if not _residual_rows:
                        st.info("아직 분석 가능한 판단 잔차 원자료가 없습니다.")
                    else:
                        _residual_rows = sorted(
                            _residual_rows,
                            key=lambda d: (d["report_item_id"], d["horizon_sessions"]),
                        )
                        _residual_table_rows = [
                            {
                                "종목명": d.get("종목명") or "-",
                                "티커": d.get("ticker") or "-",
                                "시장": d.get("market") or "-",
                                "테마 태그": (
                                    ", ".join(db.parse_theme_tags(d.get("theme_tags"))) or "-"
                                ),
                                "실제 행동": d.get("actual_action") or "미기록",
                                "거래일수": d.get("horizon_sessions"),
                                "판단 기준가격": (
                                    _fmt_actual_entry_price_display(d.get("judgment_entry_price"))
                                    or "-"
                                ),
                                "판단 수익률(%)": _fmt_pct(d.get("judgment_return_pct")),
                                "판단 초과수익률(%)": _fmt_pct(d.get("judgment_excess_return_pct")),
                                "실제 기준가격": (
                                    _fmt_actual_entry_price_display(d.get("actual_entry_price"))
                                    or "-"
                                ),
                                "실매매 수익률(%)": _fmt_pct(d.get("actual_return_pct")),
                                "실매매 초과수익률(%)": _fmt_pct(d.get("actual_excess_return_pct")),
                                "진입 효과(%p)": _fmt_pct(d.get("entry_effect_pct")),
                                "진입 초과효과(%p)": _fmt_pct(d.get("entry_excess_effect_pct")),
                                "미매수 종목 수익률(%)": _fmt_pct(d.get("non_buy_return_pct")),
                                "미매수 종목 초과수익률(%)": _fmt_pct(
                                    d.get("non_buy_excess_return_pct")
                                ),
                            }
                            for d in _residual_rows
                        ]
                        st.dataframe(
                            pd.DataFrame(_residual_table_rows),
                            width="stretch",
                            hide_index=True,
                        )

                # 전체 행동별 누적 통계. 위의 다른 세 expander와 달리 현재 선택한 report_id
                # 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된 성과를
                # db.get_all_report_outcomes()로 한 번에 모아 집계한다. evaluate_item()/
                # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
                # 없음 — 필터를 바꿔도 조회만 다시 할 뿐 DB에 아무것도 쓰지 않는다.
                with st.expander("전체 행동별 누적 통계 보기", expanded=False):
                    st.caption(
                        "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                        "여러 보고서의 저장된 성과를 함께 집계합니다."
                    )
                    st.caption(
                        "표본수가 적으면 결과가 크게 흔들릴 수 있으며, 현재 표는 자동 판정이 "
                        "아닌 누적 원자료 통계입니다."
                    )

                    _summary_filter_cols = st.columns(3)
                    _summary_market_in = _summary_filter_cols[0].selectbox(
                        "시장",
                        ["전체", "KR", "US", "OTHER"],
                        key="action_summary_market_filter",
                    )
                    _summary_date_from_in = _summary_filter_cols[1].text_input(
                        "시작일",
                        value="",
                        key="action_summary_date_from_filter",
                        placeholder="2026-07-01",
                    )
                    _summary_date_to_in = _summary_filter_cols[2].text_input(
                        "종료일",
                        value="",
                        key="action_summary_date_to_filter",
                        placeholder="2026-07-31",
                    )

                    _summary_market_filter = (
                        None if _summary_market_in == "전체" else _summary_market_in
                    )
                    _summary_date_from_filter = _summary_date_from_in.strip() or None
                    _summary_date_to_filter = _summary_date_to_in.strip() or None

                    try:
                        _summary_outcome_rows = db.get_all_report_outcomes(
                            market=_summary_market_filter,
                            date_from=_summary_date_from_filter,
                            date_to=_summary_date_to_filter,
                        )
                    except ValueError as _summary_query_err:
                        st.error(f"조회 조건 오류: {_summary_query_err}")
                    else:
                        _summary_residual_rows = performance.build_decision_residual_rows(
                            _summary_outcome_rows
                        )
                        _summary_action_rows = performance.build_action_residual_summary(
                            _summary_residual_rows
                        )
                        if not _summary_action_rows:
                            st.info("아직 누적 통계를 계산할 저장 성과가 없습니다.")
                        else:
                            _summary_table_rows = [
                                {
                                    "거래일수": s.get("horizon_sessions"),
                                    "실제 행동": s.get("actual_action"),
                                    "전체 표본수": s.get("sample_count"),
                                    "판단 수익률 표본수": s.get("judgment_return_count"),
                                    "판단 평균 수익률(%)": _fmt_pct(s.get("judgment_return_avg")),
                                    "판단 중앙 수익률(%)": _fmt_pct(
                                        s.get("judgment_return_median")
                                    ),
                                    "판단 양수 개수": s.get("judgment_positive_count"),
                                    "판단 양수 비율(%)": _fmt_pct(s.get("judgment_positive_rate")),
                                    "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                    "판단 평균 초과수익률(%)": _fmt_pct(
                                        s.get("judgment_excess_avg")
                                    ),
                                    "진입 효과 표본수": s.get("entry_effect_count"),
                                    "평균 진입 효과(%p)": _fmt_pct(s.get("entry_effect_avg")),
                                    "중앙 진입 효과(%p)": _fmt_pct(s.get("entry_effect_median")),
                                    "미매수 표본수": s.get("non_buy_return_count"),
                                    "미매수 평균 수익률(%)": _fmt_pct(s.get("non_buy_return_avg")),
                                    "미매수 중앙 수익률(%)": _fmt_pct(
                                        s.get("non_buy_return_median")
                                    ),
                                    "미매수 양수 개수": s.get("non_buy_positive_count"),
                                    "미매수 양수 비율(%)": _fmt_pct(s.get("non_buy_positive_rate")),
                                    "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                    "미매수 평균 초과수익률(%)": _fmt_pct(
                                        s.get("non_buy_excess_avg")
                                    ),
                                }
                                for s in _summary_action_rows
                            ]
                            st.dataframe(
                                pd.DataFrame(_summary_table_rows),
                                width="stretch",
                                hide_index=True,
                            )

                # 테마별 누적 통계. 위 "전체 행동별 누적 통계 보기"와 마찬가지로 현재 선택한
                # report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된
                # 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
                # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
                # 없음. 테마/실제 행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는
                # 화면 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다.
                with st.expander("테마별 누적 통계 보기", expanded=False):
                    st.caption(
                        "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                        "여러 보고서의 저장된 성과를 함께 집계합니다."
                    )
                    st.caption(
                        "한 종목에 여러 테마 태그가 있으면 각 테마에 각각 포함됩니다. 표본수가 "
                        "적으면 결과가 크게 흔들릴 수 있으며, 현재 표는 자동 판정이 아닌 누적 "
                        "원자료 통계입니다."
                    )

                    _theme_filter_cols = st.columns(3)
                    _theme_market_in = _theme_filter_cols[0].selectbox(
                        "시장",
                        ["전체", "KR", "US", "OTHER"],
                        key="theme_summary_market_filter",
                    )
                    _theme_date_from_in = _theme_filter_cols[1].text_input(
                        "시작일",
                        value="",
                        key="theme_summary_date_from_filter",
                        placeholder="2026-07-01",
                    )
                    _theme_date_to_in = _theme_filter_cols[2].text_input(
                        "종료일",
                        value="",
                        key="theme_summary_date_to_filter",
                        placeholder="2026-07-31",
                    )

                    _theme_market_filter = (
                        None if _theme_market_in == "전체" else _theme_market_in
                    )
                    _theme_date_from_filter = _theme_date_from_in.strip() or None
                    _theme_date_to_filter = _theme_date_to_in.strip() or None

                    try:
                        _theme_outcome_rows = db.get_all_report_outcomes(
                            market=_theme_market_filter,
                            date_from=_theme_date_from_filter,
                            date_to=_theme_date_to_filter,
                        )
                    except ValueError as _theme_query_err:
                        st.error(f"조회 조건 오류: {_theme_query_err}")
                    else:
                        _theme_residual_rows = performance.build_decision_residual_rows(
                            _theme_outcome_rows
                        )
                        _theme_summary_rows = performance.build_theme_residual_summary(
                            _theme_residual_rows
                        )
                        if not _theme_summary_rows:
                            st.info("아직 테마별 누적 통계를 계산할 저장 성과가 없습니다.")
                        else:
                            _theme_tag_options_seen = []
                            for _t in _theme_summary_rows:
                                if _t["theme_tag"] not in _theme_tag_options_seen:
                                    _theme_tag_options_seen.append(_t["theme_tag"])

                            _theme_display_cols = st.columns(3)
                            _theme_tag_in = _theme_display_cols[0].selectbox(
                                "테마",
                                ["전체"] + _theme_tag_options_seen,
                                key="theme_summary_theme_filter",
                            )
                            _theme_action_in = _theme_display_cols[1].selectbox(
                                "실제 행동",
                                ["전체", "매수", "보류", "제외", "미기록"],
                                key="theme_summary_action_filter",
                            )
                            _theme_horizon_in = _theme_display_cols[2].selectbox(
                                "거래일수",
                                ["전체", 1, 3, 5, 10, 20],
                                key="theme_summary_horizon_filter",
                            )

                            _theme_filtered_rows = _theme_summary_rows
                            if _theme_tag_in != "전체":
                                _theme_filtered_rows = [
                                    s for s in _theme_filtered_rows
                                    if s["theme_tag"] == _theme_tag_in
                                ]
                            if _theme_action_in != "전체":
                                _theme_filtered_rows = [
                                    s for s in _theme_filtered_rows
                                    if s["actual_action"] == _theme_action_in
                                ]
                            if _theme_horizon_in != "전체":
                                _theme_filtered_rows = [
                                    s for s in _theme_filtered_rows
                                    if s["horizon_sessions"] == _theme_horizon_in
                                ]

                            if not _theme_filtered_rows:
                                st.info("아직 테마별 누적 통계를 계산할 저장 성과가 없습니다.")
                            else:
                                _theme_table_rows = [
                                    {
                                        "테마": s.get("theme_tag"),
                                        "거래일수": s.get("horizon_sessions"),
                                        "실제 행동": s.get("actual_action"),
                                        "전체 표본수": s.get("sample_count"),
                                        "판단 수익률 표본수": s.get("judgment_return_count"),
                                        "판단 평균 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_avg")
                                        ),
                                        "판단 중앙 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_median")
                                        ),
                                        "판단 양수 개수": s.get("judgment_positive_count"),
                                        "판단 양수 비율(%)": _fmt_pct(
                                            s.get("judgment_positive_rate")
                                        ),
                                        "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                        "판단 평균 초과수익률(%)": _fmt_pct(
                                            s.get("judgment_excess_avg")
                                        ),
                                        "진입 효과 표본수": s.get("entry_effect_count"),
                                        "평균 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_avg")
                                        ),
                                        "중앙 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_median")
                                        ),
                                        "미매수 표본수": s.get("non_buy_return_count"),
                                        "미매수 평균 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_avg")
                                        ),
                                        "미매수 중앙 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_median")
                                        ),
                                        "미매수 양수 개수": s.get("non_buy_positive_count"),
                                        "미매수 양수 비율(%)": _fmt_pct(
                                            s.get("non_buy_positive_rate")
                                        ),
                                        "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                        "미매수 평균 초과수익률(%)": _fmt_pct(
                                            s.get("non_buy_excess_avg")
                                        ),
                                    }
                                    for s in _theme_filtered_rows
                                ]
                                st.dataframe(
                                    pd.DataFrame(_theme_table_rows),
                                    width="stretch",
                                    hide_index=True,
                                )

                # 판단 맥락별 누적 통계. 위 두 통계(행동별/테마별)와 마찬가지로 현재 선택한
                # report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된
                # 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
                # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
                # 없음. 맥락값/실제 행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는
                # 화면 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다. 분석 기준은 한 번에
                # 하나만 선택한다(복합 조건 분석 아님). 내부 group_by 코드(trade_mode 등)는
                # 화면에 노출하지 않고 선택된 한글 분석 기준 이름만 표시한다.
                with st.expander("판단 맥락별 누적 통계 보기", expanded=False):
                    st.caption(
                        "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                        "여러 보고서의 저장된 성과를 함께 집계합니다."
                    )
                    st.caption(
                        "각 분석 기준을 한 번에 하나씩 분리해 집계한 원자료 통계입니다. "
                        "표본수가 적으면 결과가 크게 흔들릴 수 있습니다."
                    )

                    _context_filter_cols = st.columns(3)
                    _context_market_in = _context_filter_cols[0].selectbox(
                        "시장",
                        ["전체", "KR", "US", "OTHER"],
                        key="context_summary_market_filter",
                    )
                    _context_date_from_in = _context_filter_cols[1].text_input(
                        "시작일",
                        value="",
                        key="context_summary_date_from_filter",
                        placeholder="2026-07-01",
                    )
                    _context_date_to_in = _context_filter_cols[2].text_input(
                        "종료일",
                        value="",
                        key="context_summary_date_to_filter",
                        placeholder="2026-07-31",
                    )

                    _context_basis_options = {
                        "매매유형": "trade_mode",
                        "당시 판정": "verdict",
                        "신호 분류": "signal_type",
                        "이벤트": "event_name",
                        "브리핑 단계": "briefing_stage",
                        "시점 구분": "timing_class",
                    }
                    _context_basis_label_in = st.selectbox(
                        "분석 기준",
                        list(_context_basis_options.keys()),
                        key="context_summary_basis_filter",
                    )
                    _context_group_by = _context_basis_options[_context_basis_label_in]

                    _context_market_filter = (
                        None if _context_market_in == "전체" else _context_market_in
                    )
                    _context_date_from_filter = _context_date_from_in.strip() or None
                    _context_date_to_filter = _context_date_to_in.strip() or None

                    try:
                        _context_outcome_rows = db.get_all_report_outcomes(
                            market=_context_market_filter,
                            date_from=_context_date_from_filter,
                            date_to=_context_date_to_filter,
                        )
                    except ValueError as _context_query_err:
                        st.error(f"조회 조건 오류: {_context_query_err}")
                    else:
                        _context_residual_rows = performance.build_decision_residual_rows(
                            _context_outcome_rows
                        )
                        _context_summary_rows = performance.build_context_residual_summary(
                            _context_residual_rows, _context_group_by
                        )
                        if not _context_summary_rows:
                            st.info(
                                "아직 판단 맥락별 누적 통계를 계산할 저장 성과가 없습니다."
                            )
                        else:
                            _context_value_options_seen = []
                            for _c in _context_summary_rows:
                                if _c["context_value"] not in _context_value_options_seen:
                                    _context_value_options_seen.append(_c["context_value"])

                            _context_display_cols = st.columns(3)
                            _context_value_in = _context_display_cols[0].selectbox(
                                "맥락값",
                                ["전체"] + _context_value_options_seen,
                                key="context_summary_value_filter",
                            )
                            _context_action_in = _context_display_cols[1].selectbox(
                                "실제 행동",
                                ["전체", "매수", "보류", "제외", "미기록"],
                                key="context_summary_action_filter",
                            )
                            _context_horizon_in = _context_display_cols[2].selectbox(
                                "거래일수",
                                ["전체", 1, 3, 5, 10, 20],
                                key="context_summary_horizon_filter",
                            )

                            _context_filtered_rows = _context_summary_rows
                            if _context_value_in != "전체":
                                _context_filtered_rows = [
                                    s for s in _context_filtered_rows
                                    if s["context_value"] == _context_value_in
                                ]
                            if _context_action_in != "전체":
                                _context_filtered_rows = [
                                    s for s in _context_filtered_rows
                                    if s["actual_action"] == _context_action_in
                                ]
                            if _context_horizon_in != "전체":
                                _context_filtered_rows = [
                                    s for s in _context_filtered_rows
                                    if s["horizon_sessions"] == _context_horizon_in
                                ]

                            if not _context_filtered_rows:
                                st.info(
                                    "아직 판단 맥락별 누적 통계를 계산할 저장 성과가 없습니다."
                                )
                            else:
                                _context_table_rows = [
                                    {
                                        "분석 기준": _context_basis_label_in,
                                        "맥락값": s.get("context_value"),
                                        "거래일수": s.get("horizon_sessions"),
                                        "실제 행동": s.get("actual_action"),
                                        "전체 표본수": s.get("sample_count"),
                                        "판단 수익률 표본수": s.get("judgment_return_count"),
                                        "판단 평균 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_avg")
                                        ),
                                        "판단 중앙 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_median")
                                        ),
                                        "판단 양수 개수": s.get("judgment_positive_count"),
                                        "판단 양수 비율(%)": _fmt_pct(
                                            s.get("judgment_positive_rate")
                                        ),
                                        "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                        "판단 평균 초과수익률(%)": _fmt_pct(
                                            s.get("judgment_excess_avg")
                                        ),
                                        "진입 효과 표본수": s.get("entry_effect_count"),
                                        "평균 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_avg")
                                        ),
                                        "중앙 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_median")
                                        ),
                                        "미매수 표본수": s.get("non_buy_return_count"),
                                        "미매수 평균 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_avg")
                                        ),
                                        "미매수 중앙 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_median")
                                        ),
                                        "미매수 양수 개수": s.get("non_buy_positive_count"),
                                        "미매수 양수 비율(%)": _fmt_pct(
                                            s.get("non_buy_positive_rate")
                                        ),
                                        "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                        "미매수 평균 초과수익률(%)": _fmt_pct(
                                            s.get("non_buy_excess_avg")
                                        ),
                                    }
                                    for s in _context_filtered_rows
                                ]
                                st.dataframe(
                                    pd.DataFrame(_context_table_rows),
                                    width="stretch",
                                    hide_index=True,
                                )

                # 두 조건 조합별 누적 통계. 위 세 통계(행동별/테마별/맥락별)와 마찬가지로 현재
                # 선택한 report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의
                # 저장된 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
                # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
                # 없음. 조건값/행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는 화면
                # 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다. 조건은 정확히 2개만 선택
                # 하며(세 조건 이상 조합 아님), 내부 코드명은 화면에 노출하지 않고 선택된 한글
                # 분석 기준 이름만 표시한다.
                with st.expander("두 조건 조합별 누적 통계 보기", expanded=False):
                    st.caption(
                        "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                        "여러 보고서의 저장된 성과를 함께 집계합니다."
                    )
                    st.caption(
                        "두 조건이 동시에 해당한 기록을 집계한 원자료 통계입니다. 한 종목에 "
                        "여러 테마가 있으면 각 테마 조합에 각각 포함되며, 표본수가 적으면 "
                        "결과가 크게 흔들릴 수 있습니다."
                    )

                    _combo_basis_options = {
                        "테마": "theme_tag",
                        "매매유형": "trade_mode",
                        "당시 판정": "verdict",
                        "신호 분류": "signal_type",
                        "이벤트": "event_name",
                        "브리핑 단계": "briefing_stage",
                        "시점 구분": "timing_class",
                    }
                    _combo_basis_label_list = list(_combo_basis_options.keys())

                    _combo_basis_cols = st.columns(2)
                    _combo_basis_1_label = _combo_basis_cols[0].selectbox(
                        "첫 번째 조건",
                        _combo_basis_label_list,
                        index=_combo_basis_label_list.index("테마"),
                        key="combination_summary_basis1_filter",
                    )
                    _combo_basis_2_label = _combo_basis_cols[1].selectbox(
                        "두 번째 조건",
                        _combo_basis_label_list,
                        index=_combo_basis_label_list.index("매매유형"),
                        key="combination_summary_basis2_filter",
                    )
                    _combo_group_by_1 = _combo_basis_options[_combo_basis_1_label]
                    _combo_group_by_2 = _combo_basis_options[_combo_basis_2_label]

                    _combo_filter_cols = st.columns(3)
                    _combo_market_in = _combo_filter_cols[0].selectbox(
                        "시장",
                        ["전체", "KR", "US", "OTHER"],
                        key="combination_summary_market_filter",
                    )
                    _combo_date_from_in = _combo_filter_cols[1].text_input(
                        "시작일",
                        value="",
                        key="combination_summary_date_from_filter",
                        placeholder="2026-07-01",
                    )
                    _combo_date_to_in = _combo_filter_cols[2].text_input(
                        "종료일",
                        value="",
                        key="combination_summary_date_to_filter",
                        placeholder="2026-07-31",
                    )

                    _combo_market_filter = (
                        None if _combo_market_in == "전체" else _combo_market_in
                    )
                    _combo_date_from_filter = _combo_date_from_in.strip() or None
                    _combo_date_to_filter = _combo_date_to_in.strip() or None

                    if _combo_group_by_1 == _combo_group_by_2:
                        st.error("첫 번째 조건과 두 번째 조건은 서로 달라야 합니다.")
                    else:
                        try:
                            _combo_outcome_rows = db.get_all_report_outcomes(
                                market=_combo_market_filter,
                                date_from=_combo_date_from_filter,
                                date_to=_combo_date_to_filter,
                            )
                        except ValueError as _combo_query_err:
                            st.error(f"조회 조건 오류: {_combo_query_err}")
                        else:
                            _combo_residual_rows = performance.build_decision_residual_rows(
                                _combo_outcome_rows
                            )
                            _combo_summary_rows = (
                                performance.build_combination_residual_summary(
                                    _combo_residual_rows,
                                    [_combo_group_by_1, _combo_group_by_2],
                                )
                            )
                            if not _combo_summary_rows:
                                st.info(
                                    "아직 두 조건 조합별 누적 통계를 계산할 저장 성과가 "
                                    "없습니다."
                                )
                            else:
                                _combo_value1_options_seen = []
                                _combo_value2_options_seen = []
                                for _c in _combo_summary_rows:
                                    if _c["context_value_1"] not in _combo_value1_options_seen:
                                        _combo_value1_options_seen.append(
                                            _c["context_value_1"]
                                        )
                                    if _c["context_value_2"] not in _combo_value2_options_seen:
                                        _combo_value2_options_seen.append(
                                            _c["context_value_2"]
                                        )

                                _combo_display_cols = st.columns(4)
                                _combo_value1_in = _combo_display_cols[0].selectbox(
                                    f"{_combo_basis_1_label} 조건값",
                                    ["전체"] + _combo_value1_options_seen,
                                    key="combination_summary_value1_filter",
                                )
                                _combo_value2_in = _combo_display_cols[1].selectbox(
                                    f"{_combo_basis_2_label} 조건값",
                                    ["전체"] + _combo_value2_options_seen,
                                    key="combination_summary_value2_filter",
                                )
                                _combo_action_in = _combo_display_cols[2].selectbox(
                                    "실제 행동",
                                    ["전체", "매수", "보류", "제외", "미기록"],
                                    key="combination_summary_action_filter",
                                )
                                _combo_horizon_in = _combo_display_cols[3].selectbox(
                                    "거래일수",
                                    ["전체", 1, 3, 5, 10, 20],
                                    key="combination_summary_horizon_filter",
                                )

                                _combo_filtered_rows = _combo_summary_rows
                                if _combo_value1_in != "전체":
                                    _combo_filtered_rows = [
                                        s for s in _combo_filtered_rows
                                        if s["context_value_1"] == _combo_value1_in
                                    ]
                                if _combo_value2_in != "전체":
                                    _combo_filtered_rows = [
                                        s for s in _combo_filtered_rows
                                        if s["context_value_2"] == _combo_value2_in
                                    ]
                                if _combo_action_in != "전체":
                                    _combo_filtered_rows = [
                                        s for s in _combo_filtered_rows
                                        if s["actual_action"] == _combo_action_in
                                    ]
                                if _combo_horizon_in != "전체":
                                    _combo_filtered_rows = [
                                        s for s in _combo_filtered_rows
                                        if s["horizon_sessions"] == _combo_horizon_in
                                    ]

                                if not _combo_filtered_rows:
                                    st.info(
                                        "아직 두 조건 조합별 누적 통계를 계산할 저장 성과가 "
                                        "없습니다."
                                    )
                                else:
                                    _combo_table_rows = [
                                        {
                                            "첫 번째 분석 기준": _combo_basis_1_label,
                                            "첫 번째 조건값": s.get("context_value_1"),
                                            "두 번째 분석 기준": _combo_basis_2_label,
                                            "두 번째 조건값": s.get("context_value_2"),
                                            "거래일수": s.get("horizon_sessions"),
                                            "실제 행동": s.get("actual_action"),
                                            "전체 표본수": s.get("sample_count"),
                                            "판단 수익률 표본수": s.get(
                                                "judgment_return_count"
                                            ),
                                            "판단 평균 수익률(%)": _fmt_pct(
                                                s.get("judgment_return_avg")
                                            ),
                                            "판단 중앙 수익률(%)": _fmt_pct(
                                                s.get("judgment_return_median")
                                            ),
                                            "판단 양수 개수": s.get(
                                                "judgment_positive_count"
                                            ),
                                            "판단 양수 비율(%)": _fmt_pct(
                                                s.get("judgment_positive_rate")
                                            ),
                                            "판단 초과수익률 표본수": s.get(
                                                "judgment_excess_count"
                                            ),
                                            "판단 평균 초과수익률(%)": _fmt_pct(
                                                s.get("judgment_excess_avg")
                                            ),
                                            "진입 효과 표본수": s.get("entry_effect_count"),
                                            "평균 진입 효과(%p)": _fmt_pct(
                                                s.get("entry_effect_avg")
                                            ),
                                            "중앙 진입 효과(%p)": _fmt_pct(
                                                s.get("entry_effect_median")
                                            ),
                                            "미매수 표본수": s.get("non_buy_return_count"),
                                            "미매수 평균 수익률(%)": _fmt_pct(
                                                s.get("non_buy_return_avg")
                                            ),
                                            "미매수 중앙 수익률(%)": _fmt_pct(
                                                s.get("non_buy_return_median")
                                            ),
                                            "미매수 양수 개수": s.get(
                                                "non_buy_positive_count"
                                            ),
                                            "미매수 양수 비율(%)": _fmt_pct(
                                                s.get("non_buy_positive_rate")
                                            ),
                                            "미매수 초과수익률 표본수": s.get(
                                                "non_buy_excess_count"
                                            ),
                                            "미매수 평균 초과수익률(%)": _fmt_pct(
                                                s.get("non_buy_excess_avg")
                                            ),
                                        }
                                        for s in _combo_filtered_rows
                                    ]
                                    st.dataframe(
                                        pd.DataFrame(_combo_table_rows),
                                        width="stretch",
                                        hide_index=True,
                                    )
                st.markdown("---")

            # 필터 영역 (매매유형/판정 기본값은 항상 "전체")
            fcol1, fcol2 = st.columns(2)
            trade_mode_filter = fcol1.radio(
                "단기/며칠 구분",
                ["전체", "단타", "스윙", "공통"],
                horizontal=True,
                key="perf_trade_mode_filter",
            )
            verdict_filter_display = fcol2.radio(
                "판단 구분",
                ["전체", "1순위 후보", "관찰 후보", "재확인", "보류", "제외"],
                horizontal=True,
                key="perf_verdict_filter",
            )

            perf_rows = scoped_rows
            if trade_mode_filter != "전체":
                perf_rows = [row for row in perf_rows if row["trade_mode"] == trade_mode_filter]
            if verdict_filter_display != "전체":
                internal_verdict = REVERSE_VERDICT_DISPLAY[verdict_filter_display]
                perf_rows = [row for row in perf_rows if row["verdict"] == internal_verdict]

            if not perf_rows:
                st.info("이 조건에 해당하는 종목별 기록이 없습니다.")
            else:
                # 후보 점수 계산: 저장된 문장에서 숫자 근거를 뽑아 판정 기본점수에 가감한다.
                item_text_lookup = _build_item_text_lookup()
                scored_rows = []
                for row in perf_rows:
                    key = (row["report_id"], row["ticker"], row["trade_mode"])
                    basis_text = " ".join(item_text_lookup.get(key, []))
                    basis = extract_score_basis_from_text(basis_text)
                    candidate_score = compute_candidate_score(row["verdict"], row["trade_mode"], basis)
                    scored_rows.append((candidate_score, row))

                # 후보 점수 기준 내림차순 정렬 (동점은 입력 순서 유지 — sorted()는 안정 정렬)
                scored_rows = sorted(scored_rows, key=lambda pair: -pair[0])

                # score(저장된 판단 설명 점수) 기준 순위: 같은 report·시장·매매유형 안에서만 비교한다.
                item_judgment_lookup = _build_item_judgment_lookup()
                score_rank_labels = _compute_score_rank_labels(item_judgment_lookup.values())

                # 4. compact 요약 (큰 숫자 4개만)
                status_counts = {
                    "계산 완료": sum(1 for row in perf_rows if row["status"] == "계산 완료"),
                    "대기": sum(1 for row in perf_rows if row["status"] == "대기"),
                    "데이터 부족": sum(1 for row in perf_rows if row["status"] == "데이터 부족"),
                }
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("지금 보이는 종목", len(perf_rows))
                m2.metric("결과 기다리는 중", status_counts["대기"])
                m3.metric("결과 확인 완료", status_counts["계산 완료"])
                m4.metric("가격 데이터 부족", status_counts["데이터 부족"])
                st.caption("현재 필터 기준으로 표시되는 종목 수입니다.")

                # 판정별 개수는 작은 배지 텍스트로만 표시 (큰 숫자 아님)
                verdict_counts = {
                    v: sum(1 for row in perf_rows if row["verdict"] == v) for v in VERDICT_ORDER
                }
                badge_line = "  ".join(
                    f"{_verdict_badge(v)} {verdict_counts[v]}건" for v in VERDICT_ORDER
                )
                st.markdown(badge_line)

                if st.button("수익률 다시 확인", key="perf_refresh"):
                    _cached_verification_rows.clear()
                    _cached_no_recommendation_rows.clear()
                    st.rerun()
                st.caption("저장된 종목의 1일·3일·5일·10일·20일 수익률을 다시 확인합니다.")

                # 4-1. 필터 준수 vs 필터 무시 R 비교 카드 (report_items 전체 기준, 화면 표시 전용)
                st.markdown("#### 필터 준수 vs 필터 무시 R 비교")
                st.caption("이 통계는 매수 추천이 아니라 행동 검증용입니다.")
                _fi_stats = _fetch_filter_compliance_stats()
                fc1, fc2, fc3 = st.columns(3)
                fc1.metric("필터 무시 기록 수", _fi_stats["ignored_count"])
                fc2.metric("필터 준수 기록 수", _fi_stats["followed_count"])
                fc3.metric("필터 미입력 수", _fi_stats["unset_count"])
                fc4, fc5, fc6 = st.columns(3)
                fc4.metric("필터 무시 평균 R", _fmt_avg_r(_fi_stats["ignored_avg_r"]))
                fc5.metric("필터 준수 평균 R", _fmt_avg_r(_fi_stats["followed_avg_r"]))
                fc6.metric(
                    "비교 가능 R 데이터 수",
                    f"{_fi_stats['comparable_n']}건" if _fi_stats["comparable_n"] else "0건",
                )
                if _fi_stats["comparable_n"] == 0:
                    st.info(
                        "아직 필터 준수/무시와 청산 R 데이터가 부족합니다. "
                        "필터 무시 기록과 청산 결과가 쌓이면 비교됩니다."
                    )
                elif _fi_stats["comparable_n"] < 30:
                    st.caption(f"표본 N<30: 미검증 구간입니다. ({_n_confidence_label(_fi_stats['comparable_n'])})")
                else:
                    st.caption(
                        f"표본 N={_fi_stats['comparable_n']}: {_n_confidence_label(_fi_stats['comparable_n'])} 구간입니다."
                    )

                # 4-2. 최악 5매매 R 점검 카드 (report_items 전체 기준, 화면 표시 전용)
                st.markdown("#### 최악 5매매 R 점검")
                st.caption("이 카드는 매수 추천이 아니라 손실 원인 점검용입니다.")
                _worst_stats = _fetch_worst_trades(limit=5)
                if _worst_stats["total_n"] == 0:
                    st.info("아직 청산 R 데이터가 없습니다. 청산 결과가 쌓이면 최악 5개 매매가 표시됩니다.")
                else:
                    wc1, wc2, wc3, wc4 = st.columns(4)
                    wc1.metric("R 데이터 개수", _worst_stats["total_n"])
                    wc2.metric("최악 5개 평균 R", _fmt_avg_r(_worst_stats["avg_worst"]))
                    wc3.metric("최저 R", _fmt_avg_r(_worst_stats["lowest"]))
                    wc4.metric("검증 상태", _n_confidence_label(_worst_stats["total_n"]))
                    if _worst_stats["total_n"] < 30:
                        st.caption(f"표본 N<30: {_n_confidence_label(_worst_stats['total_n'])} 구간입니다.")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "종목명": d["종목명"],
                                    "티커": d["티커"],
                                    "매매유형": d["매매유형"],
                                    "result_r": _fmt_avg_r(d["result_r"]),
                                    "청산일": d["청산일"],
                                    "청산사유": d["청산사유"],
                                    "필터무시여부": d["필터무시여부"],
                                }
                                for d in _worst_stats["worst_rows"]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )

                # 4-3. 총 오픈 리스크 3R 점검 카드 (report_items 전체 기준, 화면 표시 전용)
                st.markdown("#### 총 오픈 리스크 3R 점검")
                st.caption("이 카드는 매수 추천이 아니라 여러 포지션의 손실 노출을 점검하는 장치입니다.")
                _open_risk = _fetch_open_risk_positions()
                if _open_risk["needs_account_setting"]:
                    st.info(
                        "총 오픈 리스크를 R 단위로 계산하려면 먼저 한국장 탭의 '계좌금액'과 "
                        "'1회 리스크(%)'를 설정해야 합니다(한국장·미국장 공통 설정)."
                    )
                else:
                    oc1, oc2, oc3, oc4 = st.columns(4)
                    oc1.metric("계산 가능한 오픈 포지션 수", _open_risk["count"])
                    oc2.metric("총 오픈 리스크", f"{_open_risk['total_risk']:.2f}R")
                    oc3.metric("3R 기준 상태", _open_risk_status_label(_open_risk["count"], _open_risk["total_risk"]))
                    oc4.metric("계산 제외 항목 수", _open_risk["excluded_count"])
                    if _open_risk["count"] == 0:
                        st.info(
                            "아직 실제 매수해서 진입가·손절가·수량이 모두 입력된 미청산 항목이 없습니다. "
                            "③ 행동·청산에서 매수를 기록하면 총 오픈 리스크가 계산됩니다."
                        )
                    else:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "종목명": p["종목명"],
                                        "티커": p["티커"],
                                        "매매유형": p["매매유형"],
                                        "진입가": f"{p['진입가']:,.0f}",
                                        "손절가": f"{p['손절가']:,.0f}",
                                        "수량": f"{p['수량']:,.0f}",
                                        "1건 위험": f"{p['1건 위험']:.2f}R",
                                        "필터무시여부": p["필터무시여부"],
                                    }
                                    for p in _open_risk["positions"]
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )

                # 5. 관심 점수 설명
                st.info(
                    "관심 점수는 실제 상승확률이 아닙니다. 오늘 주가 위치, 고점 대비 밀림, 거래대금, "
                    "섹터 흐름을 기준으로 관심 순서를 비교한 점수입니다. 100점은 반드시 오른다는 "
                    "뜻이 아닙니다. 조건표상 거의 완벽한 경우에만 나오는 높은 관심 점수입니다. "
                    "일반적인 1순위 후보는 80~90점대가 정상입니다."
                )

                # 6. 결과 표 (기본 컬럼만, 관심 점수 높은 순 정렬) — 화면 표시는 한국장/미국장으로 나눠서 보여준다.
                table_rows = []
                for score, row in scored_rows:
                    saved_item = item_judgment_lookup.get(
                        (row["report_id"], row["ticker"], row["trade_mode"]), {}
                    )
                    table_rows.append(
                        {
                            "종목명": row["stock_name"],
                            "티커": row["ticker"],
                            "시장": row["market"],
                            "매매유형": row["trade_mode"],
                            "순위": score_rank_labels.get(saved_item.get("id"), "미평가"),
                            "관심 점수": score,
                            "판단": _display_verdict_name(row["verdict"]),
                            "결과 상태": row["status"],
                            "판단 시점": row["briefing_stage"],
                            "1일 뒤": _fmt_pct(row["returns"][1]),
                            "3일 뒤": _fmt_pct(row["returns"][3]),
                            "5일 뒤": _fmt_pct(row["returns"][5]),
                            "10일 뒤": _fmt_pct(row["returns"][10]),
                            "20일 뒤": _fmt_pct(row["returns"][20]),
                            "실제 청산가": (
                                f"{saved_item['actual_exit_price']:,.0f}"
                                if saved_item.get("actual_exit_price") else "-"
                            ),
                            "청산일": saved_item.get("actual_exit_date") or "-",
                            "계획 준수": saved_item.get("plan_followed") or "-",
                            "청산 사유": saved_item.get("exit_reason") or "-",
                            "R수익률": _fmt_result_r(saved_item.get("result_r")),
                            "검증 상태": saved_item.get("verification_status") or "미입력",
                        }
                    )
                perf_df = pd.DataFrame(table_rows)

                kr_table_rows = [r for r in table_rows if r["시장"] == "KR"]
                us_table_rows = [r for r in table_rows if r["시장"] == "US"]

                st.markdown("#### 한국장 저장 결과")
                if kr_table_rows:
                    st.dataframe(pd.DataFrame(kr_table_rows), width="stretch", hide_index=True)
                else:
                    st.info("한국장 저장 기록 없음")

                st.markdown("#### 미국장 저장 결과")
                if us_table_rows:
                    st.dataframe(pd.DataFrame(us_table_rows), width="stretch", hide_index=True)
                else:
                    st.info("미국장 저장 기록 없음")

                # 7. 엑셀용 파일 내보내기 (기본 표와 동일한 컬럼)
                st.download_button(
                    "결과 표 엑셀로 저장",
                    data=perf_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="결과확인.csv",
                    mime="text/csv",
                    key="perf_csv_download",
                )

                # 8. 자세히 보기 (숨긴 컬럼 포함 전체)
                with st.expander("자세히 보기"):
                    detail_table_rows = []
                    for score, row in scored_rows:
                        saved_item = item_judgment_lookup.get(
                            (row["report_id"], row["ticker"], row["trade_mode"]), {}
                        )
                        if saved_item:
                            auto_info = _auto_fill_item_display(saved_item)
                            score_text = f"{auto_info['score']:.0f}" + (" (자동계산)" if auto_info["score_is_auto"] else "")
                            top_reason = saved_item.get("top_candidate_reason") or auto_info["score_reason"]
                        else:
                            auto_info = {"score_reason": "-", "penalty_reason": "-", "buy_confirmed": "-", "buy_confirm_condition": "-"}
                            score_text = "-"
                            top_reason = "-"
                        detail_table_rows.append(
                            {
                                "종목명": row["stock_name"],
                                "순위": score_rank_labels.get(saved_item.get("id"), "미평가"),
                                "관심 점수": score,
                                "구분": row["trade_mode"],
                                "판단": _display_verdict_name(row["verdict"]),
                                "결과 상태": row["status"],
                                "판단 시점": row["briefing_stage"],
                                "저장 시각": row["saved_at"],
                                "신호 종류": _display_signal_type(row["signal_type"]),
                                "종목코드": row["ticker"],
                                "시장": row["market"],
                                "비교 기준": row["benchmark"],
                                "검증 시작가": row["entry_rule"],
                                "1일 뒤": _fmt_pct(row["returns"][1]),
                                "3일 뒤": _fmt_pct(row["returns"][3]),
                                "5일 뒤": _fmt_pct(row["returns"][5]),
                                "10일 뒤": _fmt_pct(row["returns"][10]),
                                "20일 뒤": _fmt_pct(row["returns"][20]),
                                "초과수익률(%, 5일 기준)": _fmt_pct(row["excess_return"]),
                                "판단 근거": saved_item.get("stock_market_judgment") or "-",
                                "점수": score_text,
                                "점수 근거": auto_info["score_reason"],
                                "1순위 후보 근거": top_reason,
                                "감점 이유": auto_info["penalty_reason"],
                                "매수 확정 여부": auto_info["buy_confirmed"],
                                "매수 확정 조건": auto_info["buy_confirm_condition"],
                            }
                        )

                    st.dataframe(pd.DataFrame(detail_table_rows), width="stretch", hide_index=True)

        st.markdown("---")
        with st.expander("오늘 관심 종목 없음 평가", expanded=False):
            st.caption(
                "종목 항목이 0개인 기록(오늘 추천 없음)에 대해, 그날 이후 기준지수가 올랐으면 "
                "기회비용, 내렸으면 위험회피 성공으로 표시합니다. 지수 상승만으로 실패 처리하지 않습니다."
            )

            no_rec_rows = (
                _cached_no_recommendation_rows(_reports_signature())
                if _perf_performance_ready
                else []
            )

            if not no_rec_rows:
                st.info("종목 항목이 0개인 기록이 없습니다.")
            else:
                no_rec_status_counts = {
                    "계산 완료": sum(1 for row in no_rec_rows if row["status"] == "계산 완료"),
                    "대기": sum(1 for row in no_rec_rows if row["status"] == "대기"),
                    "데이터 부족": sum(1 for row in no_rec_rows if row["status"] == "데이터 부족"),
                }
                n1, n2, n3, n4 = st.columns(4)
                n1.metric("전체 대상 수", len(no_rec_rows))
                n2.metric("결과 확인 완료", no_rec_status_counts["계산 완료"])
                n3.metric("결과 기다리는 중", no_rec_status_counts["대기"])
                n4.metric("가격 데이터 부족", no_rec_status_counts["데이터 부족"])

                no_rec_table_rows = [
                    {
                        "결과 상태": row["status"],
                        "저장 시각": row["saved_at"],
                        "오늘 요약": row["day_conclusion"],
                        "시장 구분": row["market_label"],
                        "비교 기준": row["benchmark"],
                        "검증 시작가": row["entry_rule"],
                        "1일 뒤": _fmt_pct(row["returns"][1]),
                        "3일 뒤": _fmt_pct(row["returns"][3]),
                        "5일 뒤": _fmt_pct(row["returns"][5]),
                        "10일 뒤": _fmt_pct(row["returns"][10]),
                        "20일 뒤": _fmt_pct(row["returns"][20]),
                        "판단(5일 기준)": row["judgment_5d"],
                    }
                    for row in no_rec_rows
                ]
                no_rec_df = pd.DataFrame(no_rec_table_rows)
                st.dataframe(no_rec_df, width="stretch", hide_index=True)
                st.download_button(
                    "결과 표 엑셀로 저장 (오늘 관심 종목 없음 평가)",
                    data=no_rec_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="관심종목없음평가.csv",
                    mime="text/csv",
                    key="no_rec_csv_download",
                )

if _aux_view == "추가 기능":
    with tab_aux:
        st.subheader("추가 기능")
        st.markdown(
            """
    - 결과 확인 통계/요약 (추후 별도 논의)
    - 지난 기록 보기 필터/검색 고도화 (추후 별도 논의)
    """
        )

        st.markdown("---")
        st.markdown("#### 리스크 관리 공통 설정")
        _daily_threshold_current = db.get_daily_entry_warning_threshold()
        _daily_threshold_in = st.number_input(
            "하루 신규 진입 경고 기준(건)",
            min_value=1,
            step=1,
            value=_daily_threshold_current,
            key="daily_entry_warning_threshold_input",
            help="이 건수를 초과해 오늘 신규 매수하면 참고용 경고만 표시합니다(차단 없음).",
        )
        if st.button("경고 기준 저장", key="daily_entry_warning_threshold_save"):
            db.set_daily_entry_warning_threshold(int(_daily_threshold_in))
            st.success(f"하루 신규 진입 경고 기준을 {int(_daily_threshold_in)}건으로 저장했습니다.")
            st.rerun()

if _aux_view == "사용법":
    with tab_aux:
        st.subheader("자비스 사용법")
        st.caption("이 화면은 자비스_사용법.md 파일을 앱 안에서 보여주는 화면입니다.")
        try:
            _guide_path = Path(__file__).parent / "자비스_사용법.md"
            _guide_text = _guide_path.read_text(encoding="utf-8")
            st.markdown(_guide_text)
        except FileNotFoundError:
            st.warning("자비스_사용법.md 파일을 찾을 수 없습니다.")
        except Exception as e:
            st.warning(f"사용법 파일을 불러오지 못했습니다: {e}")

# 성공 오버레이는 본문이 모두 렌더링된 뒤 pending 값을 한 번만 꺼내 표시한다.
# CSS만으로 2초 뒤 숨기므로 앱 실행을 막는 sleep/JavaScript 타이머가 없다.
if _login_transition_pending and not _login_transition_rendered_early:
    st.session_state.pop("login_transition_pending", None)
    st.markdown(
        """
        <style>
        .jarvis-login-transition {
            position: fixed !important;
            inset: 0;
            z-index: 2147483647 !important;
            display: block;
            overflow: hidden;
            pointer-events: none;
            isolation: isolate;
            opacity: 1;
            visibility: visible;
            background: radial-gradient(circle at center, #071b3a 0, #020713 46%, #000207 100%);
            animation-name: jarvis-transition-overlay;
            animation-duration: 2s;
            animation-timing-function: linear;
            animation-fill-mode: forwards;
        }
        .jarvis-transition-earth {
            position: absolute;
            z-index: 2;
            left: 50%;
            top: 50%;
            width: min(58vw, 620px);
            transform: translate(-92%, -50%) scale(.82);
            animation-name: jarvis-transition-earth-zoom;
            animation-duration: 2s;
            animation-timing-function: cubic-bezier(.58, 0, .88, .72);
            animation-fill-mode: forwards;
            will-change: transform;
        }
        .jarvis-transition-earth .jarvis-earth-visual {
            position: relative;
            width: 100%;
            aspect-ratio: 1;
            isolation: isolate;
        }
        .jarvis-transition-earth .jarvis-earth-disc {
            position: absolute;
            inset: 7.5%;
            z-index: 2;
            overflow: hidden;
            border-radius: 50%;
            background: #01040a;
            box-shadow: 0 0 0 2px rgba(75, 181, 255, .84), 0 0 24px rgba(35, 139, 255, .34);
        }
        .jarvis-transition-earth .jarvis-earth-image {
            position: absolute;
            inset: -5%;
            display: block;
            width: 110%;
            max-width: none;
            height: 110%;
            object-fit: cover;
            opacity: 1;
            animation-name: jarvis-earth-turn;
            animation-duration: 28s;
            animation-timing-function: ease-in-out;
            animation-iteration-count: infinite;
            animation-direction: alternate;
            animation-fill-mode: both;
        }
        .jarvis-transition-earth .jarvis-orbit {
            position: absolute;
            z-index: 1;
            left: -2%;
            top: 35%;
            width: 104%;
            height: 29%;
            border: 2px solid rgba(58, 155, 255, .72);
            border-radius: 50%;
            transform: rotate(-13deg);
            animation-name: jarvis-transition-ring-charge;
            animation-duration: 2s;
            animation-timing-function: ease-out;
            animation-fill-mode: forwards;
        }
        .jarvis-transition-earth .jarvis-orbit-secondary {
            top: 37%;
            height: 25%;
            border-width: 1px;
            transform: rotate(58deg);
            animation-name: jarvis-transition-ring-charge-soft;
        }
        .jarvis-transition-panel-echo {
            position: absolute;
            z-index: 4;
            right: clamp(2rem, 8vw, 9rem);
            top: 50%;
            width: min(34vw, 460px);
            padding: 2rem;
            transform: translateY(-50%);
            border: 1px solid rgba(85, 151, 236, .32);
            border-radius: 22px;
            color: #dcecff;
            background: linear-gradient(145deg, rgba(15, 31, 56, .82), rgba(3, 10, 24, .92));
            box-shadow: 0 24px 70px rgba(0, 0, 0, .45), inset 0 1px rgba(179, 220, 255, .1);
            animation-name: jarvis-transition-panel-fade;
            animation-duration: 2s;
            animation-timing-function: ease-out;
            animation-fill-mode: forwards;
        }
        .jarvis-transition-panel-kicker {
            color: #64b7ff;
            font: 700 .7rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .2em;
        }
        .jarvis-transition-panel-title { margin-top: .8rem; font-size: 1.8rem; font-weight: 800; }
        .jarvis-transition-panel-line {
            height: 46px;
            margin-top: 1.4rem;
            border: 1px solid rgba(92, 157, 234, .28);
            border-radius: 11px;
            background: rgba(2, 9, 22, .66);
        }
        .jarvis-transition-status {
            position: absolute;
            z-index: 6;
            top: 50%;
            left: 50%;
            width: min(92vw, 680px);
            transform: translate(-50%, -50%);
            color: #eaf6ff;
            text-align: center;
            text-shadow: 0 0 12px #00152f, 0 0 24px rgba(74, 174, 255, .95);
            opacity: 0;
            animation-name: jarvis-transition-status-show;
            animation-duration: 2s;
            animation-timing-function: linear;
            animation-fill-mode: forwards;
        }
        .jarvis-transition-access,
        .jarvis-transition-online,
        .jarvis-transition-complete { opacity: 1; }
        .jarvis-transition-access {
            font: 800 clamp(1.15rem, 3vw, 1.85rem)/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .2em;
        }
        .jarvis-transition-online {
            margin-top: .38rem;
            color: #69bfff;
            font: 700 clamp(.78rem, 2vw, 1rem)/1.35 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .24em;
        }
        .jarvis-transition-complete {
            margin-top: .28rem;
            color: #b9cce0;
            font-size: clamp(.72rem, 1.8vw, .9rem);
            letter-spacing: .12em;
        }
        .jarvis-transition-light {
            position: absolute;
            z-index: 3;
            left: 50%;
            top: 50%;
            width: 9vmin;
            aspect-ratio: 1;
            border: 2px solid rgba(82, 176, 255, .92);
            border-radius: 50%;
            opacity: 0;
            transform: translate(-50%, -50%) scale(.1);
            box-shadow: 0 0 34px rgba(36, 137, 255, .9), inset 0 0 30px rgba(31, 129, 255, .62);
            animation-name: jarvis-transition-light-expand;
            animation-duration: 2s;
            animation-timing-function: ease-in;
            animation-fill-mode: forwards;
        }
        @keyframes jarvis-earth-turn {
            from { transform: translate3d(-1.2%, 0, 0) scale(1.035) rotate(-.6deg); }
            to { transform: translate3d(1.2%, 0, 0) scale(1.035) rotate(.6deg); }
        }
        @keyframes jarvis-transition-ring-charge {
            0% { opacity: .45; border-color: rgba(58, 155, 255, .72); box-shadow: 0 0 2px rgba(73, 178, 255, .1); }
            8%, 20% { opacity: 1; border-color: #79ceff; box-shadow: 0 0 15px #2598ff, inset 0 0 12px rgba(37, 152, 255, .5); }
            50%, 100% { opacity: .34; border-color: rgba(58, 155, 255, .58); box-shadow: 0 0 6px rgba(37, 152, 255, .25); }
        }
        @keyframes jarvis-transition-ring-charge-soft {
            0% { opacity: .2; }
            8%, 20% { opacity: .9; border-color: #8ad7ff; box-shadow: 0 0 12px #278fff; }
            50%, 100% { opacity: .18; }
        }
        @keyframes jarvis-transition-panel-fade {
            0% { opacity: 1; transform: translateY(-50%) scale(1); }
            20% { opacity: 0; transform: translateY(-50%) scale(.98); }
            100% { opacity: 0; transform: translateY(-50%) scale(.98); }
        }
        @keyframes jarvis-transition-status-show {
            0%, 19.99% { opacity: 0; transform: translate(-50%, calc(-50% + 6px)); }
            20%, 50% { opacity: 1; transform: translate(-50%, -50%); }
            50.01%, 100% { opacity: 0; transform: translate(-50%, calc(-50% - 5px)); }
        }
        @keyframes jarvis-transition-earth-zoom {
            0% { transform: translate(-92%, -50%) scale(.82); }
            20% { transform: translate(-50%, -50%) scale(.78); }
            50% { transform: translate(-50%, -50%) scale(.84); }
            100% { transform: translate(-50%, -50%) scale(5.8); }
        }
        @keyframes jarvis-transition-light-expand {
            0%, 49.9% { opacity: 0; transform: translate(-50%, -50%) scale(.1); }
            56% { opacity: .88; }
            100% { opacity: 0; transform: translate(-50%, -50%) scale(24); }
        }
        @keyframes jarvis-transition-overlay {
            0%, 84% { opacity: 1; visibility: visible; }
            99.9% { opacity: 0; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }
        @keyframes jarvis-transition-reduced {
            0% { opacity: 1; visibility: visible; }
            99.9% { opacity: 0; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }
        @media (max-width: 768px) {
            .jarvis-transition-earth { width: min(92vw, 500px); transform: translate(-50%, -66%) scale(.72); }
            .jarvis-transition-panel-echo {
                right: 50%;
                top: auto;
                bottom: 7%;
                width: min(84vw, 520px);
                padding: 1.2rem;
                transform: translateX(50%);
            }
            .jarvis-transition-panel-line { height: 38px; margin-top: .8rem; }
            @keyframes jarvis-transition-panel-fade {
                0% { opacity: 1; transform: translateX(50%) scale(1); }
                20%, 100% { opacity: 0; transform: translateX(50%) scale(.98); }
            }
            @keyframes jarvis-transition-earth-zoom {
                0% { transform: translate(-50%, -66%) scale(.72); }
                20% { transform: translate(-50%, -50%) scale(.7); }
                50% { transform: translate(-50%, -50%) scale(.76); }
                100% { transform: translate(-50%, -50%) scale(5.8); }
            }
        }
        @media (prefers-reduced-motion: reduce) {
            .jarvis-login-transition {
                animation-name: jarvis-transition-reduced !important;
                animation-duration: .2s !important;
                animation-timing-function: ease-out !important;
                animation-fill-mode: forwards !important;
            }
            .jarvis-transition-earth,
            .jarvis-transition-earth *,
            .jarvis-transition-panel-echo,
            .jarvis-transition-status,
            .jarvis-transition-status *,
            .jarvis-transition-light { animation: none !important; }
        }
        </style>
        <div class="jarvis-login-transition" aria-hidden="true">
            <div class="jarvis-transition-earth">
        """ + _jarvis_earth_markup + """
            </div>
            <div class="jarvis-transition-panel-echo">
                <div class="jarvis-transition-panel-kicker">SECURE MARKET INTELLIGENCE</div>
                <div class="jarvis-transition-panel-title">Stock Event Jarvis</div>
                <div class="jarvis-transition-panel-line"></div>
            </div>
            <div class="jarvis-transition-light"></div>
            <div class="jarvis-transition-status">
                <div class="jarvis-transition-access">ACCESS GRANTED</div>
                <div class="jarvis-transition-online">JARVIS ONLINE</div>
                <div class="jarvis-transition-complete">인증 완료</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
