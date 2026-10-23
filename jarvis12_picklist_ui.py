"""자비스12 전용 날짜별 목록 화면 — picklist_ui.render 를 베낀 것 (2026-10-15 상하님 지시).

상하님 — 9월 1일 날짜별 목록의 「급락 후 반등장」이 성적표 급락 10종목과 다르다(그날 옛 규칙으로 찍은 20개). 고르신 것:
**「10종목으로 바꿔 보여 주기」** — 자비스12 에서는 그날 들고 있던 기준일 10종목이 보이고, 저장 파일과 자비스3 은 그대로.

picklist_ui 는 자비스3·한국테마와 같이 쓰는 얼린 파일이라(CLAUDE.md 0-2) 여기에 render 하나만 베꼈다. 표 그리기·누르기
장치·값 받기·파일 만들기는 picklist_ui 것을 **그대로 부른다.** 베낀 render 와 원본이 다른 곳은 넷뿐이다.
  ① rows_view — 보여 줄 줄(shown)을 따로 만든다. **파일에 적는 것(save_rows)은 언제나 저장된 줄(rows)** 이다.
  ② quick_prices — 장이 닫혀 있으면 마지막 종가를 바로(2026-10-14 · 64.6초 → 3초).
  ③ 지금 값·그날 엑셀 칸 이름을 j12_ 로 — 같은 세션의 자비스3 칸과 섞이지 않게.
  ④ kind_note — 갈래 표 밑 한 줄.
picklist_ui.render 를 고치면(상하님이 자비스3 을 고치라고 하실 때) 여기도 같이 볼 것.
"""

from __future__ import annotations

from datetime import datetime

from picklist_ui import (  # noqa: F401  — 원본의 이름을 그대로 쓴다
    CSS,
    _SEOUL,
    _keep_keyboard_down,
    _kept_file,
    _remember_pick,
    fetch_buy_opens,
    fetch_prices,
    open_key,
    pick_bridge,
    pick_key,
    store,
    table_html,
)

# 표시·계산을 바꾸면 올리고 자비스12 의 _REQUIRED_J12_PICKLIST_REVISION 도 같이 올린다(규칙 11).
MODULE_REVISION = 2026101510


def _view(rows_view, picked: str, rows: list) -> list:
    """보여 줄 줄. 못 만들면 저장된 줄 그대로 — 바꾸다 실패했다고 목록을 비우지 않는다(CLAUDE.md 0-0)."""
    if rows_view is None:
        return list(rows)
    try:
        shown = rows_view(picked, [dict(row) for row in rows])
    except Exception:
        return list(rows)
    return list(rows) if shown is None else list(shown)


