"""J7 isolation, bounded async reads and source-preserving screen contracts."""
import copy
import sqlite3
import threading
import time
from unittest.mock import patch

import pytest

import jarvis7_app as app
import jarvis7_data as data
import jarvis7_store as store
import jarvis7_ui as ui
from test_jarvis3_page import _market, _ranking, _leaders, _fear_greed, _chart_bundle, _intraday_chart_payload


def finish(cache,key,loader):
    cache.request(key,loader)
    cache.entries[key]["future"].result(timeout=5)
    return cache.request(key,loader)


def test_first_render_never_waits_for_slow_network_and_deduplicates():
    cache=data.ReadCache(workers=1)
    release=threading.Event()
    calls=[]
    def slow():
        calls.append(1)
        release.wait(3)
        return {"ok":True,"price":123}
    try:
        start=time.perf_counter()
        for _ in range(50):
            result=cache.request(("market",),slow)
            assert result.pending
        assert time.perf_counter()-start<.2
        release.set()
        cache.entries[("market",)]["future"].result(timeout=2)
        assert cache.request(("market",),slow).value["price"]==123
        assert calls==[1]
    finally:
        release.set()
        cache.pool.shutdown()


def test_failed_refresh_keeps_old_value_and_does_not_retry_on_every_poll():
    cache=data.ReadCache()
    try:
        key=("market",)
        finish(cache,key,lambda:{"ok":True,"score":75})
        cache.invalidate(key)
        fail=lambda:{"ok":False}
        result=finish(cache,key,fail)
        assert result.value["score"]==75 and result.failed and result.stale
        assert not result.pending
        result.value["score"]=0
        assert cache.request(key,fail).value["score"]==75
    finally:
        cache.pool.shutdown()


def test_cache_evicts_completed_entries():
    cache=data.ReadCache(capacity=3)
    try:
        for i in range(8):
            finish(cache,(i,),lambda:{"ok":True})
        assert len(cache.entries)<=3
    finally:
        cache.pool.shutdown()


def test_partial_quote_failure_retains_last_price_for_failed_symbol():
    cache=data.ReadCache()
    try:
        key=("cards",("NVDA","AMD"))
        finish(cache,key,lambda:{"NVDA":{"price":100},"AMD":{"price":200}})
        cache.invalidate(key)
        result=finish(cache,key,lambda:{"NVDA":{"price":None},"AMD":{"price":201}})
        assert result.value["NVDA"]=={"price":100,"stale":True}
        assert result.value["AMD"]["price"]==201
    finally:
        cache.pool.shutdown()


def test_completed_session_score_not_replaced_with_live_score():
    market={**_market(),"score":90,"previous_market":{"ok":True,"score":65,"regime":"상승 신호 우세","trade_date":"2026-09-04"}}
    assert data.market_assessment(market)["score"]==65
    assert "2026-09-04" in data.market_assessment(market)["basis"]
    assert data.market_assessment({})["score"] is None


def test_watchlist_writes_only_j7_and_preserves_source_and_reports(tmp_path):
    path=tmp_path/'test.sqlite3'
    def connect():
        conn=sqlite3.connect(path)
        conn.row_factory=sqlite3.Row
        return conn
    with connect() as conn:
        conn.executescript("CREATE TABLE reports (id INTEGER, day_conclusion TEXT); INSERT INTO reports VALUES (1,'[테스트]'); CREATE TABLE jarvis3_briefing_stocks (group_name TEXT,position INTEGER,ticker TEXT,stock_name TEXT); INSERT INTO jarvis3_briefing_stocks VALUES ('selected',1,'NVDA','NVIDIA');")
    with patch.object(store,'connect',connect):
        assert store.watchlist()["selected"][0]["ticker"]=="NVDA"
        with connect() as conn:
            assert not store._exists(conn,"jarvis7_settings") # reading doesn't write
        store.edit("replace","AMD",slot=0)
        store.edit("add","MSFT","Microsoft")
        assert store.watchlist()["selected"][0]["ticker"]=="AMD"
        store.edit("remove","MSFT")
        assert all(r["ticker"]!='MSFT' for r in store.watchlist()["extra"])
        with connect() as conn:
            assert conn.execute('SELECT ticker FROM jarvis3_briefing_stocks').fetchone()[0]=='NVDA'
            assert conn.execute('SELECT count(*) FROM reports').fetchone()[0]==1


