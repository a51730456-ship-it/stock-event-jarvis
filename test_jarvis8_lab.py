import copy
from unittest.mock import patch
import pandas as pd
import pytest
from test_jarvis8 import inputs
import jarvis8_lab as lab


@pytest.fixture(scope='module')
def snapshot(inputs):
    frames, ixic, day = inputs
    return lab.original_snapshot(frames,ixic,day)


def test_original_adapter_does_not_patch_shared_functions(inputs,snapshot):
    import jarvis3_data as j3
    originals = (j3._download_cached,j3._series_metrics,j3._universe_daily,j3.crash_reference_day)
    frames, ixic, day = inputs
    again=lab.original_snapshot(frames,ixic,day)
    assert originals == (j3._download_cached,j3._series_metrics,j3._universe_daily,j3.crash_reference_day)
    assert [r['ticker'] for r in again['crash']['rows']] == [r['ticker'] for r in snapshot['crash']['rows']]


def test_original_crash_function_matches_same_input_adapter(inputs,snapshot):
    import jarvis3_data as j3
    import us_swing_selector as sw
    from jarvis8_engine import clean
    frames, ixic, day = inputs
    raw={s:clean(f,day).loc[day-pd.DateOffset(years=2):day] for s,f in frames.items()}
    prepared={s:sw._clean_frame(f) for s,f in raw.items()}
    memberships={s:[t['name'] for t in j3.US_THEMES if s in t['stocks']] for s in j3.US_LARGE_CAP_UNIVERSE}
    with patch.object(j3,'_universe_daily',return_value=(prepared,{},memberships)), \
         patch.object(j3,'_download_cached',return_value=(raw,{})), \
         patch.object(j3,'_series_metrics',side_effect=j3._series_metrics_uncached), \
         patch.object(j3,'crash_market_state',return_value={'drop_pct':snapshot['reference']['today_drop']}):
        actual=j3.find_crash_rebound_stocks(result_limit=999)
    expected=snapshot['crash']
    assert [(r['ticker'],r['score'],r['reference_date']) for r in actual['rows']] == [
        (r['ticker'],r['score'],r['reference_date']) for r in expected['rows']]
    assert actual['score_weak']==expected['score_weak'] and actual['score_blind']==expected['score_blind']


def test_experiments_preserve_candidate_pool_and_original_fields(snapshot):
    before=copy.deepcopy(snapshot)
    result=lab.compare(snapshot)
    assert snapshot==before
    for baseline,new in [('rise_original','rise2'),('crash_original','crash2')]:
        assert {r['ticker'] for r in result['models'][baseline]} == {r['ticker'] for r in result['models'][new]}
        original={r['ticker']:r['score'] for r in result['models'][baseline]}
        assert all(r['score']==original[r['ticker']] for r in result['models'][new])


def test_rise2_is_a_separate_ranking_not_renamed_original():
    rows=[{'ticker':'A','eligible_primary':True,'score':90,'total_score':90,'core_score':60},
          {'ticker':'B','eligible_primary':True,'score':80,'total_score':80,'core_score':70}]
    assert [r['ticker'] for r in lab.rise2_rows(rows)] == ['B','A']
    assert rows[0]['score']==90 and 'comparison_score' not in rows[0]
    with pytest.raises(ValueError):lab.rise2_rows([dict(rows[0],eligible_primary=False)])


def test_future_rows_do_not_change_original_selection(inputs,snapshot):
    frames,ixic,day=inputs
    next_day=day+pd.offsets.BDay()
    future={}
    for s,f in frames.items():
        extra=f.tail(1).copy();extra.index=[next_day];extra.loc[:,['Open','High','Low','Close']]*=10
        future[s]=pd.concat([f,extra])
    result=lab.original_snapshot(future,ixic,day)
    for kind,key in [('crash','rows'),('rise','primary_rows')]:
        assert [(r['ticker'],r['score']) for r in result[kind][key]] == [(r['ticker'],r['score']) for r in snapshot[kind][key]]


def test_missing_observation_does_not_fetch_network():
    state=lab.request({'as_of':'2026-09-15'})
    assert state['error'] and not state['pending']


def test_comparison_page_selects_experiments_without_changing_default(snapshot):
    from streamlit.testing.v1 import AppTest
    import jarvis8_data as data
    # Only fields used before the comparison route are needed; no production I/O.
    bundle={'as_of':snapshot['as_of'],'version':'fixture','observation':'fixture.json.gz',
            'observation_sha256':'test','excluded':{},'load_seconds':0}
    cache={'value':bundle,'pending':False,'error':'','stale':False,'age_seconds':0}
    comparison={'value':lab.compare(snapshot),'pending':False,'error':''}
    with patch('auth.sync_auth'),patch.object(data.CACHE,'request',return_value=cache), \
         patch.object(lab,'request',return_value=comparison):
        page=AppTest.from_file('pages/8_자비스8.py',default_timeout=20)
        page.session_state['authenticated']=True
        page.session_state['j8_view']='기존·실험2'
        page.run();assert not page.exception
        page.radio(key='j8_lab_family').set_value('급락 후 회복').run()
        page.radio(key='j8_lab_model_crash_original').set_value(lab.MODELS['crash2']['name']).run()
        assert not page.exception
        assert page.selectbox(key='j8_lab_ticker_crash2').value == comparison['value']['models']['crash2'][0]['ticker']


def test_original_rise_adapter_matches_unmodified_wrapper(inputs,snapshot):
    import jarvis3_data as j3
    import us_swing_selector as sw
    from jarvis8_engine import clean
    frames,ixic,day=inputs
    raw={s:clean(f,day).loc[day-pd.DateOffset(years=2):day] for s,f in frames.items()}
    daily={s:sw._clean_frame(f) for s,f in raw.items()}
    memberships={s:[t['name'] for t in j3.US_THEMES if s in t['stocks']] for s in j3.US_LARGE_CAP_UNIVERSE}
    history=clean(ixic,day).loc[day-pd.DateOffset(years=j3.IXIC_HISTORY_YEARS):]
    with patch.object(j3,'_universe_daily',return_value=(daily,{},memberships)), \
         patch.object(j3,'_download_cached',return_value=({'^IXIC':history},{})), \
         patch.object(j3,'_trim_index_history',side_effect=lambda f:f), \
         patch.object(j3,'_series_metrics',side_effect=j3._series_metrics_uncached), \
         patch.object(j3,'_save_swing_scan_in_background') as writer:
        actual=j3.find_breakout_pullback_stocks(result_limit=999,persist=False,
            universe_mode='LEGACY_RESEARCH_200',as_of=day)
        writer.assert_not_called()
    assert [(r['ticker'],r['score'],r['eligible_primary']) for r in actual['all_rows']] == [
        (r['ticker'],r['score'],r['eligible_primary']) for r in snapshot['rise']['all_rows']]