def render(st, market: str, *, toggle, header=None, close=None, on_pick=None,
           scorecard=None, rows_view=None, quick_prices=None, kind_note=None) -> None:
    """'저장된 목록 보기' 구역 전체 — picklist_ui.render 와 같고 자비스12 가 넘기는 셋만 더 받는다.

    rows_view   : ``rows_view(날짜, 저장된 줄) -> 보여 줄 줄``. 자비스12 는 「급락 후 반등장」 줄을 그날 들고 있던
                  기준일 10종목으로 바꿔 보여 준다(2026-10-15 상하님 「10종목으로 바꿔 보여 주기」). **파일에 적는 것은
                  언제나 저장된 줄**이다 — 매수금액 채우기·다시 받기가 save_rows 에 넘기는 것은 rows 뿐이다.
    quick_prices: ``quick_prices(종목들) -> {종목: 값} 또는 None``. 미국장이 닫혀 있으면 마지막 종가를 바로 준다
                  (2026-10-14 · 종목마다 다시 받던 64.6초). None 이면 예전처럼 받는다.
    kind_note   : ``kind_note(갈래, 그 갈래 줄) -> HTML 또는 None``. 표 바로 밑에 붙일 한 줄.

    아래는 picklist_ui.render 의 설명 그대로다.

    toggle : 페이지의 ``_section_toggle``을 그대로 받는다. 여닫는 방식이 그 화면의
             다른 구역과 같아야 해서 새로 만들지 않고 빌려 쓴다.
    close  : 페이지의 ``_section_close``. 넘기면 이 구역 **맨 아래 왼쪽**에 작은
             닫기 단추를 하나 더 둔다(2026-08-15 상하님 지시). 이 구역은 날짜마다
             표가 넷이라 화면 몇 장이고, 다 보고 나면 맨 위 닫기 단추가 화면 밖으로
             나가 접으려고 한참 올라가야 했다. 안 넘기면 예전처럼 위에만 둔다.
    on_pick: 종목명을 눌렀을 때 **그 종목 세부사항을 그릴 함수**다(2026-09-01
             상하님 지시 — "종목명에 종목을 누르면 선택종목 세부사항이 나오도록").
             `on_pick(code, name, kind, row)` 로 부르고, 표 아래 · 닫기 단추 위에서
             부른다. 안 넘기면 종목명은 예전처럼 그냥 글자다 — 이 모듈은 시장을
             가리지 않아야 하므로 **무엇을 그릴지는 화면 쪽이 정한다.**
    scorecard: 「CSV로 받기」 자리에 놓을 **파트별 성적표** 함수다 (2026-09-16
             상하님 지시 — "자리는 csv로 받기 자리에 그대로 넣고, 밑에 저장해 둔
             28일치 csv는 비워둬라"). 넘기면 그 두 자리의 CSV 단추가 성적표로
             바뀌고, 안 넘기면 **지금과 똑같이** CSV 단추가 나온다. 이 모듈은
             시장을 가리지 않아야 하므로 **무엇을 그릴지는 화면 쪽이 정한다.**
    header : 이 구역 **맨 위**에 그릴 것이 있으면 넘긴다(2026-08-14 상하님 지시 —
             "날짜별로 저장해 둔 목록 보기에 제일 위에 자동 저장된 게 나오도록").
             미국은 매수 기록을, 한국은 아직 아무것도 안 넘긴다. 이 모듈은 시장을
             가리지 않아야 하므로 **여기서 매수 기록을 직접 읽지 않는다** —
             무엇을 그릴지는 화면 쪽이 정한다.
    """
    market = str(market).upper()
    st.markdown(CSS, unsafe_allow_html=True)
    if not toggle("📁 날짜별로 저장해 둔 목록 보기", open_key(market),
                  close_label="저장해 둔 목록 닫기"):
        return
    if header is not None:
        try:
            header()
        except Exception as exc:      # 맨 위 한 칸 때문에 목록 전체가 막히면 안 된다
            st.caption(f"매수 기록을 읽지 못했습니다: {exc}")

    dates = store.available_dates(market)
    if not dates:
        st.info(
            "아직 저장된 날이 없습니다. 장 마감 뒤 자동으로 하루에 한 번 저장됩니다 — "
            "상하님이 접속하지 않아도 저장됩니다."
        )
        return

    # **날짜 고르기 위의 설명 네 줄은 뺐다** (2026-08-29 상하님 지시 —
    # "「어느 날 목록을 볼까요」 바로 위에까지 잘라라").
    # 폰에서 이 글이 화면 한 장을 통째로 먹어, 날짜를 고르려면 매번 그만큼
    # 굴려 내려와야 했다. 같은 내용은 아래 표의 칸 이름과 「설명」 창에 있다.
    # 되살리려면 여기에 pl-note 한 덩어리를 도로 넣으면 된다(CSS는 그대로 둔다).
    # 날짜는 **선택칸 그대로** 두고, 자판만 안 뜨게 한다 (2026-08-28 상하님 지시).
    #
    # 처음에는 누르는 조각(pills)으로 바꿨는데 상하님이 바로 짚으셨다 —
    # "날짜를 저렇게 해 놓으면 **일 년 지나면 250개** 될 거 아냐. 그냥 날짜에
    #  자판이 없게만 하라니깐." 맞다. 지금 16일치라 열여섯 조각이지만 쌓이면
    # 화면이 조각으로 뒤덮인다. 선택칸은 몇 개가 쌓여도 한 줄이다.
    picked = st.selectbox(
        "어느 날 목록을 볼까요", dates, index=0, key=f"picklist_date_{market}",
    )
    _keep_keyboard_down(st, market)
    rows = store.load_rows(picked, market)
    if not rows:
        st.warning(f"{picked} 자료를 읽지 못했습니다.")
        return

    # ── 매수금액(다음 거래일 시가)은 **단추 없이 자동으로** 채운다 ──────────────
    # 2026-08-14 상하님 지시 — "매수금액이 다음날 시가 자동으로 기입되게 하라고.
    # 단추 안 눌러도 자동 기입되어야지."
    #
    # 이래도 느려지지 않는 까닭이 둘이다.
    #   ① **과거의 시가는 고정된 사실**이라 한 번 파일에 적히면 다시 안 받는다.
    #      이미 다 채워진 날(08-11·08-12)은 여기서 아무것도 안 한다.
    #   ② 한 판에 **딱 한 번만** 시도한다. 다음 거래일이 아직 안 열린 날은 받아도
    #      빈칸이라, 안 그러면 화면을 그릴 때마다 헛되이 받아 온다.
    #
    auto_key = f"j12_picklist_open_tried_{market}_{picked}"   # 자비스3 과 따로(2026-10-23)
    if not st.session_state.get(auto_key) and any(
            store._num(row.get("buy_open")) is None for row in rows):
        st.session_state[auto_key] = True
        with st.spinner(f"{picked} 목록의 매수금액(다음 거래일 시가)을 채우는 중입니다…"):
            try:
                opens = fetch_buy_opens(market, rows)
            except Exception as exc:            # 못 받아도 목록은 그대로 보여준다
                opens, _ = {}, exc
            if opens:
                rows = store.set_buy_opens(rows, opens)
                try:
                    store.save_rows(rows, trade_date=picked, market=market)
                except Exception:
                    pass                        # 못 적어도 화면 숫자는 그대로 나온다
    # **보여 줄 줄(shown)은 여기서 만든다** — 위에서 파일에 적은 뒤다. 아래 지금 값·표·그날 엑셀은 shown 으로 그린다.
    shown = _view(rows_view, picked, rows)

    # ── 지금 값·수익·손실도 **단추 없이 자동으로** 채운다 ──────────────────────
    # 2026-08-15 상하님 지적 — "날 지나면 수익 손실이 없냐?"
    #
    # 2026-08-09에는 이것을 단추로 뺐다. 종목마다 따로 받느라 41종목에 **25초**가
    # 걸렸기 때문이다. 2026-08-15에 **묶어 받게 고쳐 3.5초**가 됐다(실측).
    # 그래서 자동으로 되돌린다.
    #
    # **한 판에 한 번만** 받는다 — 지금 값은 1분마다 바뀌지만, 화면을 그릴 때마다
    # 받으면 다른 단추를 누를 때마다 다시 기다리게 된다. 새로 받고 싶으시면 아래
    # '다시 받기' 단추를 누르시면 된다.
    #
    # 자비스12 — 값 담는 칸 이름을 j12_ 로 따로 둔다. 같은 세션에서 자비스3 이 같은 날을 먼저 열면 그 칸에는 저장된
    # 종목 값만 있어 바꿔 보인 급락 종목(HPE·RIVN 등)이 빈칸이 되고, 거꾸로면 자비스3 쪽이 빈칸이 된다.
    cache_key = f"j12_picklist_prices_{market}_{picked}"
    fetched_at_key = f"{cache_key}_at"
    if cache_key not in st.session_state:
        codes = [row.get("code") for row in shown]
        quick = None
        if quick_prices is not None:
            try:
                quick = quick_prices(codes)
            except Exception:
                quick = None
        if quick is not None:
            st.session_state[cache_key] = quick
        else:
            count = len({row.get("code") for row in shown})
            with st.spinner(f"{picked} 목록 {count}종목의 지금 값을 받는 중입니다…"):
                try:
                    st.session_state[cache_key] = fetch_prices(market, codes)
                except Exception:
                    st.session_state[cache_key] = {}
        st.session_state[fetched_at_key] = datetime.now(_SEOUL).strftime("%H:%M")
    if st.button("🔄 지금 값 다시 받기", key=f"picklist_calc_{market}"):
        count = len({row.get("code") for row in shown})
        with st.spinner(f"{picked} 목록 {count}종목의 지금 값을 받는 중입니다…"):
            # ① 자동으로 못 채운 줄이 남아 있으면 여기서 한 번 더 찾아본다.
            #    (다음 거래일이 그사이에 열렸을 수 있다.)
            opens = fetch_buy_opens(market, rows)
            if opens:
                rows = store.set_buy_opens(rows, opens)
                try:
                    store.save_rows(rows, trade_date=picked, market=market)
                except Exception:
                    pass      # 못 적어도 화면 숫자는 그대로 나온다
            # ② 지금 값 — 다시 읽은 저장 줄로 보여 줄 줄을 새로 만든 뒤 그 종목으로 받는다.
            shown = _view(rows_view, picked, rows)
            st.session_state[cache_key] = fetch_prices(
                market, [row.get("code") for row in shown])
        st.session_state[fetched_at_key] = datetime.now(_SEOUL).strftime("%H:%M")
        rows = store.load_rows(picked, market)
        shown = _view(rows_view, picked, rows)
    prices = st.session_state.get(cache_key) or {}
    if prices:
        shown = store.with_profit(shown, prices)

    # 아래 표가 '지금 값을 받아 봤나'를 알아야 '—'와 '못 받음'을 가른다.
    tried = bool(st.session_state.get(fetched_at_key))
    # **날짜 밑 요약 줄은 뺐다** (2026-08-29 상하님이 캡처에 ×표로 짚어 주셨다).
    # 「2026-08-28 · 상위 테마 5개 … 순위 9 8」 · 「매수금액은 아직 없습니다 …」 ·
    # 「지금 값은 14:33 기준(30종목)입니다 …」 세 줄이었다.
    # 같은 것을 아래 표가 이미 말한다 — 갈래마다 제목과 줄 수가 있고, 매수금액은
    # 빈 칸으로 보인다. 폰에서는 이 줄이 표를 화면 밖으로 밀어냈다.
    # **계산은 그대로 둔다** — 지금 값(prices)은 위에서 이미 붙였다.

    # 파일 이름표 — 날짜·줄 수·값 받은 시각이 같으면 파일도 같다.
    stamp = f"{picked}|{len(shown)}|{st.session_state.get(fetched_at_key) or ''}"
    excel = _kept_file(st, f"j12_xlsx_{market}", stamp, lambda: store.to_excel_bytes(shown))
    # 받기 단추 두 줄을 **한 칸 안에** 담는다 (2026-09-16 상하님 지시 — 폰에서
    # "파트별 성적표 부분이 저장해 둔 28일치 밑에 들어가게"). 폰에서 차례를 바꾸려면
    # 두 줄이 같은 칸의 형제여야 한다 — 그 차례는 mobile_ui 의 폰 규칙이 바꾼다.
    # 성적표를 안 쓰는 화면에서는 이 칸을 만들지 않는다 — DOM 이 지금 그대로다.
    box = st.container(key=f"pldl_{market}") if scorecard is not None else st
    columns = box.columns(2)
    if excel:
        columns[0].download_button(
            "⬇ 엑셀로 받기 (.xlsx)", data=excel,
            file_name=f"목록_{market}_{picked}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"picklist_xlsx_{market}", width="stretch",
        )
    if scorecard is not None:
        # 「CSV로 받기」 자리다. 단추만 여기 놓고, 열린 창은 두 줄 밑에서 그린다.
        with columns[1]:
            scorecard_open = scorecard("button")
    else:
        columns[1].download_button(
            "⬇ CSV로 받기",
            data=_kept_file(st, f"j12_csv_{market}", stamp,
                            lambda: store.to_csv_bytes(shown)),
            file_name=f"목록_{market}_{picked}.csv", mime="text/csv",
            key=f"picklist_csv_{market}", width="stretch",
        )
        scorecard_open = False

    # ── **저장해 둔 날을 한꺼번에** 받는다 (2026-08-15 상하님 지시) ──────────────
    # 상하님 — "나중에 엑셀로 한꺼번에 받아서 정리해서 볼 수 있는 데이터 형식으로
    # 하려면…" 날짜마다 따로 받으면 상하님이 엑셀에서 손으로 이어 붙이셔야 한다.
    # 줄마다 **매수일 칸**이 이미 있으므로, 그대로 이어 붙이면 날짜별로 걸러 보실 수
    # 있다. 지금 값·수익·손실은 **그날 화면에서 채운 것만** 들어간다 — 여기서 새로
    # 받지 않는다(날마다 40종목씩 받으면 이 구역을 여는 데만 몇 분이 걸린다).
    every = []
    for day in dates:
        try:
            every.extend(store.load_rows(day, market) or [])
        except Exception:
            continue
    if len(dates) > 1 and every:
        # **「n일치 n줄을 한 파일로…」 안내는 뺐다** (2026-08-29 상하님 ×표).
        # 바로 밑 단추에 「저장해 둔 n일치 전부」라고 이미 적혀 있다.
        all_columns = box.columns(2)
        all_stamp = f"{dates[0]}|{len(dates)}|{len(every)}"
        all_excel = _kept_file(st, f"xlsx_all_{market}", all_stamp,
                               lambda: store.to_excel_bytes(every))
        if all_excel:
            all_columns[0].download_button(
                f"⬇ 저장해 둔 {len(dates)}일치 전부 (.xlsx)", data=all_excel,
                file_name=f"목록_{market}_전체_{dates[-1]}~{dates[0]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"picklist_xlsx_all_{market}", width="stretch",
            )
        if scorecard is None:
            all_columns[1].download_button(
                f"⬇ 저장해 둔 {len(dates)}일치 전부 (CSV)",
                data=_kept_file(st, f"csv_all_{market}", all_stamp,
                                lambda: store.to_csv_bytes(every)),
                file_name=f"목록_{market}_전체_{dates[-1]}~{dates[0]}.csv", mime="text/csv",
                key=f"picklist_csv_all_{market}", width="stretch",
            )
        # 성적표를 쓰는 화면에서는 이 자리를 **비워 둔다** (2026-09-16 상하님 지시).
    if scorecard is not None and scorecard_open:
        scorecard("panel")


    # 지금 고른 종목(있으면 그 줄에 표시가 붙는다). 없으면 None 이다.
    picked_now = st.session_state.get(pick_key(market)) if on_pick is not None else None
    hidden = 0
    for kind in store.KIND_ORDER:
        part = [row for row in shown if str(row.get("list_kind")) == kind]
        if not part:
            continue
        # 그 시장 화면에 없는 갈래는 **표로 보여 주지 않는다**(2026-08-15 상하님
        # 지적 — "저거는 없앴는데 왜 나오냐"). 파일에는 그대로 있고 엑셀·CSV로
        # 받으시면 다 들어 있다.
        if not store.should_show(kind, market):
            hidden += len(part)
            continue
        prefix = f"plpick_{market}_{kind}_" if on_pick is not None else None
        # **제목과 표를 한 덩이로 그린다** (2026-09-16 상하님 지적 — 온라인 노트북에서
        # "두 번째 표에 제목이 없다", 9월 11일·14일 두 날 다 둘째 제목만 빠졌다).
        # 예전에는 제목과 표를 st.markdown 두 번으로 나눠 그렸다. 그러면 화면 조각이
        # 둘이라, 스트림릿이 판을 다시 그리며 조각을 자리 번호로 갈아 끼울 때 제목
        # 조각만 헌 채로 남을 수 있다(제 노트북에서는 게스트·로그인, 폰·태블릿·노트북,
        # 바로 열기·날짜 바꾸기 여섯 가지로 해 봤지만 재현되지 않았다 — 원인을 못
        # 박았으므로 **제목이 표에서 떨어질 수 없게** 아예 한 조각으로 합친다).
        st.markdown(
            # 제목은 **그 시장 화면이 쓰는 말 그대로**다(2026-08-15 상하님 지시).
            f"<div class='pl-kind'>{store.kind_label(kind, market)} · {len(part)}종목</div>"
            + table_html(part, kind, tried=tried, pick_prefix=prefix,
                         picked_code=(picked_now or {}).get("code")),
            unsafe_allow_html=True,
        )
        if prefix:
            # 종목명이 누르면 대신 눌릴 **보이지 않는 단추**들. 표 바로 뒤에 둔다.
            # 자리를 안 차지하게 CSS 로 흐름 밖에 뺐다(위 pl-pick 설명 참고).
            hidden_box = st.container(key=f"plpickbox_{market}_{kind}")
            for index, row in enumerate(part):
                code = str(row.get("code") or "")
                if not code:
                    continue
                hidden_box.button(
                    code, key=f"{prefix}{index:02d}",
                    on_click=_remember_pick,
                    args=(st, market, code, str(row.get("name") or code), kind,
                          dict(row)),
                )
        # 「매수 파트」가 빈 줄은 2026-08-15 이전에 저장된 것이다. 그때는 세 파트로
        # 나누기 전 목록을 저장해서 어디서 왔는지가 파일에 없다(되돌려 못 채운다).
        if kind == "top7" and any(not str(row.get("origin") or "") for row in part):
            st.markdown(
                "<div class='pl-note'>「매수 파트」가 빈 줄은 <b>2026-08-15 이전</b>에 "
                "저장된 것입니다. 그때는 세 파트(테마 대장주·상승장·급락 후 반등장)로 "
                "나누기 <u>전</u> 목록을 저장해서 어디서 왔는지가 파일에 없습니다. "
                "그날 것을 되돌려 채울 수는 없고, <b>2026-08-15 마감 뒤 저장분부터</b> "
                "파트가 찍히고 순위도 파트마다 1·2·3으로 매겨집니다.</div>",
                unsafe_allow_html=True,
            )
        if kind_note is not None:
            try:
                note = kind_note(kind, part)
            except Exception:
                note = None
            if note:
                st.markdown(f"<div class='pl-note'>{note}</div>", unsafe_allow_html=True)

    if hidden:
        st.caption(
            f"이 날짜에는 지금 화면에 없는 옛 갈래 {hidden}줄이 더 저장돼 있습니다 — "
            "표로는 보여 드리지 않고, 위 ‘엑셀로 받기·CSV로 받기’에는 그대로 들어갑니다."
        )

    if on_pick is not None:
        # 누르기를 이어 주는 장치는 표를 다 그린 **뒤에** 심는다 — 심을 때 이미
        # 표가 화면에 있어야 첫 누름부터 받는다.
        pick_bridge(st)
        picked = st.session_state.get(pick_key(market))
        if picked and picked.get("code"):
            try:
                on_pick(str(picked.get("code")), str(picked.get("name") or ""),
                        str(picked.get("kind") or ""), picked.get("row") or {})
            except Exception as exc:
                # 세부사항 하나 때문에 목록 전체가 막히면 안 된다.
                st.caption(f"세부사항을 열지 못했습니다: {exc}")

    # 이 구역의 **맨 끝** — 여기서 바로 접을 수 있게 한다(2026-08-15 상하님 지시).
    if close is not None:
        try:
            close(open_key(market), "저장해 둔 목록 닫기")
        except Exception:
            pass          # 닫기 단추 하나 때문에 목록 전체가 막히면 안 된다