def source(kind,*args):
    if kind=='market':return _market()
    if kind=='ranking':return _ranking()
    if kind=='watch':return copy.deepcopy(store.DEFAULTS)
    if kind=='cards':return {t:{"price":150.,"change_pct":1.2,"chart_today":[149,150,151]} for t in args[0]}
    if kind=='fear':return _fear_greed()
    if kind=='drawdown':return {"ok":True,"drawdown_pct":-2.6,"high":20000,"state":"고점 근처"}
    if kind=='sparks':return {}
    if kind=='leaders':return _leaders()
    if kind=='stock':return {"ok":True,"row":_leaders()["rows"][0]}
    if kind=='chart':return _intraday_chart_payload() if args[1]=='당일' else _chart_bundle()['charts'][args[1]]
    if kind=='archive':return {"day":"2026-09-04","dates":["2026-09-04"],"rows":[{"list_kind":"top7","code":"NVDA","score":85,"price":150.}]}
    if kind=='trades':return []
    if kind=='news':return {"ok":True,"items":[]}
    if kind=='search':return {"ok":True,"rows":[{"ticker":"NVDA","name":"NVIDIA"}]}
    if kind in ('top','breakout','crash'):return {"ok":True,"rows":_leaders()['rows']}
    raise AssertionError(kind)


@pytest.mark.parametrize('view',sorted(app.VIEWS))
def test_all_screens_render_with_real_source_shapes(view):
    calls=[]
    def request(key,loader,ttl=120):
        calls.append(key)
        # Avoid executing actual provider; key holds arguments except top.
        args=key[1:] if key[0]!='top' else ()
        return data.Snapshot(source(key[0],*args))
    with patch.object(data.CACHE,'request',request):
        state={"view":view,"ticker":"NVDA","theme":"반도체","query":"엔비디아"}
        markup=app.Dashboard(state).render()
        assert 'j7-nav' in markup and 'JARVIS' in markup
        assert '<script' not in markup
        if view=='home':
            assert not any(k[0] in ('chart','stock','top','crash','breakout','leaders','fear') for k in calls)
        if view=='records':
            assert not any(k[0] in ('market','ranking','chart') for k in calls)


def test_guest_does_not_receive_private_trade_records_or_management_controls():
    calls=[]
    def request(key,loader,ttl=120):
        calls.append(key[0])
        return data.Snapshot(source(key[0],*key[1:]))
    with patch.object(data.CACHE,'request',request):
        out=app.Dashboard({"view":"records"},guest=True).render()
        assert 'trades' not in calls and 'archive' not in calls
        out=app.Dashboard({"view":"watch","query":"NVDA"},guest=True).render()
        assert 'data-action="replace"' not in out
        assert '&quot;action&quot;: &quot;add&quot;' not in out


def test_untrusted_names_are_html_escaped_and_missing_values_not_zero():
    out=ui.stock_tiles([{"ticker":"NVDA","name":'<img src=x onerror=alert(1)>'}],{})
    assert '<img src=x' not in out
    assert '&lt;img' in out
    assert ui.number(None)=='—'
    assert ui.number(float('nan'))=='—'
    assert ui.number(0)=='0.00'


def test_chart_only_requests_selected_timeframe():
    with patch('jarvis3_data.get_chart_data',return_value={"ok":True}) as chart,patch('jarvis3_data.get_chart_bundle') as bundle:
        data.load('chart','NVDA','주봉')
        chart.assert_called_once_with('NVDA','주봉')
        bundle.assert_not_called()


@pytest.mark.parametrize('action',['add','remove','replace'])
def test_forged_guest_write_event_is_rejected_on_server(action):
    state={}
    with patch.object(store,'edit') as edit:
        app.apply_event({"action":action,"ticker":"NVDA"},state,guest=True)
        edit.assert_not_called()
        assert '로그인' in state['message']


