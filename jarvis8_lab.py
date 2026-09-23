"""Separate comparison models. No writes/patches to J3, its cache, or its database.

The original selector function bytecode runs with private input adapters. This
preserves its selection/tie rules while making price inputs and the date explicit.
Neither model is promoted automatically, including after a successful study.
"""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
import threading
from pathlib import Path
from types import FunctionType
import pandas as pd

ROOT = Path(__file__).resolve().parent
VERSION = "J8-LAB-20260916.1"
MODELS = {
    "rise_original": {"name":"상승장 · 기존100", "max":100,
        "rule":"기존 필수 조건과 25/25/20/10/8/5/7, 원래 동점 순서 유지"},
    "rise2": {"name":"상승장2 · 핵심70", "max":70,
        "rule":"기존 통과 후보 그대로, 상대강도25+25와 눌림20만 사용. 보조30은 0, 재배분 없음"},
    "crash_original": {"name":"급락 · 기존100", "max":100,
        "rule":"기존 후보·40/30/20/10·동점 처리·같은 점수 내 테마 분산 유지"},
    "crash2": {"name":"급락2 · 회복60", "max":60,
        "rule":"기존 후보 그대로, 변동성40은 0. 나머지30/20/10과 기존 동점 규칙 유지"},
}


def isolated(function, replacements):
    """Keep production globals intact, including when the live app is concurrent."""
    fn = FunctionType(function.__code__, dict(function.__globals__, **replacements),
                      function.__name__, function.__defaults__, function.__closure__)
    fn.__kwdefaults__ = copy.copy(function.__kwdefaults__)
    return fn


