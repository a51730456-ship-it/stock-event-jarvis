"""자비스6 — 종가 관찰. 장 막판에 조건을 재서 보여주고, 눌러 둔 것을 기록한다.

추천기가 아니다. 막지도 않는다. 경고는 보여주되 클릭은 항상 되고, 무시한 것도
기록한다. 그래야 나중에 '경고 지킨 매매와 무시한 매매 중 뭐가 나았나'를 숫자로
비교할 수 있다(JARVIS_CONTEXT: 필터 준수 vs 무시 손익 차이 증명).

자료는 자비스4·5가 이미 모은 것을 쓴다. 새로 조회하지 않는다.
"""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import auth

_REQUIRED_AUTH_REVISION = 2026072503
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib
    auth = _importlib.reload(auth)

st.set_page_config(page_title="자비스6 — 종가 관찰", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        width: 10rem !important; min-width: 10rem !important; max-width: 10rem !important;
    }
    [data-testid="stSidebarNav"] a, [data-testid="stSidebarNav"] a * {
        font-size: 1.15rem !important; font-weight: 800 !important; color: #ffb020 !important;
    }
    /* 파일명이 그대로 보이지 않게 이름을 덮어쓴다(자비스4와 같은 방식) */
    [data-testid="stSidebarNav"] li:nth-child(1) a p,
    [data-testid="stSidebarNav"] li:nth-child(4) a p,
    [data-testid="stSidebarNav"] li:nth-child(5) a p,
    [data-testid="stSidebarNav"] li:nth-child(6) a p,
    [data-testid="stSidebarNav"] li:nth-child(7) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(1) a p::before { content: "자비스1"; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before { content: "미국테마"; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before { content: "한국테마"; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before { content: "선행감지"; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p::before { content: "종가관찰"; }
    [data-testid="stSidebarNav"] li a p::before {
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    .j6-guide { color: #c8ccd4; font-size: 1rem; line-height: 1.8; font-weight: 600; }
    .j6-guide b { color: #ffffff; font-weight: 800; }
    .j6-kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr));
        gap: .7rem; margin: .8rem 0; }
    .j6-kpi { border: 1px solid rgba(255,255,255,.11); background: rgba(255,255,255,.025);
        border-radius: .6rem; padding: .7rem .9rem; text-align: center; }
    .j6-kpi-label { color: #4da6ff; font-size: .9rem; font-weight: 800; }
    .j6-kpi-value { color: #44f0a1; font-size: 1.5rem; font-weight: 800; }
    .j6-check { color: #44f0a1; font-weight: 800; }
    .j6-cross { color: #ff6b6b; font-weight: 800; }
    .j6-table { width: 100%; border-collapse: collapse; font-size: 1.02rem; }
    .j6-table th { color: #4da6ff; font-weight: 800; text-align: center;
        padding: .6rem .4rem; border-bottom: 2px solid rgba(255,255,255,.2);
        font-size: .95rem; }
    .j6-table td { padding: .62rem .4rem; text-align: center; font-weight: 800;
        color: #e6e6e6; border-bottom: 1px solid rgba(255,255,255,.09); }
    .j6-table td.j6-left { text-align: left; }
    .j6-name { color: #ffffff; font-size: 1.05rem; font-weight: 800; }
    .j6-theme { color: #9aa0aa; font-size: .85rem; font-weight: 700; }
    .j6-sel { background: rgba(77,166,255,.16); }
    .j6-sel td { border-bottom-color: rgba(77,166,255,.4); }
    .j6-dim td { opacity: .45; }
    .j6-up { color: #ff5b5b; } .j6-down { color: #4da6ff; } .j6-muted { color: #9aa0aa; }
    .j6-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:3px; }
    .j6-on { background:#44f0a1; } .j6-off { background:#4a4f57; }
    .j6-note { color:#ffb020; font-size:1rem; font-weight:800; line-height:1.7; }
    .j6-sub { color:#c8ccd4; font-size:1rem; font-weight:700; line-height:1.85; }
    @media (max-width: 600px) {
        .j6-kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
        .j6-table { font-size: .82rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    auth.sync_auth()
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스6 — 종가 관찰")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j6_login_password")
    if st.button("자비스6 로그인", width="stretch"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import importlib

import jarvis4_data as j4
import jarvis6_data as j6
import jarvis6_guide as guide
import jarvis6_store as store

# 배포 중 옛 모듈이 프로세스에 남으면 계산이 조용히 옛것으로 돈다(CLAUDE.md 11항).
for _module, _need in ((j6, 2026072701), (guide, 2026072701), (store, 2026072701)):
    if int(getattr(_module, "MODULE_REVISION", 0)) < _need:
        importlib.reload(_module)

_SEOUL = ZoneInfo("Asia/Seoul")


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _pct(value, digits=1) -> str:
    if value is None:
        return "<span class='j6-muted'>—</span>"
    cls = "j6-up" if value > 0 else "j6-down" if value < 0 else "j6-muted"
    return f"<span class='{cls}'>{value:+.{digits}f}%</span>"


def _dots(items) -> str:
    return "".join(
        f"<span class='j6-dot {'j6-on' if ok else 'j6-off'}' title='{_esc(name)}'></span>"
        for name, ok, _v in items
    )


def _guide(title: str, producer) -> None:
    """설명은 그 내용이 있는 자리에서 펼친다. 따로 찾아가지 않게."""
    with st.expander(title, expanded=False):
        st.markdown(producer(), unsafe_allow_html=True)


def _render_guides() -> None:
    """설명만 따로 훑고 싶을 때 쓰는 목록."""
    for title, producer in guide.SECTIONS:
        _guide(title, producer)


@st.cache_data(ttl=120, show_spinner=False)
def _load_candidates(limit: int = 12) -> dict:
    """자비스4가 이미 쓰는 조회를 그대로 쓴다. 새 자료원을 만들지 않는다."""
    market = j4.get_market_overview()
    ranking = j4.get_theme_rankings()
    if not ranking.get("ok"):
        return {"ok": False, "error": ranking.get("error"), "market": market}

    # 시가총액은 테마 상세에 없고 실시간 묶음조회에 들어 있다. 대형주에서만
    # 외인·기관 수급을 무겁게 보므로 이 값이 없으면 판정이 틀어진다.
    codes, rows = [], []
    for theme_row in ranking["rows"][:6]:
        leaders = j4.get_theme_leaders(theme_row, market.get("score", 0),
                                       theme_row.get("score", 0))
        if not leaders.get("ok"):
            continue
        for leader in leaders["rows"][:3]:
            metrics = leader.get("metrics") or {}
            flow = leader.get("flow") or {}
            stock = {
                "price": metrics.get("current"),
                "day_open": metrics.get("day_open"),
                "day_high": metrics.get("day_high"),
                "day_low": metrics.get("day_low"),
                "trading_value": (metrics.get("avg_trading_value") or 0)
                                 * (metrics.get("volume_ratio") or 0),
                "market_cap": None,
            }
            codes.append(leader.get("code"))
            rows.append({
                "code": leader.get("code"), "name": leader.get("name"),
                "theme": theme_row.get("name"), "stock": stock,
                "metrics": metrics, "flow": flow, "theme_row": theme_row,
            })

    try:
        import naver_stock_quote as quote_api
        quotes = quote_api.get_quotes(codes)
    except Exception:
        quotes = {}
    for row in rows:
        quote = quotes.get(row["code"]) or {}
        if quote.get("tradable"):
            for key in ("day_open", "day_high", "day_low"):
                if quote.get(key):
                    row["stock"][key] = quote[key]
            if quote.get("trading_value"):
                row["stock"]["trading_value"] = quote["trading_value"]
        row["stock"]["market_cap"] = quote.get("market_cap")
        row["eval"] = j6.evaluate(row["stock"], row["metrics"],
                                  row["flow"], row["theme_row"])

    return {"ok": True, "market": market, "rows": j6.rank(rows)[:limit],
            "checked_at": datetime.now(_SEOUL).strftime("%H:%M")}


def _render_header(market: dict, phase: dict) -> None:
    now = datetime.now(_SEOUL)
    cells = [
        ("지금", now.strftime("%H:%M")),
        ("단계", phase["label"]),
        ("시장", f"{market.get('score', 0):.0f}점 {market.get('regime', '—')}"
                 if market.get("ok") else "자료 없음"),
        ("판단 마감", "15:18"),
    ]
    st.markdown(
        "<div class='j6-kpi-grid'>"
        + "".join(f"<div class='j6-kpi'><div class='j6-kpi-label'>{_esc(a)}</div>"
                  f"<div class='j6-kpi-value'>{_esc(b)}</div></div>" for a, b in cells)
        + "</div>",
        unsafe_allow_html=True,
    )
    if not phase["watching"]:
        st.markdown(
            f"<div class='j6-note'>지금은 <b>{_esc(phase['label'])}</b>입니다. "
            "관찰 구간은 평일 14:30~15:19입니다. 그 밖에는 마지막 자료를 보여줍니다.</div>",
            unsafe_allow_html=True,
        )


def _why(e: dict) -> str:
    """왜 이 종목이 여기 있나 — 한 마디로.

    좋으면 좋은 이유를, 아니면 걸린 이유를 적는다. 숫자만 늘어놓으면
    무엇을 보라는 건지 알 수 없다.
    """
    if e["warnings"]:
        return e["warnings"][0]

    from_high = e["from_high"]
    wick = e["upper_wick"]
    ratio = e["value_ratio"]

    # 걸린 이유가 있으면 그것부터
    if from_high is not None and from_high < -10:
        return f"전고점이 {abs(from_high):.0f}% 남아 자리가 아니다"
    if wick is not None and wick > 0.5:
        return f"고가에서 {wick*100:.0f}% 밀렸다"
    if ratio is not None and ratio < 2:
        return f"거래대금 {ratio:.1f}배 — 돈이 덜 몰렸다"

    # 여기까지 왔으면 좋은 이유를 적는다
    good = []
    if from_high is not None:
        good.append("신고가 돌파" if from_high >= 0 else f"전고점 {abs(from_high):.1f}% 앞")
    if ratio is not None:
        good.append(f"돈 {ratio:.1f}배 몰림")
    if wick is not None and wick <= 0.2:
        good.append("고가 마감")
    if e["both_buy_days5"] >= 3:
        good.append(f"외인·기관 {e['both_buy_days5']}일 동반")
    return " · ".join(good) if good else "—"


def _render_table(rows: list[dict]) -> int | None:
    """클릭되는 표. 줄을 누르면 그 종목이 아래에 펼쳐진다.

    HTML 표는 예쁘게 그릴 수 있지만 눌러도 파이썬이 알 수 없다. 그래서
    스트림릿 표에 선택을 켜고, 색은 스타일러로 입힌다.
    종목은 초록, 테마는 붉은색(2026-07-26 사용자 지시).
    """
    import pandas as pd

    frame = pd.DataFrame([
        {
            "종목": row["name"],
            "테마": row["theme"],
            "왜 이 종목인가": _why(row["eval"]),
            "조건": f"{row['eval']['passed']}/{row['eval']['total']}",
            "전고점": (f"{row['eval']['from_high']:+.1f}%"
                     if row["eval"]["from_high"] is not None else "—"),
            "거래대금": (f"{row['eval']['value_ratio']:.1f}배"
                     if row["eval"]["value_ratio"] else "—"),
            "윗꼬리": (f"{row['eval']['upper_wick']*100:.0f}%"
                     if row["eval"]["upper_wick"] is not None else "—"),
            "수급": f"{row['eval']['both_buy_days5']}일/5일",
        }
        for row in rows
    ])

    styled = (
        frame.style
        .set_properties(subset=["종목"], **{"color": "#44f0a1", "font-weight": "800"})
        .set_properties(subset=["테마"], **{"color": "#ff6b6b", "font-weight": "700"})
        .set_properties(subset=["왜 이 종목인가"], **{"color": "#e6e6e6", "font-weight": "700"})
        .set_properties(subset=["조건"], **{"color": "#4da6ff", "font-weight": "800"})
    )

    event = st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="j6_table",
        column_config={
            "왜 이 종목인가": st.column_config.TextColumn(width="large"),
            "종목": st.column_config.TextColumn(width="small"),
        },
    )
    picked = (event.selection or {}).get("rows") or []
    return picked[0] if picked else None


def _render_detail(row: dict) -> None:
    e, m = row["eval"], row["metrics"]
    st.markdown(f"### {row['name']} · {row['theme']}")

    cells = [("전일종가", m.get("prev_close")), ("시가", m.get("day_open")),
             ("고가", m.get("day_high")), ("저가", m.get("day_low")),
             ("현재가", m.get("current"))]
    st.markdown(
        "<div class='j6-kpi-grid' style='grid-template-columns:repeat(5,minmax(0,1fr))'>"
        + "".join(
            f"<div class='j6-kpi'><div class='j6-kpi-label'>{_esc(a)}</div>"
            f"<div class='j6-kpi-value'>{f'{b:,.0f}' if b else '—'}</div></div>"
            for a, b in cells)
        + "</div>",
        unsafe_allow_html=True,
    )

    _guide("당일 가격과 윗꼬리 읽는 법", guide.day_price)
    if e["location"] is not None:
        st.markdown(
            f"<div class='j6-guide'>오늘 <b>저가에서 {e['location']*100:.0f}% 지점</b>에 있습니다. "
            f"윗꼬리 <b>{e['upper_wick']*100:.0f}%</b> — 고가에서 그만큼 밀렸다는 뜻입니다.</div>",
            unsafe_allow_html=True,
        )
        st.progress(min(1.0, max(0.0, e["location"])))

    for label, items in (("재료 (사람이 적는 것)", e["material"]),
                         ("자리 (차트)", e["place"]),
                         ("힘 (오늘 들어오는 돈)", e["strength"])):
        marks = " &nbsp; ".join(
            (f"<span class='j6-check'>&#10004;</span>" if ok
             else f"<span class='j6-cross'>&#10008;</span>")
            + f" {_esc(name)}"
            + (f" <span class='j6-muted'>{_esc(value)}</span>" if value else "")
            for name, ok, value in items
        )
        st.markdown(f"<div class='j6-sub'><b style='color:#4da6ff'>{_esc(label)}</b><br>{marks}</div>",
                    unsafe_allow_html=True)

    _guide("수급은 어디까지 보이나요", guide.supply_demand)
    for warning in e["warnings"]:
        st.markdown(f"<div class='j6-note'>주의 — {_esc(warning)} "
                    "(막지 않습니다. 사시면 기록만 남습니다.)</div>", unsafe_allow_html=True)

    with st.expander("차트 보기 (당일 · 일봉 · 주봉 · 월봉)", expanded=False):
        intraday = j4.get_last_session_intraday(row["code"])
        if intraday and intraday.get("ok"):
            st.caption(f"당일 분봉 · {intraday.get('source_time')}")
            st.line_chart(intraday["price"], height=180)
        # 일봉·주봉·월봉을 한 줄에 나란히 놓는다. 눌러서 바꿔 보면 서로 비교가 안 된다.
        bundle = j4.get_chart_bundle(row["code"])
        if bundle.get("ok"):
            charts = bundle["charts"]
            names = list(charts.keys())
            for column, name in zip(st.columns(len(names)), names):
                payload = charts.get(name) or {}
                frame = payload.get("price")
                with column:
                    st.markdown(
                        f"<div style='color:#4da6ff;font-weight:800;font-size:.95rem'>{_esc(name)}</div>",
                        unsafe_allow_html=True,
                    )
                    if payload.get("ok") and frame is not None and len(frame):
                        st.line_chart(frame, height=200)
                    else:
                        st.caption("자료 없음")

    key = f"j6_{row['code']}"
    reason = st.text_input("왜 오르나 (나중에 써도 됩니다)", key=f"{key}_reason")
    cont = st.text_input("내일까지 갈 근거", key=f"{key}_cont")
    inval = st.text_input("틀렸다고 볼 조건", key=f"{key}_inval")

    _guide("연습은 어떻게 하나요", guide.practice_mode)
    left, right = st.columns(2)
    for column, action, label in ((left, "bought", "샀다"), (right, "skipped", "안 샀다")):
        if column.button(label, key=f"{key}_{action}", width="stretch"):
            row["stock"].update({"reason": reason, "continuation": cont,
                                 "invalidation": inval})
            store.save_pick(row, action=action)
            st.success(f"{row['name']} — {label}로 기록했습니다. 1주 기준, 연습입니다.")


def _render_records() -> None:
    _guide("기록해서 뭘 얻나요", guide.why_record)
    _guide("저녁에 뭘 확인하나요", guide.after_hours)
    _guide("다음 날 언제 파나요", guide.next_morning)
    picks = store.list_picks(limit=40)
    if not picks:
        st.caption("아직 기록이 없습니다. 후보에서 '샀다'나 '안 샀다'를 누르면 쌓입니다.")
        return
    body = []
    for p in picks:
        action = "샀다" if p["action"] == "bought" else "안 샀다"
        price = f"{p['price']:,.0f}" if p.get("price") else "—"
        has_reason = "있음" if (p.get("reason") or "").strip() else "없음"
        body.append(
            "<tr>"
            f"<td>{_esc(p['trade_date'])}</td>"
            f"<td class='j6-left'>{_esc(p['name'])}</td>"
            f"<td>{action}</td>"
            f"<td>{price}</td>"
            f"<td>{p['passed']}/{p['total']}</td>"
            f"<td>{has_reason}</td>"
            f"<td>{_pct(p.get('net_pct'), 2)}</td>"
            "</tr>"
        )
    st.markdown(
        "<table class='j6-table'><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in
                  ("날짜", "종목", "행동", "가격", "조건", "이유", "익일 결과"))
        + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>",
        unsafe_allow_html=True,
    )

    summary = store.review()
    st.markdown("#### 조건별 성적")
    if summary["total"] < store.MIN_SAMPLE:
        st.markdown(
            f"<div class='j6-guide'>결과가 붙은 기록이 <b>{summary['total']}건</b>입니다. "
            f"<b>{store.MIN_SAMPLE}건</b>이 넘어야 숫자를 보여드립니다. "
            "표본이 적을 때 승률을 말하면 그건 거짓말입니다.</div>",
            unsafe_allow_html=True,
        )
        return
    for group in summary["groups"]:
        if not group["enough"]:
            st.markdown(f"<div class='j6-guide'>{_esc(group['label'])} — "
                        f"{group['n']}건 (표본 부족)</div>", unsafe_allow_html=True)
            continue
        st.markdown(
            f"<div class='j6-guide'><b>{_esc(group['label'])}</b> {group['n']}건 · "
            f"승률 {group['win']:.0f}% · 거래당 {group['avg']:+.2f}% · "
            f"손익비 {group['rr']:.2f} · 최악 {group['worst']:+.2f}%</div>",
            unsafe_allow_html=True,
        )


def main() -> None:
    st.markdown("## 자비스6 — 종가 관찰")
    st.markdown(
        "<div class='j6-guide'>장 막판에 조건을 재서 보여주고, 눌러 둔 것을 기록합니다. "
        "<b>추천기가 아니고, 막지도 않습니다.</b> 지금은 <b>1주 고정 연습</b>이라 돈이 들지 않습니다.</div>",
        unsafe_allow_html=True,
    )
    _guide("자비스6이 뭔가요", guide.what_is_this)

    # 결과가 안 붙은 기록을 조용히 채운다. 부르는 곳이 없으면 영원히 반쪽이다.
    try:
        store.fill_outcomes()
    except Exception:
        pass

    phase = j6.market_phase()
    tab_watch, tab_record, tab_guide = st.tabs(["후보 보기", "기록 · 복기", "설명"])

    with tab_watch:
        with st.spinner("오늘 후보를 재는 중입니다…"):
            data = _load_candidates()
        _render_header(data.get("market") or {}, phase)
        _guide("시장 상태는 왜 먼저 보나요", guide.market_gate)
        _guide("왜 15시 18분인가요", guide.timing)
        if not data.get("ok"):
            st.warning(f"자료를 가져오지 못했습니다: {data.get('error')}")
            return
        rows = data["rows"]
        if not rows:
            st.info("오늘 조건에 걸린 종목이 없습니다. 없는 날도 정상입니다.")
            return
        st.caption(f"{data['checked_at']} 기준 · {len(rows)}개 · "
                   "표에서 종목 줄을 누르면 아래에 자세히 나옵니다")
        index = _render_table(rows)
        _guide("재료·자리·힘이 뭔가요", guide.three_groups)
        st.divider()
        if index is None:
            st.info("위 표에서 보고 싶은 종목 줄을 눌러 주십시오.")
        else:
            _render_detail(rows[index])
        if st.button("자료 다시 받기", key="j6_reload"):
            _load_candidates.clear()
            st.rerun()

    with tab_record:
        _render_records()

    with tab_guide:
        _render_guides()


main()
