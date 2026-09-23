"""J8 temporal integrity, accounting, failure isolation and actual page routes."""
import copy
import gzip
import hashlib
import json
import threading
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import jarvis8_data as data
import jarvis8_engine as engine


def price_frame(index, close):
    c = np.asarray(close)
    return pd.DataFrame({"Open":c*.999,"High":c*1.015,"Low":c*.985,"Close":c,
                         "Volume":np.full(len(c), 1_000_000.)}, index=index)


@pytest.fixture(scope="module")
def inputs():
    dates = pd.bdate_range(end="2026-08-18", periods=560)
    frames = {}
    for i,s in enumerate(engine.TICKERS):
        c = 100*np.exp(np.arange(len(dates))*.0008)*(1+.015*np.sin(np.arange(len(dates))/(7+i%11)))
        if i%3 == 0:
            c[-28:] *= np.linspace(.7,.78,28)
        frames[s] = price_frame(dates,c)
    q = 100*np.exp(np.arange(len(dates))*.0004)
    q[-25:] *= np.linspace(.9,.95,25)
    frames["QQQ"] = price_frame(dates,q)
    frames["SPY"] = price_frame(dates,np.linspace(100,160,len(dates)))
    long_dates = pd.bdate_range(end=dates[-1], periods=6400)
    index = price_frame(long_dates,np.linspace(100,180,len(long_dates)))
    return frames,index,dates[-1]


@pytest.fixture(scope="module")
def bundle(inputs):
    f, ix, day = inputs
    return engine.build(f,day,ix)


def test_future_prices_cannot_change_signals(inputs,bundle):
    frames, ix, day = inputs
    future_day = pd.bdate_range(start=day,periods=2)[-1]
    future = {s:pd.concat([f,price_frame([future_day],[1e9])]) for s,f in frames.items()}
    later = engine.build(future,day,ix)
    for key in ("themes","crash","momentum","independent_momentum","reversal","reference","input_hashes"):
        assert later[key] == bundle[key]


def test_reference_matches_original_observable_app(inputs):
    import jarvis3_data as j3
    frames,_,_ = inputs
    with patch.object(j3,"_download_cached",return_value=({"QQQ":frames["QQQ"]},{})):
        original=j3.crash_reference_day()
    actual=engine.reference(frames["QQQ"])
    assert actual["armed"] == original["armed"]
    assert actual["date"] == original["reference_date"]
    assert actual["today_drop"] == original["today_drop"]


def test_scores_and_dedup_are_explicit(bundle):
    assert bundle["themes"] and bundle["crash"] and bundle["reversal"]
    assert all(0<=r["score"]<=90 for r in bundle["themes"])
    assert all(0<=r["score"]<=60 for r in bundle["crash"])
    for kind in ("crash","momentum","reversal"):
        symbols=[r["ticker"] for r in bundle[kind]]
        assert len(symbols)==len(set(symbols))
    independent=bundle["independent_momentum"]
    assert independent["version"].startswith("J8-MOMENTUM-12-1-")
    assert len(independent["top5"])<=5
    assert independent["top5"]==independent["rows"][:5]
    for r in bundle["reversal"]:
        peers={p for t in engine.THEMES if t["name"] in engine.MEMBERS[r["ticker"]]
               for p in t["stocks"] if p!=r["ticker"] and p in bundle["metrics"]}
        assert r["peers"]==len(peers)


@pytest.mark.parametrize("fault",["missing_day","bad_high","zero_volume","missing_cell"])
def test_bad_data_is_excluded_without_fill(inputs,fault):
    frames,_,day=inputs
    f=frames[engine.TICKERS[0]].copy()
    if fault=="missing_day":f=f.iloc[:-1]
    elif fault=="bad_high":f.iloc[-1,f.columns.get_loc("High")]=1
    elif fault=="zero_volume":f.iloc[-1,f.columns.get_loc("Volume")]=0
    else:f.iloc[-1,f.columns.get_loc("Close")]=np.nan
    assert engine.quality(f,day)


def test_short_index_cannot_silently_enable_rise(inputs):
    frames,ix,day=inputs
    result=engine.build(frames,day,ix.tail(500))
    assert not result["rise"]["ok"] and not result["rise"]["primary_rows"]


def test_risk_deduplicates_and_never_exceeds_cash():
    rows=[{"ticker":s,"metrics":{"current":100,"atr_pct":1}} for s in engine.TICKERS[:30]]
    selected=[r["ticker"] for r in rows]*2
    result=engine.unique_risk(rows,selected,10000,5,2,100)
    assert len(result)==30
    assert sum(r["notional"] for r in result)<=10000
    assert all(r["shares"]>=0 for r in result)


