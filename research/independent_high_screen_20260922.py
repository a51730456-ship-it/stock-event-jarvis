"""Research only: fixed independent ranking screen, no imports from app engines.

Discovery on an already-seen survivor roster. NOT a replication of George/Hwang,
NOT an unseen test, NOT a deployment candidate until further validation.
Predeclared: 252-close high proximity vs 12-1 return; same eligible stock pool;
QQQ > SMA200, stock > SMA200, positive 12-1 return, 20-session dollar volume >=20m.
Current adjusted prices*volume are only a liquidity proxy, not historical notional.
Top5, 10% each, cash remainder. Same timing/exposure QQQ benchmark.
Next open entry, close exit after1/3/5/10/20 sessions; cost .2/.5/1% roundtrip.
Primary grid offset274 every21 sessions; offset+7/+14 robustness20days/.5%.
Never choose a rule based on these robustness results. No parameter search.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'output/jarvis3_audit_20260909'
OUT=ROOT/'output/independent_research/high_screen_20260922'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def features(w,symbols):
    c=w['close']; r=c.pct_change(fill_method=None)
    valid=pd.DataFrame(True,index=c.index,columns=c.columns)
    for k in ['open','high','low','close','volume']:
        valid &= w[k].notna() & w[k].gt(0)
    # Numerical tolerance only (1e-8% of close), not tolerance for bad OHLC bars.
    eps=c.abs()*1e-10
    valid &= (w['high']+eps).ge(w['open']) & (w['high']+eps).ge(c)
    valid &= (w['low']-eps).le(w['open']) & (w['low']-eps).le(c)
    # Only trailing data may exclude a stock; never screen on future availability.
    clean=valid.rolling(253,min_periods=253).sum().eq(253)
    clean &= r.abs().rolling(252,min_periods=252).max().le(.8)
    mom=c.shift(21)/c.shift(252)-1
    eligible=clean & c.gt(c.rolling(200).mean()) & mom.gt(0)
    eligible &= (c*w['volume']).rolling(20).mean().ge(20_000_000)
    eligible=eligible.reindex(columns=symbols,fill_value=False).fillna(False)
    eligible=eligible.mul(c.QQQ.gt(c.QQQ.rolling(200).mean()),axis=0).astype(bool)
    return eligible,c/c.rolling(252).max(),mom

def picks(eligible,scores,pos):
    # Stable alphabetical ties are known before any future return is read.
    row=scores.iloc[pos].reindex(eligible.columns).where(eligible.iloc[pos]).dropna()
    return row.sort_index().sort_values(ascending=False,kind='stable').head(5).index.tolist()

def path(op,cl,indices,pos,hold,cost,weights=None):
    weights=np.repeat(.1,len(indices)) if weights is None else np.asarray(weights)
    if not len(indices):return np.ones(hold)
    entry=op[pos+1,indices]; closes=cl[pos+1:pos+hold+1,indices]
    if closes.shape[0]!=hold or not np.isfinite(entry).all() or not np.isfinite(closes).all() or (entry<=0).any() or (closes<=0).any():
        raise ValueError('Selected future prices missing; no substitute or cash imputation')
    assert weights.sum()<=1
    half=cost/200
    invested=(closes/entry*weights/(1+half)).sum(axis=1)
    nav=1-weights.sum()+invested
    nav[-1]-=invested[-1]*half
    return nav

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=[SRC/f'fresh_{k}.parquet' for k in ['open','high','low','close','volume']]
    roster=ROOT/'data/jarvis8/universe.json'
    source_hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files+[roster]}
    saved=json.loads((SRC/'price_validation_summary.json').read_text(encoding='utf-8'))
    assert all(sha(p)==saved['fresh_file_hashes'][p.name] for p in files)
    w={p.stem.removeprefix('fresh_'):pd.read_parquet(p) for p in files}
    dates=w['close'].QQQ.dropna().index
    w={k:f.reindex(dates) for k,f in w.items()}
    symbols=sorted(set(json.loads(roster.read_text(encoding='utf-8'))['tickers'])-{'QQQ','SPY','^IXIC'})
    eligible,high,mom=features(w,symbols)
    columns=list(w['close']); col={s:columns.index(s) for s in columns}
    op=w['open'].to_numpy();cl=w['close'].to_numpy()
    # Arithmetic unit checks with known, independently calculable paths.
    fixture=np.full((4,1),100.)
    assert np.allclose(path(fixture,fixture,[0],0,3,.5)[-1],.9+.1*.9975/1.0025)
    missing=fixture.copy();missing[3,0]=np.nan
    try:path(fixture,missing,[0],0,3,.5)
    except ValueError:pass
    else:raise AssertionError('Missing selected price was accepted')
    # Verify ranks do not change when later rows are excluded entirely.
    for pos in [500,1500,2500]:
        e,h,m=features({k:f.iloc[:pos+1] for k,f in w.items()},symbols)
        assert picks(e,h,pos)==picks(eligible,high,pos)
        assert picks(e,m,pos)==picks(eligible,mom,pos)
    summaries=[];cycles=[];selections=[];max_arithmetic_error=0
    for offset in [0,7,14]:
        positions=list(range(274+offset,len(dates)-20,21))
        first=positions[0]+1;last=positions[-1]+20
        selected={}
        for pos in positions:
            hp=picks(eligible,high,pos);mp=picks(eligible,mom,pos)
            assert len(hp)==len(mp)
            selected[pos]={'high':hp,'momentum':mp,'qqq':['QQQ'] if hp else []}
            selections.append({'offset':offset,'day':str(dates[pos].date()),'eligible':int(eligible.iloc[pos].sum()),**selected[pos]})
        holds=[1,3,5,10,20] if offset==0 else [20]
        costs=[.2,.5,1.] if offset==0 else [.5]
        for hold in holds:
            for cost in costs:
                for method in ['high','momentum','qqq']:
                    nav=np.ones(last-first+1);equity=1.;group=[]
                    for pos in positions:
                        ss=selected[pos][method];indices=[col[s] for s in ss]
                        weights=([.1*len(selected[pos]['high'])] if ss else []) if method=='qqq' else [.1]*len(ss)
                        p=path(op,cl,indices,pos,hold,cost,weights)
                        # Independent share-count terminal return check for every cycle.
                        terminal=1-sum(weights)
                        for s,weight in zip(ss,weights):
                            shares=weight/(w['open'].iloc[pos+1][s]*(1+cost/200))
                            terminal+=shares*w['close'].iloc[pos+hold][s]*(1-cost/200)
                        err=abs(terminal-p[-1]);max_arithmetic_error=max(max_arithmetic_error,err)
                        assert err<1e-12
                        a=pos+1-first;z=a+hold
                        nav[a:z]=equity*p;equity*=p[-1];nav[z:]=equity
                        row={'offset':offset,'day':str(dates[pos].date()),'method':method,'hold':hold,'cost':cost,
                             'tickers':' '.join(ss),'exposure':sum(weights),'return_pct':float((p[-1]-1)*100)}
                        cycles.append(row);group.append(row)
                    g=pd.DataFrame(group);active=g[g.exposure>0]
                    years=(dates[last]-dates[first]).days/365.25
                    peak=np.maximum.accumulate(np.r_[1,nav])[1:]
                    def cagr(terminal):return float((terminal**(1/years)-1)*100)
                    half_results={}
                    for label,mask in [('before_2021',g.day<'2021'),('2021_on',g.day>='2021')]:
                        half_results[label+'_mean_cycle_pct']=float(g.loc[mask,'return_pct'].mean())
                    summaries.append({'offset':offset,'method':method,'hold':hold,'cost':cost,'signals':len(g),
                        'active':len(active),'basket_win_pct':float((active.return_pct>0).mean()*100),
                        'cagr_pct':cagr(equity),'mdd_pct':float((nav/peak-1).min()*100),
                        'mean_cycle_pct':float(g.return_pct.mean()),
                        'without_best3_cagr_pct':cagr(equity/np.prod(1+g.return_pct.nlargest(3)/100)),
                        **half_results})
    result={'metadata':{'version':'independent-high-screen-20260922.3','script_sha256':sha(Path(__file__)),
            'input_hashes':source_hashes,'roster_stock_count':len(symbols),
            'priced_stock_count':len(set(symbols)&set(columns)),
            'missing_roster_tickers':sorted(set(symbols)-set(columns)),
            'price_first':str(dates[0].date()),
            'price_last':str(dates[-1].date()),'first_signal':selections[0]['day'],
            'primary_last_signal':[r['day'] for r in selections if r['offset']==0][-1],
            'policy':__doc__,'checks':{'past_only_ranking_dates':3,'terminal_arithmetic_error_max':max_arithmetic_error},
            'limits':['Already-seen history and current survivors: not OOS',
            'Single provider adjusted OHLCV; original price files retained; no independent full-series validation',
            'Adjusted close times volume is a proxy, not point-in-time dollar volume',
            '252 trading-day closing high differs from exact 52-week price high and original paper',
            'No delisted roster, spread/impact, cash interest, intraday exits or intraday drawdown',
            'Offsets overlap across experiments and are not independent confirmations',
            'No positive finding alone justifies application implementation']},'summary':summaries}
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(cycles).to_csv(OUT/'cycles.csv',index=False)
    (OUT/'selections.json').write_text(json.dumps(selections,ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(summaries).query('cost==.5 and (hold==20 or (offset==0 and hold==3))').round(3).to_string(index=False))
    print('CHECKS',result['metadata']['checks'])

if __name__=='__main__':main()
