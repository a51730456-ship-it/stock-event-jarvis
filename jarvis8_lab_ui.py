"""Explain parallel models and their evidence without changing the current default."""
import json
import hashlib
from pathlib import Path
import pandas as pd
import jarvis8_lab as lab
from jarvis8_ui import stock_name

NAMES = {**{k:v['name'] for k,v in lab.MODELS.items()},
         'j8_rise':'현재 J8 상승장', 'j8_crash_baseline':'현재 J8 급락',
         'j8_crash_recovery60':'J8 회복60 · 이전 실험',
         'j8_momentum':'모멘텀 · 별도 전략', 'j8_reversal':'반전 · 별도 전략'}


def research(st):
    path=Path(__file__).resolve().parent/'data/jarvis8/lab_study.json'
    st.subheader('실제로 돌린 비교 결과')
    if not path.exists():
        st.info('원본 동점 규칙까지 맞춘 추가 비교를 계산 중입니다. 아래 모델을 검증 통과로 읽지 마세요.')
        return
    result=json.loads(path.read_text(encoding='utf-8'))
    m=result['metadata']
    st.caption(f"{m['first_signal']}~{m['last_signal']} · {m['completed']}개 기준일 · {m['version']}")
    root = Path(__file__).resolve().parent
    changed = [name for name, digest in m.get('signature', {}).items()
               if name.endswith('.py') and
               (not (root / name).exists() or
                hashlib.sha256((root / name).read_bytes()).hexdigest() != digest)]
    if changed:
        st.warning('저장된 실험 이후 코드가 바뀌었습니다. 아래 성적은 실험 당시 버전의 결과이며, 현재 코드의 재검증 결과가 아닙니다. 차이: ' + ', '.join(changed))
    st.write('같은 기준일에 다음 날 시가로 진입하고 선택한 기간의 종가에 청산했습니다. 종목당 계좌의 10%만 투자하고 나머지는 현금입니다. 21거래일 간격의 표본이며 매일 발생한 신호 전체 검사는 아닙니다.')
    hold=st.selectbox('비교 보유기간 (거래일)',[1,3,5,10,20],index=4,key='j8_lab_hold')
    cost=st.selectbox('비교 왕복 비용 (%)',[0.,.2,.5,1.],index=2,key='j8_lab_cost')
    k=st.selectbox('선택 종목 수 상한',[1,5],index=1,key='j8_lab_k',
                   format_func=lambda n:f'상위 {n}개 · 최대 투자 {n*10}%')
    all_rows=pd.DataFrame(result['summary'])
    rows=all_rows[(all_rows.hold==hold)&(all_rows.cost==cost)&(all_rows.k==k)].copy()
    rows['method']=rows.method.map(NAMES)
    cols={'method':'방법','active':'후보 있던 횟수','win_pct':'묶음 수익 비율 %',
          'cagr_pct':'계좌 연복리 %','mdd_pct':'최대 하락 %'}
    st.dataframe(rows[list(cols)].rename(columns=cols).round(2),hide_index=True,width='stretch')
    st.caption('수익 비율은 개별 종목 승률이 아니라 선택한 묶음의 비용 후 수익 비율입니다. 최대 하락은 종가 기준이며 장중 손실은 제외합니다.')
    pairs=pd.DataFrame(result['paired'])
    pairs=pairs[(pairs.hold==hold)&(pairs.cost==cost)&(pairs.k==k)]
    for new,title in [('rise2','상승장2'),('crash2','급락2')]:
        r=pairs[pairs.new==new].iloc[0]
        if r.changed_dates==0:
            st.info(f"{title}: {int(r.dates)}회 중 상위 후보와 순서가 달라진 날이 0회입니다. 이 표본에서는 새 순위의 효과를 구별할 수 없습니다.")
        else:
            difference=r.mean_cycle_difference_pp
            st.write(f"**{title}** — 상위 후보 또는 순서가 달라진 날 {int(r.changed_dates)}/{int(r.dates)}회. 관측 1회당 계좌 수익 차이 {difference:+.3f}%p. 연도별 평균 차이를 재표본화한 탐색 범위 {r.annual_block_low_pp:+.3f}~{r.annual_block_high_pp:+.3f}%p.")
    with st.expander('특정 대박 의존도 · 비교의 한계'):
        st.dataframe(rows[['method','cagr_pct','without_best3_cagr_pct']].rename(columns={
            'method':'방법','cagr_pct':'원 연복리 %','without_best3_cagr_pct':'최고 이익 3구간 제외 %'}).round(2),hide_index=True,width='stretch')
        st.write('현재 살아남은 종목 명부와 이미 살펴본 자료를 사용한 탐색입니다. 미래 검증이 아닙니다. 원본의 선정과 동점 규칙을 복원했지만, 위 매수·매도·자금 배분은 비교를 위해 추가한 가정입니다.')
        st.write(f"원본이 순위 해석을 경고한 구간도 기록했습니다: 깊은 급락 {m['blind_dates']}회, 얕은 급락 {m['weak_dates']}회. 이 표는 경고를 임의의 현금 전환 규칙으로 바꾸지 않았습니다.")
        st.caption('원본과 실험2의 같은 후보 비교와, 후보 조건 자체가 다른 모멘텀·반전 비교를 구분하세요. 가장 좋은 숫자 하나만으로 실전 사용을 결정하지 않습니다.')
    if m['missing']:
        st.error('미래 보유가격이 누락된 조합이 있습니다. 해당 계좌의 성과는 확정하지 않았습니다.')
    st.download_button('비교 규칙·결과 내려받기',path.read_bytes(),'jarvis8_lab_study.json','application/json')


