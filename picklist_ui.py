"""날짜별로 저장된 목록을 화면에서 불러 보는 자리 (2026-08-09 상하님 지시).

상하님 요구 — "각 테마에 저장된 리스트를 화면으로 불러올 수 있는 것을 만들고,
클릭하면 리스트가 뜨도록 하고, 클릭 버튼을 만들어라. 엑셀로 파일 다운받기도 하라."

미국테마(자비스3)·한국테마(자비스4) 두 화면이 **같은 코드를 쓴다.** 한쪽만 고쳐
두 화면이 달라지는 일을 막으려는 것이다(method_help와 같은 방식).

여기서는 **아무것도 계산하지 않는다.** 저장된 줄을 그대로 표로 그리고 파일로 내려
줄 뿐이다. 그래야 "그날 화면에 뜬 그대로"라는 약속이 지켜진다.
"""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import picklist_store as store

_SEOUL = ZoneInfo("Asia/Seoul")

# 표시 문구·칸을 바꾸면 이 숫자를 올리고 페이지의 요구 리비전도 올린다(규칙 11).
MODULE_REVISION = 2026080940

def open_key(market: str) -> str:
    """여닫힘을 담아 두는 자리 이름. **시장마다 따로 둔다.**

    하나로 두면 한국테마에서 펴 놓은 것이 미국테마에서도 펴져 있다. 두 화면은
    서로 다른 목록이라 각자 기억해야 한다(2026-08-09 실물에서 확인).
    """
    return f"picklist_archive_open_{str(market).upper()}"

# 화면에 보일 칸과 그 이름. 저장 파일에는 칸이 더 많지만(내려받기에는 다 들어간다)
# 화면에서는 눈으로 읽을 것만 남긴다 — 칸 이름이 곧 그 칸의 질문이다.
_COLUMNS = (
    ("rank", "순위"),
    ("trade_date", "매수일"),
    ("name", "종목명"),
    ("code", "티커·종목코드"),
    ("score", "점수"),
    ("price", "신호일 종가"),
    ("buy_open", "매수금액 (다음날 시가)"),
    ("now_price", "지금 값"),
    ("profit_pct", "수익·손실"),
    ("days_since", "지난 날수"),
    ("from_high_pct", "고점 대비"),
    ("judged_from_high_pct", "기준일 낙폭"),
    ("bucket_label", "낙폭 갈래"),
    ("wait_days", "고점 뒤 며칠"),
    ("hold_days", "보유일수"),
    ("state", "매수 상태"),
    ("themes", "테마"),
)

# 매수일·매수금액·지금 값·수익률은 **네 갈래 모두** 앞쪽에 둔다(2026-08-09 상하님
# 지시) — 그날 얼마에 샀고 그 뒤 얼마가 됐는지가 이 화면의 목적이다.
_HEAD = ("rank", "trade_date", "name", "code", "score",
         "price", "buy_open", "now_price", "profit_pct", "days_since")

# 갈래마다 뜻이 없는 칸은 감춘다 — 빈 칸이 늘어서 있으면 표가 안 읽힌다.
_KIND_COLUMNS = {
    "pullback": _HEAD + ("from_high_pct", "wait_days", "state", "themes"),
    "breakout": _HEAD + ("from_high_pct", "wait_days", "hold_days", "themes"),
    "crash": _HEAD + ("judged_from_high_pct", "from_high_pct", "bucket_label",
                      "hold_days", "themes"),
    "top7": _HEAD + ("state", "themes"),
}