def test_navigation_and_timeframe_apply_before_render_without_rerun():
    state={"view":"home"}
    assert app.apply_event({"action":"nav","view":"stock","ticker":"NVDA"},state,guest=False)
    assert state['ticker']=='NVDA' and state['view']=='stock'
    app.apply_event({"action":"timeframe","value":"주봉"},state,guest=False)
    assert state['timeframe']=='주봉'
    assert not app.apply_event({"action":"nav","view":"invalid"},state,guest=False)


def test_capacity_also_bounds_in_flight_jobs():
    cache=data.ReadCache(workers=1,capacity=2)
    release=threading.Event()
    def slow():
        release.wait(2)
        return {"ok":True}
    try:
        for i in range(10):
            cache.request((i,),slow)
        assert len(cache.entries)==2
    finally:
        release.set()
        cache.pool.shutdown()


@pytest.mark.parametrize('strategy',['breakout','crash'])
def test_strategy_detail_uses_actual_scanner_payload(strategy):
    from test_jarvis3_page import _breakout_result,_crash_result
    scan=_breakout_result() if strategy=='breakout' else _crash_result()
    row=scan['rows'][0]
    def request(key,loader,ttl=120):
        return data.Snapshot(scan if key[0]==strategy else source(key[0],*key[1:]))
    with patch.object(data.CACHE,'request',request):
        out=app.Dashboard({'view':'stock','ticker':row['ticker'],'strategy':strategy}).render()
        assert '상세 배점' in out
        assert '매수 근거' in out
        if strategy=='crash':
            from bs4 import BeautifulSoup
            table=BeautifulSoup(out,'html.parser').select_one('#j7-score-parts table')
            assert all(len(tr.find_all(['td','th']))==3 for tr in table.find_all('tr'))


def test_same_ticker_in_two_origins_opens_selected_original_row():
    row=_leaders()['rows'][0]
    rows=[{**row,'top7_origin':origin,'stock_reason':marker}
          for origin,marker in [('테마 대장주','첫 갈래 고유 근거'),('상승장','둘째 갈래 고유 근거')]]
    def request(key,loader,ttl=120):
        return data.Snapshot({'ok':True,'rows':rows} if key[0]=='top' else source(key[0],*key[1:]))
    with patch.object(data.CACHE,'request',request):
        state={'view':'stock','ticker':row['ticker'],'strategy':'top','origin':'상승장'}
        out=app.Dashboard(state).render()
        assert '둘째 갈래 고유 근거' in out and '첫 갈래 고유 근거' not in out
        assert '상승장' in ui.stock_rows(rows,strategy='top')


def test_empty_top_scan_is_a_valid_empty_result_not_failed_refresh():
    with patch('jarvis3_data.collect_top_picks',return_value={'ok':False,'rows':[],'errors':[]}),patch('jarvis3_data.breakout_scan',return_value={'ok':True,'rows':[]}):
        value=data.load('top',[],75)
        assert value['ok'] and value['rows']==[]


@pytest.mark.parametrize('guest',[False,True])
def test_streamlit_entrypoint_renders_with_login_state(guest):
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    # Each AppTest owns a fresh runtime/component registry.
    st.cache_resource.clear()
    def request(key,loader,ttl=120):
        return data.Snapshot(source(key[0],*key[1:]))
    with patch('auth.sync_auth'),patch.object(data.CACHE,'request',request):
        page=AppTest.from_file('pages/7_자비스7.py',default_timeout=15)
        page.session_state['authenticated']=True
        page.session_state['jarvis_access_role']='guest' if guest else 'owner'
        page.run()
        assert not page.exception
    st.cache_resource.clear()


@pytest.mark.parametrize('view',['home','top','stock'])
def test_guest_cannot_read_archived_or_top_candidates_through_other_routes(view):
    calls=[]
    def request(key,loader,ttl=120):
        calls.append(key[0])
        assert key[0] not in ('archive','trades','top')
        return data.Snapshot(source(key[0],*key[1:]))
    with patch.object(data.CACHE,'request',request):
        out=app.Dashboard({'view':view,'strategy':'top','ticker':'NVDA'},guest=True).render()
        assert '로그인' in out