def render(st,bundle,blocked):
    st.subheader('기존 배점은 그대로 · 실험2와 나란히')
    st.write('원본 후보 선정·동점 규칙을 저장된 동일 입력에서 재현합니다. 현재 자비스8 기본 목록도 바뀌지 않습니다. 실험2는 따로 선택해 보는 연구 항목입니다.')
    family=st.radio('비교할 전략',['상승장 눌림','급락 후 회복'],horizontal=True,key='j8_lab_family')
    keys=('rise_original','rise2') if family=='상승장 눌림' else ('crash_original','crash2')
    with st.expander('왜 이 실험을 하나 · 배점표',expanded=True):
        if keys[0]=='rise_original':
            st.dataframe(pd.DataFrame({'항목':['3개월 강도','6개월 강도','눌림','테마','거래량','상승 종목 비율','반등'],
                         '기존':[25,25,20,10,8,5,7],'상승장2':[25,25,20,0,0,0,0]}),hide_index=True,width='stretch')
            st.write('가설: 보조30점이 강도·눌림으로 고른 후보의 순위를 바꾸는 것이 실제로 도움이 되는가? 필수 조건은 유지하고 점수만 비교합니다. 빠진 점수는 재배분하지 않습니다.')
        else:
            st.dataframe(pd.DataFrame({'항목':['변동성','테마 추세','동반 후보','테마 6개월 강도'],
                         '기존':[40,30,20,10],'급락2':[0,30,20,10]}),hide_index=True,width='stretch')
            st.write('가설: 크게 움직이는 종목에 주는40점을 빼면 위험과 수익이 개선되는가? 기존 후보·동점 규칙은 유지합니다. 앞선 단순 동점 실험에서는 개선되지 않았습니다.')
    state=lab.request(bundle)
    if state.get('error'):
        st.warning('현재 종목 비교 보류: '+state['error'])
    if state.get('pending'):
        st.info('저장된 원본 입력으로 두 순서를 계산하고 있습니다. 추가 시세 다운로드는 하지 않습니다.')
    value=state.get('value')
    if value:
        if blocked:
            st.warning('과거 자료의 순위 비교입니다. 현재 매수 판단으로 사용하지 마세요.')
        if keys[0]=='crash_original':
            if value['crash']['score_blind']:
                st.error('원본 경고: 깊은 급락으로 순위를 신뢰하기 어려운 구간입니다. 아래 숫자는 계산값이며 매수 우선순위로 읽지 마세요.')
            elif value['crash']['score_weak']:
                st.warning('원본 경고: 얕은 급락 구간으로 점수의 구분력이 약합니다.')
        selected=st.radio('살펴볼 모델',[lab.MODELS[k]['name'] for k in keys],horizontal=True,key='j8_lab_model_'+keys[0])
        for column,key in zip(st.columns(2),keys):
            with column:
                column.markdown('**'+lab.MODELS[key]['name']+'**')
                rows=value['models'][key]
                if rows:
                    table=pd.DataFrame([{'순위':i+1,'종목':f"{stock_name(r['ticker'])} · {r['ticker']}",
                        f"점수 /{lab.MODELS[key]['max']}":r.get('comparison_score',r['score'])}
                        for i,r in enumerate(rows[:10])])
                    column.dataframe(table.round(1),hide_index=True,width='stretch')
                else:column.info('조건에 맞는 후보 없음')
        key=next(k for k in keys if lab.MODELS[k]['name']==selected)
        rows=value['models'][key]
        if rows:
            ticker=st.selectbox('선택한 모델의 종목 근거',[r['ticker'] for r in rows],key='j8_lab_ticker_'+key)
            r=next(r for r in rows if r['ticker']==ticker)
            parts=r.get('score_parts') if keys[0]=='rise_original' else None
            if parts is None:
                import jarvis3_data as j3
                parts=j3.crash_rebound_score(r)['parts']
            if key=='rise2':parts=[(a,b if i<3 else 0,c if i<3 else 0,d) for i,(a,b,c,d) in enumerate(parts)]
            elif key=='crash2':parts=[(a,0 if i==0 else b,0 if i==0 else c,d) for i,(a,b,c,d) in enumerate(parts)]
            st.dataframe(pd.DataFrame(parts,columns=['항목','획득','배점','계산 근거']),hide_index=True,width='stretch')
            st.caption('70점·60점을 100점으로 환산하거나 기존 S/A 등급을 붙이지 않습니다. 서로 다른 만점의 점수 크기를 승률처럼 비교하지 마세요.')
    research(st)
    return state