CSS = """
<style>
.pl-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch;
    border: 1px solid rgba(255,255,255,.09); border-radius: .55rem; margin-bottom: .9rem; }
.pl-table { width: 100%; min-width: 760px; border-collapse: collapse; font-size: .88rem; }
.pl-table th { text-align: center; color: #9dccff; font-weight: 800; white-space: nowrap;
    padding: .5rem .45rem; background: rgba(77,166,255,.07);
    border-bottom: 1px solid rgba(77,166,255,.3); }
.pl-table td { text-align: center; color: #e6e6e6; padding: .45rem .45rem;
    white-space: nowrap; border-bottom: 1px solid rgba(255,255,255,.06); }
.pl-table tr:last-child td { border-bottom: none; }
.pl-name { color: #c084fc !important; font-weight: 800; }
/* 한국 테마는 한 종목이 테마를 열 개씩 달고 있어, 그대로 두면 표가 2,200px까지
   늘어난다(2026-08-09 폰 실측). 테마 칸만 폭을 묶고 넘치면 …으로 자른다 —
   전체 이름은 칸에 손을 올리면 뜬다. 자르는 것은 **폭을 묶은 칸(td)** 이어야 한다.
   안쪽 글자에만 걸면 칸이 그대로 늘어난다. */
.pl-table td.pl-c-themes { max-width: 18rem; overflow: hidden; text-overflow: ellipsis;
    text-align: left; }
.pl-theme { color: #9dccff !important; }
.pl-up { color: #4da6ff; font-weight: 700; }
.pl-down { color: #ff5b5b; font-weight: 700; }
/* 수익·손실은 이 표에서 가장 먼저 보여야 하는 칸이라 더 굵고 진하게 뽑는다.
   번 것은 초록, 잃은 것은 붉은색 — 위 '고점 대비'(파랑/빨강)와 색을 갈라
   두 칸이 서로 다른 것을 말한다는 것이 눈에 보이게 한다. */
.pl-sameday { color: #9aa0aa; font-weight: 700; }
.pl-profit-up { color: #22c55e; font-weight: 900; }
.pl-profit-down { color: #ff4d4f; font-weight: 900; }
.pl-table td.pl-c-profit_pct { font-size: .95rem; }
.pl-kind { color: #ffb020; font-weight: 800; font-size: 1.02rem; margin: 1rem 0 .35rem; }
.pl-note { color: #9aa0aa; font-size: .88rem; line-height: 1.6; margin: .2rem 0 .8rem; }
.pl-note b { color: #44f0a1; }
/* 여는 단추 — 네 갈래 단추와 같은 결의 회색 띠. 누를 곳이라는 것만 보이면 된다. */
div[class*="st-key-picklist_archive_open"] button,
div[class*="st-key-btn_picklist_archive_open"] button {
    background: linear-gradient(90deg, #2b2f38 0%, #3c424e 38%, #6b7484 100%) !important;
    border: none !important; border-radius: .5rem !important;
    min-height: 3rem !important;
    box-shadow: 0 2px 10px rgba(107,116,132,.25) !important;
}
div[class*="st-key-picklist_archive_open"] button p,
div[class*="st-key-btn_picklist_archive_open"] button p {
    color: #ffffff !important; font-size: 1.02rem !important; font-weight: 800 !important;
}
</style>
"""


def _cell(row: dict, field: str) -> str:
    value = row.get(field)
    # 수익·손실과 매수금액은 **왜 비었는지**를 알려 준다. 그냥 '—'로 두면
    # '아직 살 때가 안 됐다'와 '못 받아 왔다'가 구별되지 않는다(2026-08-09).
    if field in ("profit_pct", "buy_open") and value in (None, ""):
        days = row.get("days_since")
        if days == 0:
            return "<span class='pl-sameday'>아직 안 삼</span>"
        if row.get("now_price") in (None, "") and field == "profit_pct":
            return "—"
        return "<span class='pl-sameday'>못 받음</span>"
    if value in (None, ""):
        return "—"
    if field in ("from_high_pct", "judged_from_high_pct"):
        number = float(value)
        klass = "pl-up" if number >= 0 else "pl-down"
        return f"<span class='{klass}'>{number:+.2f}%</span>"
    if field == "profit_pct":
        number = float(value)
        klass = "pl-profit-up" if number >= 0 else "pl-profit-down"
        return f"<span class='{klass}'>{number:+.2f}%</span>"
    if field == "score":
        return f"{float(value):.1f}"
    if field in ("price", "buy_open", "now_price"):
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    if field == "days_since":
        days = int(float(value))
        return "당일" if days == 0 else f"{days}일째"
    if field in ("rank", "wait_days", "hold_days"):
        return f"{int(float(value))}"
    if field == "name":
        return f"<span class='pl-name'>{html.escape(str(value))}</span>"
    if field == "themes":
        text = html.escape(str(value))
        return f"<span class='pl-theme' title='{text}'>{text}</span>"
    return html.escape(str(value))