def original_snapshot(frames, ixic, as_of):
    import jarvis3_data as j3
    import us_swing_selector as sw
    from jarvis8_engine import clean
    day = pd.Timestamp(as_of).normalize()
    raw = {s:clean(f, day).loc[day-pd.DateOffset(years=2):day] for s,f in frames.items()}
    daily = {s:sw._clean_frame(f) for s,f in raw.items()}
    history = clean(ixic, day)
    floor = day-pd.DateOffset(years=j3.IXIC_HISTORY_YEARS)
    history = history.loc[floor:] if len(history.loc[floor:]) >= 300 else history
    memberships = {s:[t['name'] for t in j3.US_THEMES if s in t['stocks']]
                   for s in j3.US_LARGE_CAP_UNIVERSE}
    meta = {"stale":False,"fetched_at":str(day.date())}
    def loader(tickers, **kwargs):
        return {s:(history if s == '^IXIC' else raw[s]) for s in tickers
                if s == '^IXIC' or s in raw}, meta
    reference = isolated(j3.crash_reference_day, {'_download_cached':loader})()
    if not reference.get('ok'):
        raise ValueError('Original crash reference unavailable: '+str(reference.get('reason')))
    market = {'ok':True,'drop_pct':reference['today_drop']}
    replacements = {
        '_universe_daily':lambda reuse_only:(daily,meta,memberships),
        '_download_cached':loader, '_download_cache_only':loader,
        '_trim_index_history':lambda f:f,
        '_series_metrics':j3._series_metrics_uncached,
        'crash_market_state':lambda:market,
        'crash_reference_day':lambda:reference,
    }
    rise = isolated(j3.find_breakout_pullback_stocks,replacements)(
        result_limit=len(j3.US_LARGE_CAP_UNIVERSE), persist=False,
        universe_mode='LEGACY_RESEARCH_200', as_of=day)
    if not rise.get('ok'):
        raise ValueError('Original rise scan unavailable: '+str(rise.get('error')))
    crash = isolated(j3.find_crash_rebound_stocks,replacements)(result_limit=len(j3.US_LARGE_CAP_UNIVERSE))
    if not crash.get('ok'):
        raise ValueError('Original crash scan unavailable')
    return {'ok':True,'as_of':str(day.date()),'version':VERSION,
            'rise':rise, 'crash':crash, 'reference':reference,
            'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                for p in ('jarvis3_data.py','us_swing_selector.py','jarvis8_lab.py')}}


def rise2_rows(rows):
    """Only ranking changes. No promotion of failed gates, no S/A grade invented."""
    import us_swing_selector as sw
    result = copy.deepcopy(rows)
    for r in result:
        if not r.get('eligible_primary'):
            raise ValueError('rise2 requires the same qualified candidate pool')
        r['original_score'] = r['score']
        r['comparison_score'] = r['core_score']
        r['comparison_max'] = 70
    # Remove total score; keep the original core/RS120/RS60/pullback/liquidity/ticker tie key.
    return sorted(result,key=lambda r:sw.candidate_sort_key(r)[2:])


def crash2_rows(rows):
    import jarvis3_data as j3
    result = copy.deepcopy(rows)
    orders = {r['key']:i for i,r in enumerate(j3.CRASH_REBOUND_RULES)}
    for r in result:
        score = j3.crash_rebound_score(r)
        r['original_score'] = r['score']
        r['score'] = float(score['score']-score['parts'][0][1])
        r['comparison_score'], r['comparison_max'] = r['score'],60
        r['_order'] = orders[r['bucket']]
    result.sort(key=lambda r:(-r['score'],int(r.get('theme_above20') or 99),
                             j3._rank_key(r)[0],j3._rank_key(r)[1],r['_order'],*j3._rank_key(r)[2:]))
    result = j3._spread_by_theme(result)
    for r in result:
        r['score'] = r['original_score']  # Preserve the original score on the copied row too.
        r.pop('_order',None)
    return result


def compare(snapshot):
    rise = snapshot['rise']['primary_rows']
    crash = snapshot['crash']['rows']
    rows = {'rise_original':rise,'rise2':rise2_rows(rise),
            'crash_original':crash,'crash2':crash2_rows(crash)}
    assert {r['ticker'] for r in rows['rise2']} == {r['ticker'] for r in rise}
    assert {r['ticker'] for r in rows['crash2']} == {r['ticker'] for r in crash}
    return dict(snapshot, models=rows)


def from_observation(bundle):
    """Recover the precise saved inputs, never fetch fresh prices for just one arm."""
    name = bundle.get('observation','')
    if not name or Path(name).name != name:
        raise ValueError('원본 입력 관측 파일이 없어 같은 자료의 비교를 만들 수 없습니다.')
    path = ROOT/'data/jarvis8/observations'/name
    raw = gzip.decompress(path.read_bytes())
    if hashlib.sha256(raw).hexdigest() != bundle.get('observation_sha256'):
        raise ValueError('관측 파일 해시가 일치하지 않습니다.')
    saved = json.loads(raw)
    if saved['as_of'] != bundle['as_of'] or saved['input_hashes'] != bundle['input_hashes']:
        raise ValueError('화면과 관측 자료의 기준이 다릅니다.')
    frames = {s:pd.DataFrame(v['values'],columns=v['columns'],index=pd.to_datetime(v['dates']))
              for s,v in saved['prices'].items()}
    ixic = frames.pop('^IXIC_LONG')
    return compare(original_snapshot(frames,ixic,bundle['as_of']))


_LOCK = threading.Lock()
_KEY = None
_CACHE = None


def request(bundle):
    """One current input's comparison, lazily run off the page thread."""
    from jarvis8_data import BundleCache
    global _KEY, _CACHE
    if not bundle.get('observation'):
        return {'value':None,'pending':False,'error':'원본 입력 저장이 없어 비교를 보류합니다.'}
    key = (bundle['observation_sha256'],VERSION)
    with _LOCK:
        if key != _KEY:
            if _CACHE is not None:
                _CACHE.pool.shutdown(wait=False,cancel_futures=True)
            _CACHE = BundleCache(ttl=3600,retry=60)
            _KEY = key
        cache = _CACHE
    return cache.request(lambda:from_observation(bundle))