def test_background_request_is_nonblocking_and_single_flight():
    cache=data.BundleCache(); release=threading.Event(); calls=[]
    def slow():
        calls.append(1);release.wait(5);return {"ok":True}
    try:
        t=time.perf_counter()
        for _ in range(100):assert cache.request(slow)["pending"]
        assert time.perf_counter()-t<.25
        release.set();cache.future.result(timeout=3)
        assert cache.request(slow)["value"]["ok"]
        assert len(calls)==1
    finally:
        release.set();cache.pool.shutdown()


def test_failure_keeps_last_good_bundle_without_busy_retry():
    cache=data.BundleCache()
    try:
        cache.request(lambda:{"ok":True,"as_of":"old"});cache.future.result(timeout=3)
        cache.request()
        cache.updated=time.monotonic()-cache.ttl-1
        cache.attempt=time.monotonic()-cache.retry-1
        cache.request(lambda:{"ok":False,"error":"provider unavailable"})
        cache.future.result(timeout=3)
        state=cache.request()
        assert state["value"]["as_of"]=="old" and state["stale"] and state["error"]
        assert not state["pending"]
    finally:cache.pool.shutdown()


def test_archive_has_prices_and_hash_matches(bundle,inputs,tmp_path):
    frames,ix,_=inputs
    path,digest=data.archive(bundle,frames,ix,tmp_path)
    raw=gzip.decompress(__import__("pathlib").Path(path).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==digest
    saved=json.loads(raw)
    assert saved["prices"]["QQQ"]["dates"][-1]==bundle["as_of"]
    changed_runtime=dict(bundle, fetched_at="a later refresh", load_seconds=99)
    again,_=data.archive(changed_runtime,frames,ix,tmp_path)
    assert again==path and len(list(tmp_path.iterdir()))==1


def test_crash_default_remains_baseline_order(bundle):
    assert bundle["crash"] == sorted(bundle["crash"], key=lambda r:(-r["baseline_score"],r["ticker"]))


def test_universe_covers_extras_and_theme_members():
    assert len(engine.TICKERS) == 199
    assert "BRK-B" in engine.TICKERS
    assert engine.MEMBERS["BRK-B"] == []
    assert all(s in engine.TICKERS for t in engine.THEMES for s in t["stocks"])


def test_benchmark_missing_bar_blocks_whole_bundle(inputs):
    frames,ix,day=inputs
    damaged=dict(frames, QQQ=frames["QQQ"].iloc[:-1])
    with pytest.raises(ValueError,match="QQQ"):
        engine.build(damaged,day,ix)


def test_volume_only_provider_bar_uses_prior_completed_day(inputs):
    frames, _, day = inputs
    next_day = pd.bdate_range(start=day, periods=2)[-1]
    partial = price_frame([next_day], [200.])
    partial.loc[next_day, ["Open", "High", "Low", "Close"]] = np.nan
    raw = pd.concat({s: pd.concat([frames[s], partial]) for s in ("SPY", "QQQ")}, axis=1)
    assert data.completed_benchmark_day(raw, next_day) == day.date()
    for column, value in zip(("Open", "High", "Low", "Close"), (190., 205., 185., 200.)):
        raw.loc[next_day, ("QQQ", column)] = value
    assert data.completed_benchmark_day(raw, next_day) == day.date()


def test_momentum_history_failure_does_not_hide_other_j8_views(inputs):
    frames, ix, day = inputs
    with patch("jarvis8_momentum.select", side_effect=ValueError("QQQ 이력 253일 미만")):
        result = engine.build(frames, day, ix)
    assert result["ok"] and result["themes"] and result["crash"]
    assert result["independent_momentum"]["ok"] is False
    assert result["independent_momentum"]["top5"] == []


def test_optional_quotes_are_lazy_and_failure_safe(bundle):
    from streamlit.testing.v1 import AppTest
    state={"value":bundle,"pending":False,"error":"","stale":False,"age_seconds":0}
    with patch("auth.sync_auth"), patch.object(data.CACHE,"request",return_value=state), \
         patch.object(data.QUOTE_CACHE,"request",return_value={"value":None,"pending":False,"error":"offline"}) as quote:
        page=AppTest.from_file("pages/8_자비스8.py",default_timeout=20)
        page.session_state["authenticated"]=True
        page.run()
        page.radio[0].set_value("21개 테마").run()
        assert quote.call_count==0
        page.checkbox[0].check().run()
        assert quote.call_count>0 and not page.exception
        assert any("갱신 실패" in x.value for x in page.warning)


def test_risk_form_and_alternative_views_work(bundle):
    from streamlit.testing.v1 import AppTest
    state={"value":bundle,"pending":False,"error":"","stale":False,"age_seconds":0}
    with patch("auth.sync_auth"),patch.object(data.CACHE,"request",return_value=state):
        page=AppTest.from_file("pages/8_자비스8.py",default_timeout=20)
        page.session_state["authenticated"]=True
        page.run();page.radio[0].set_value("위험·비용").run()
        page.multiselect[0].set_value(["NVDA","MSFT"]).run()
        assert not page.exception and len(page.dataframe)==2
        page.radio[0].set_value("다른 방법").run()
        page.radio[1].set_value("변동성 조정 모멘텀 · 이전 실험").run()
        assert not page.exception


@pytest.mark.parametrize("view",["오늘의 판단","모멘텀 스윙","21개 테마","상승장 눌림","급락 후 회복","다른 방법","위험·비용","검증 근거"])
def test_all_page_routes_run_without_network(bundle,view):
    from streamlit.testing.v1 import AppTest
    state={"value":bundle,"pending":False,"error":"","stale":False,"age_seconds":0}
    with patch("auth.sync_auth"),patch.object(data.CACHE,"request",return_value=state):
        page=AppTest.from_file("pages/8_자비스8.py",default_timeout=20)
        page.session_state["authenticated"]=True
        page.session_state["jarvis_access_role"]="guest"
        page.run()
        page.radio[0].set_value(view).run()
        assert not page.exception
        if view!="검증 근거":assert any("최신 상태" in e.value for e in page.error)


def test_pending_page_and_evidence_do_not_wait_for_data():
    from streamlit.testing.v1 import AppTest
    with patch("auth.sync_auth"),patch.object(data.CACHE,"request",return_value={"value":None,"pending":True,"error":""}) as request:
        page=AppTest.from_file("pages/8_자비스8.py",default_timeout=10)
        page.session_state["authenticated"]=True
        page.run();assert not page.exception and page.title
        before=request.call_count
        page.radio[0].set_value("검증 근거").run()
        assert not page.exception and request.call_count==before


def test_ui_never_promotes_stale_or_failed_candidates(bundle):
    import jarvis8_ui as ui
    row = {"ticker":"NVDA", "eligible_primary":True, "failed_gates":[],
           "score":100, "metrics":{}, "core_score":70, "support_score":30}
    enabled = dict(bundle, rise=dict(bundle['rise'], market={"market_status":"MARKET_ON"}))
    assert "조건 통과" in ui.selection_reason(row, "rise", enabled)["status"]
    assert "판단 보류" in ui.selection_reason(row, "rise", enabled, True)["status"]
    failed = dict(row, failed_gates=["MARKET_RISK"])
    assert "조건 미달" in ui.selection_reason(failed, "rise", enabled)["status"]
    assert "관찰" in ui.selection_reason(bundle['crash'][0], "crash", bundle)["status"]


def test_ui_reason_escapes_external_text_and_explains_score(bundle):
    import jarvis8_ui as ui
    row = dict(bundle['crash'][0], themes=['<script>alert(1)</script>'])
    html = ui.card_html(row, "crash", bundle)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert "선정 근거" in html and "다음 확인" in html and "변동성" in html
    assert "nan" not in ui.number(float('nan'))


def test_candidate_to_risk_navigation_keeps_selected_stock(bundle):
    from streamlit.testing.v1 import AppTest
    state={"value":bundle,"pending":False,"error":"","stale":False,"age_seconds":0}
    with patch("auth.sync_auth"),patch.object(data.CACHE,"request",return_value=state):
        page=AppTest.from_file("pages/8_자비스8.py",default_timeout=20)
        page.session_state["authenticated"]=True
        page.run()
        next(x for x in page.button if "회복 근거 보기" in x.label).click().run()
        assert page.radio[0].value == "급락 후 회복" and not page.exception
        ticker=page.selectbox[0].value
        next(x for x in page.button if x.key == "j8_risk_from_detail").click().run()
        assert page.radio[0].value == "위험·비용" and not page.exception
        assert page.multiselect[0].value == [ticker]