def table_html(rows, kind: str) -> str:
    """한 갈래의 표를 통째로 그린다. 값은 하나도 고치지 않는다."""
    fields = _KIND_COLUMNS.get(kind, tuple(field for field, _ in _COLUMNS))
    titles = dict(_COLUMNS)
    head = "".join(f"<th>{titles.get(field, field)}</th>" for field in fields)
    body = []
    for row in rows:
        cells = "".join(
            f"<td class='pl-c-{field}'>{_cell(row, field)}</td>" for field in fields
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        "<div class='pl-wrap'><table class='pl-table'>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def fetch_prices(market: str, codes) -> dict:
    """종목마다 '지금 값'을 모아 온다. 못 받은 종목은 목록에서 빠진다.

    화면이 이미 쓰는 `get_live_quote`를 그대로 부른다 — 여기서 시세를 새로
    계산하지 않는다. 한 종목이 실패해도 나머지는 그대로 온다.

    종목이 마흔 개쯤이라 하나씩 부르면 오래 걸린다. 서로를 기다릴 필요가 없으므로
    한꺼번에 부른다. 일꾼은 6개로 묶어 둔다 — 온라인은 코어가 한두 개뿐이라
    무작정 늘리면 오히려 느려진다(2026-07-30에 겪은 자리).
    """
    from concurrent.futures import ThreadPoolExecutor

    codes = [str(code) for code in dict.fromkeys(codes) if str(code).strip()]
    if not codes:
        return {}
    if str(market).upper() == "US":
        import jarvis3_data as data
    else:
        import jarvis4_data as data

    def _one(code):
        try:
            quote = data.get_live_quote(code)
        except Exception:
            return code, None
        if not isinstance(quote, dict) or not quote.get("ok"):
            return code, None
        return code, quote.get("current")

    out = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for code, price in pool.map(_one, codes):
            if price is not None:
                out[code] = price
    return out


# 시가 조회는 **창고(picklist_store)로 옮겼다**(2026-08-12) — 화면만 부르면
# 상하님이 단추를 눌러야 채워지고, 온라인에서 채운 값은 저장소에 안 올라가
# 앱이 한 번 쉬면 사라진다. 이제 클라우드 수집기도 같은 함수를 부른다.
fetch_buy_opens = store.fetch_buy_opens


def render(st, market: str, *, toggle) -> None:
    """'저장된 목록 보기' 구역 전체.

    toggle : 페이지의 ``_section_toggle``을 그대로 받는다. 여닫는 방식이 그 화면의
             다른 구역과 같아야 해서 새로 만들지 않고 빌려 쓴다.
    """
    market = str(market).upper()
    st.markdown(CSS, unsafe_allow_html=True)
    if not toggle("📁 날짜별로 저장해 둔 목록 보기", open_key(market),
                  close_label="저장해 둔 목록 닫기"):
        return

    dates = store.available_dates(market)
    if not dates:
        st.info(
            "아직 저장된 날이 없습니다. 장 마감 뒤 자동으로 하루에 한 번 저장됩니다 — "
            "상하님이 접속하지 않아도 저장됩니다."
        )
        return

    st.markdown(
        "<div class='pl-note'>그날 화면에 떠 있던 목록을 <b>그대로</b> 옮겨 둔 것입니다. "
        "다시 계산하지 않으므로, 시간이 지난 뒤 그때 목록이 맞았는지 견줄 수 있습니다.<br>"
        "<b>매수금액은 신호가 난 날의 <u>다음 거래일 시가</u></b>입니다 — 설명서의 "
        "규칙이 ‘종가를 확인하고 다음 거래일 시가에 산다’이기 때문입니다. "
        "<b>수익·손실</b>은 그 시가와 <b>지금 값</b>을 견준 것입니다.<br>"
        "신호가 난 날에는 아직 살 수 없으므로 <b>‘아직 안 삼’</b>으로 두고, "
        "<b>다음 거래일부터</b> 숫자가 나옵니다. 날짜마다 따로 저장되므로 같은 종목이 "
        "이튿날 또 나와도 <u>그날의 매수금액으로 따로 잽니다.</u><br>"
        "실제로 사고팔았다는 뜻이 아니라 <u>그날 목록이 그 뒤 어떻게 됐는지</u>를 "
        "보는 숫자입니다."
        "</div>",
        unsafe_allow_html=True,
    )
    picked = st.selectbox(
        "어느 날 목록을 볼까요", dates, index=0, key=f"picklist_date_{market}",
    )
    rows = store.load_rows(picked, market)
    if not rows:
        st.warning(f"{picked} 자료를 읽지 못했습니다.")
        return

    # 눌러야 받아 온다 — 목록 한 판이 마흔 종목이라 화면을 그릴 때마다 받아 오면
    # 이 구역을 여는 데만 몇 초가 걸린다(2026-08-09).
    cache_key = f"picklist_prices_{market}_{picked}"
    fetched_at_key = f"{cache_key}_at"
    if st.button("💰 지금 값으로 수익·손실 계산", key=f"picklist_calc_{market}"):
        count = len({row.get("code") for row in rows})
        with st.spinner(f"{picked} 목록 {count}종목의 매수 시가와 지금 값을 받는 중입니다…"):
            # ① 아직 안 채운 줄의 **다음 거래일 시가**를 찾아 파일에 적어 둔다.
            #    한 번 적히면 다시는 안 바뀐다 — 과거의 시가는 고정된 사실이다.
            opens = fetch_buy_opens(market, rows)
            if opens:
                rows = store.set_buy_opens(rows, opens)
                try:
                    store.save_rows(rows, trade_date=picked, market=market)
                except Exception:
                    pass      # 못 적어도 화면 숫자는 그대로 나온다
            # ② 지금 값
            st.session_state[cache_key] = fetch_prices(
                market, [row.get("code") for row in rows])
        st.session_state[fetched_at_key] = datetime.now(_SEOUL).strftime("%H:%M")
        rows = store.load_rows(picked, market)
    prices = st.session_state.get(cache_key) or {}
    if prices:
        rows = store.with_profit(rows, prices)

    fetched_at = st.session_state.get(fetched_at_key)
    filled = sum(1 for row in rows if store._num(row.get("buy_open")) is not None)
    st.caption(
        f"{picked} · {store.summarize(rows)}"
        + (f" · 지금 값 {fetched_at} 기준({len(prices)}종목) · 매수 시가 {filled}줄"
           if fetched_at else " · 수익·손실은 위 단추를 누르면 채워집니다")
    )

    excel = store.to_excel_bytes(rows)
    columns = st.columns(2)
    if excel:
        columns[0].download_button(
            "⬇ 엑셀로 받기 (.xlsx)", data=excel,
            file_name=f"목록_{market}_{picked}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"picklist_xlsx_{market}", width="stretch",
        )
    columns[1].download_button(
        "⬇ CSV로 받기", data=store.to_csv_bytes(rows),
        file_name=f"목록_{market}_{picked}.csv", mime="text/csv",
        key=f"picklist_csv_{market}", width="stretch",
    )

    for kind in store.KIND_ORDER:
        part = [row for row in rows if str(row.get("list_kind")) == kind]
        if not part:
            continue
        st.markdown(
            f"<div class='pl-kind'>{store.LIST_KINDS[kind]} · {len(part)}종목</div>",
            unsafe_allow_html=True,
        )
        st.markdown(table_html(part, kind), unsafe_allow_html=True)


def autosave(market: str, list_kind: str, result) -> None:
    """화면이 목록을 그릴 때 그날 것이 없으면 조용히 한 판 남긴다.

    자동 저장의 본체는 클라우드 작업(picklist_collector)이다. 이건 그것이 실패한
    날을 메우는 보조 장치라, **이미 그날 그 갈래가 저장돼 있으면 아무것도 하지
    않는다** — 장중에 눌러 볼 때마다 파일을 새로 쓰면 마감값이 장중값으로 덮인다.
    무슨 일이 있어도 화면을 죽이지 않는다(조용한 실패).
    """
    try:
        trade_date = store.trade_date_for(market)
        if list_kind in store.saved_kinds(trade_date, market):
            return
        rows = store.rows_from_result(
            result, market=market, list_kind=list_kind, trade_date=trade_date)
        store.save_rows(rows, trade_date=trade_date, market=market)
    except Exception:
        pass
