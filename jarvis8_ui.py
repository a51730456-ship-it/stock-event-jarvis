"""J8-only presentation. Reads completed bundles; never changes scores or candidates."""
from html import escape
import math


def number(value, digits=1, signed=False):
    try:
        value = float(value)
        if not math.isfinite(value):
            return "자료 없음"
        return format(value, f"+,.{digits}f" if signed else f",.{digits}f")
    except (TypeError, ValueError):
        return "자료 없음"


def stock_name(ticker):
    from jarvis3_data import STOCK_NAMES
    return STOCK_NAMES.get(ticker, ticker)


def selection_reason(row, kind, bundle, blocked=False):
    """Explain observed rule inputs, with eligibility taking priority over score."""
    from us_swing_selector import plain_state
    m = bundle.get("metrics", {}).get(row["ticker"], row.get("metrics", {}))
    failed = row.get("failed_gates", [])
    market_on = bundle.get("rise", {}).get("market", {}).get("market_status") == "MARKET_ON"
    if kind == "rise":
        qualified = bool(row.get("eligible_primary")) and not failed and market_on
        status = "조건 통과 · 매수 검토" if qualified else "조건 미달 · 관찰만"
        reasons = [
            f"3개월 수익 {number(m.get('ret60'), signed=True)}% · 6개월 {number(m.get('ret120'), signed=True)}%",
            f"신고가 돌파일 {row.get('breakout_date') or '확인 안 됨'} · 기준 고점에서 {number(row.get('pullback_pct_close'))}% 눌림",
            f"강도·눌림 {number(row.get('core_score'))}/70 · 테마·거래량 등 {number(row.get('support_score'))}/30",
        ]
        caution = " · ".join(plain_state(x) for x in failed) if failed else (
            "시장 조건 미통과" if not market_on else "마감 조건만 통과했습니다. 다음 장 가격이 달라지면 같은 매수 자리가 아닙니다.")
        next_step = "상세 차트 → 현재 가격과 눌림 유지 여부 → 실적 발표 일정 → 위험·비용 순서로 확인하세요."
        score = f"{number(row.get('score'))} / 100"
    elif kind == "crash":
        status = "낙폭 후보 · 반등 관찰"
        reasons = [
            f"급락 기준일 {bundle['reference'].get('date') or '없음'}에 52주 고점 대비 {number(row.get('reference_drop'), signed=True)}%",
            f"그 기준일 이후 {number(row.get('since_reference'), signed=True)}% · 지금 고점 대비 {number(m.get('from_high_pct'), signed=True)}%",
            f"회복 관련 {number(row.get('score'))}/60 + 변동성 {number(row.get('baseline_score', 0)-row.get('score', 0))}/40",
        ]
        caution = row.get("state", "반등 확인 필요") + ". 점수에는 크게 움직이는 성질도 들어 있어 손실 위험이 큽니다."
        next_step = "낙폭이 크다는 이유로 바로 매수하지 마세요. 재하락 여부와 하락 원인을 확인한 뒤 감당할 손실을 계산하세요."
        score = f"{number(row.get('baseline_score'))} / 100"
    elif kind == "reversal":
        status = "실험 후보 · 매수 신호 아님"
        reasons = [f"최근 20일 {number(m.get('ret20'), signed=True)}%",
                   f"같은 테마 동료 {row.get('peers')}개보다 {number(row.get('residual'), signed=True)}%p",
                   f"20일 평균 거래대금 ${number(m.get('avg_dollar_volume'), 0)}"]
        caution = "싸진 것과 나빠진 것은 다릅니다. 실적 악화·악재 원인은 자동 확인하지 않습니다."
        next_step = "하락 원인을 먼저 조사하세요. 이 목록은 기존 두 전략을 대신하는 추천이 아닙니다."
        score = "별도 실험"
    else:
        status = "실험 후보 · 매수 신호 아님"
        reasons = [f"최근 1개월을 뺀 12개월 수익 {number(row.get('momentum'), signed=True)}%",
                   f"수익 ÷ 연율 변동성 {number(row.get('risk_adjusted'), 2)}",
                   "종목과 QQQ가 각각 200일 평균 위"]
        caution = "과거 강세가 이어진다는 보장은 없습니다. 몇 번의 큰 상승에 성과가 집중됐습니다."
        next_step = "추격 전에 최근 상승 폭을 확인하세요. 새 자료에서 관찰 중인 실험 목록입니다."
        score = "별도 실험"
    if blocked:
        status = "과거 자료 · 현재 판단 보류"
        next_step = "자료를 새로 확인하세요. 최신 마감 자료가 확보되기 전에는 현재 추천으로 읽지 마세요."
    return dict(status=status, reasons=reasons, caution=caution, next_step=next_step,
                score=score, metrics=m)


def card_html(row, kind, bundle, blocked=False, rank=None):
    p = selection_reason(row, kind, bundle, blocked)
    m = p["metrics"]
    ticker = row["ticker"]
    theme = " · ".join(row.get("themes") or []) or "확장 검색 종목"
    tone = "mint" if kind == "rise" and "조건 통과" in p["status"] else "amber"
    if blocked:
        tone = "muted"
    facts = "".join(f"<li>{escape(str(x))}</li>" for x in p["reasons"])
    return f'''<article class="j8-stock {tone}" translate="no">
      <div class="j8-card-top"><span class="j8-badge">{escape(p['status'])}</span><span class="j8-rank">{rank or ''}</span></div>
      <div class="j8-stock-title"><strong>{escape(stock_name(ticker))}</strong><span>{escape(ticker)}</span></div>
      <div class="j8-muted">{escape(theme)}</div>
      <div class="j8-price">${number(m.get('current'), 2)} <span>조정종가 · 순위 점수 {escape(p['score'])}</span></div>
      <div class="j8-label">선정 근거</div><ul>{facts}</ul>
      <div class="j8-caution"><b>주의</b> {escape(p['caution'])}</div>
      <div class="j8-next"><b>다음 확인</b> {escape(p['next_step'])}</div>
    </article>'''


def render_candidates(st, bundle, rows, kind, blocked=False, limit=3):
    if not rows:
        text = "조건을 통과한 종목이 없습니다. 억지로 종목을 고르지 말고 다음 마감 자료를 기다리세요." if kind == "rise" else "해당 조건의 후보가 없습니다. 다른 조건의 종목을 이 전략의 후보로 대신 표시하지 않습니다."
        st.html(f'<div class="j8-empty" translate="no">{text}</div>')
        return
    content = "".join(card_html(r, kind, bundle, blocked, i+1) for i,r in enumerate(rows[:limit]))
    st.html(f'<div class="j8-card-grid" translate="no">{content}</div>')


def overview_html(bundle, blocked=False):
    rise = bundle["rise"]
    market_on = rise.get("market", {}).get("market_status") == "MARKET_ON"
    count = len(rise["primary_rows"])
    if blocked:
        headline, detail, tone = "자료 확인 전에는 매수 판단을 보류하세요", "아래 종목은 과거 관찰 자료입니다. 새로 확인한 마감 자료가 필요합니다.", "amber"
    elif not rise.get("ok"):
        headline, detail, tone = "시장 자료가 부족해 상승장 판단을 보류합니다", rise.get("error", "시장 자료 확인 필요"), "amber"
    elif market_on and count:
        headline, detail, tone = f"상승장 눌림 후보 {count}개를 먼저 살펴보세요", "신고가 이후 눌림과 강도 조건을 통과했습니다. 종목별 근거와 현재 가격을 확인한 뒤 매수를 검토하세요.", "mint"
    elif market_on:
        headline, detail, tone = "시장 조건은 통과했지만, 눌림 후보는 없습니다", "테마 순위가 높아도 매수 자리가 생긴 것은 아닙니다. 조건에 맞는 종목이 나올 때까지 기다립니다.", "amber"
    else:
        headline, detail, tone = "상승장 눌림 매수는 기다릴 때입니다", "상승장 시장 조건이 미달입니다. 급락 후보가 있다면 회복 과정을 관찰하되 매수 신호로 읽지 마세요.", "amber"
    crash = f"{len(bundle['crash'])}개 관찰" if bundle['reference']['armed'] else "급락 기준 없음"
    shortlist = ""
    if not blocked and rise.get("ok") and market_on and count:
        names = " · ".join(f"{stock_name(r['ticker'])} ({r['ticker']})" for r in rise['primary_rows'][:3])
        shortlist = f'<div class="j8-shortlist">먼저 볼 종목 <strong>{escape(names)}</strong></div>'
    return f'''<section class="j8-decision {tone}" translate="no"><div class="j8-eyebrow">01 · 오늘의 판단</div>
      <h2>{headline}</h2>{shortlist}<p>{escape(detail)}</p>
      <div class="j8-status-grid"><div><span>상승장 시장 조건</span><b>{'보류' if blocked else ('통과' if market_on else '미달')}</b></div>
      <div><span>급락 후 회복</span><b>{crash}</b></div><div><span>QQQ · 52주 고점 대비</span><b>{number(bundle['reference']['today_drop'], signed=True)}%</b></div>
      <div><span>자료 검사 통과</span><b>{bundle['valid']} / {bundle['total']}종목</b></div></div></section>'''


STYLE = '''<div class="j8-mount" translate="no"></div><style>
body:has(.j8-mount) [data-testid="stAppViewContainer"]{background:#081321;color:#e5edf7}
body:has(.j8-mount) [data-testid="stHeader"]{background:#081321;border-bottom:1px solid #1c3249}
body:has(.j8-mount) .block-container{max-width:1320px;padding-top:3.3rem;padding-bottom:3rem}
body:has(.j8-mount) h1{font-size:clamp(1.7rem,3vw,2.35rem);letter-spacing:-.04em;color:#f2f6fd;padding-bottom:.25rem}
body:has(.j8-mount) h2,body:has(.j8-mount) h3{color:#dceafb;letter-spacing:-.025em}
body:has(.j8-mount) [data-testid="stCaptionContainer"],body:has(.j8-mount) [data-testid="stCaptionContainer"] p{color:#a6bad2!important}
body:has(.j8-mount) [data-testid="stExpander"]{background:#112338;border-color:#334b65;color:#dceafb}
body:has(.j8-mount) [data-testid="stExpander"] summary p{color:#dceafb}
body:has(.j8-mount) .stMarkdown p,body:has(.j8-mount) .stMarkdown li{color:#cad9eb}
body:has(.j8-mount) .stRadio [role="radiogroup"]{gap:8px;flex-wrap:wrap}
body:has(.j8-mount) .stRadio label{background:#13263c;border:1px solid #30455d;border-radius:9px;padding:8px 12px;margin:0}
body:has(.j8-mount) .stRadio label:has(input:checked){background:#194465;border-color:#62bfff}
body:has(.j8-mount) .stRadio label p{color:#e7effa!important;font-size:.92rem}
body:has(.j8-mount) .stRadio label>div:first-child{display:none}
body:has(.j8-mount) [data-testid="stBaseButton-secondary"]{background:#12283f;border:1px solid #395872;color:#e4effb;border-radius:9px}
body:has(.j8-mount) [data-testid="stBaseButton-primary"]{background:#086b52;border:1px solid #29bd90;color:white}
.j8-decision,.j8-stock,.j8-theme{border:1px solid #294966;border-radius:15px;background:linear-gradient(135deg,#102a43,#0b1a2d);color:#e5edf7}
.j8-decision{padding:23px;margin:6px 0 20px;border-top:3px solid #efb866}
.j8-decision.mint{border-top-color:#48d6aa}
.j8-eyebrow,.j8-label{font-size:.78rem;font-weight:800;letter-spacing:.08em;color:#7ecaff}
.j8-decision h2{font-size:clamp(1.25rem,2.5vw,1.8rem);line-height:1.4;margin:10px 0;word-break:keep-all}
.j8-decision p{color:#becfe3;line-height:1.7;margin:0 0 18px}
.j8-shortlist{color:#a9c7df;font-size:.87rem;margin:8px 0 12px}.j8-shortlist strong{color:#87eac6;display:block;font-size:1.13rem;margin-top:5px}
.j8-status-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,125px),1fr));gap:12px;border-top:1px solid #29445f;padding-top:16px}
.j8-status-grid span{display:block;font-size:.79rem;color:#a4bad3}
.j8-status-grid b{display:block;font-size:1.2rem;margin-top:6px}
.j8-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,285px),1fr));gap:14px;margin:10px 0 16px}
.j8-stock{padding:19px;min-width:0;border-top:3px solid #f2b76b;overflow-wrap:anywhere}
.j8-stock.mint{border-top-color:#42cfaa}.j8-stock.muted{border-top-color:#8b9aab}
.j8-card-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.j8-badge{font-size:.76rem;color:#ffd397;background:#a3621726;border:1px solid #795c37;border-radius:6px;padding:4px 7px;font-weight:700}
.mint .j8-badge{color:#81ecc6;background:#15806626;border-color:#2d7863}
.j8-rank{color:#a6bdd6;font-size:.8rem}.j8-stock-title{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin:16px 0 5px}
.j8-stock-title strong{font-size:1.35rem;color:#f4f8ff}.j8-stock-title span{color:#8cb8de;font-size:.9rem}
.j8-muted{color:#9bb3cc;font-size:.79rem;line-height:1.6}.j8-price{font-size:1.25rem;color:#e9f3ff;margin:14px 0 18px;font-weight:800}
.j8-price span{display:block;font-size:.77rem;color:#96b1cf;font-weight:400;margin-top:4px}
.j8-stock ul{margin:8px 0 16px;padding-left:18px;font-size:.88rem;color:#d0deed;line-height:1.8}
.j8-caution,.j8-next{font-size:.83rem;line-height:1.7;padding-top:12px;border-top:1px solid #2a4059;margin-top:12px;color:#c1d1e4}
.j8-caution b{color:#f4c384}.j8-next b{color:#73c9ff}.j8-empty{border:1px dashed #3b536c;border-radius:12px;padding:22px;color:#b9cce0;background:#102035;line-height:1.8}
.j8-theme{padding:17px}.j8-theme strong{font-size:1.1rem;display:block;margin:8px 0}.j8-theme p{margin:5px 0;color:#c5d5e6;font-size:.87rem}
.j8-up{color:#7bc6ff}.j8-down{color:#ff9090}
</style>'''

# Only attributes on the J8 main region are changed. Restore them on page departure;
# never suppress React errors or patch browser DOM methods globally.
TRANSLATION_GUARD = '''<script>
(() => {
  if (window.__j8TranslationGuard) return;
  const marker = document.querySelector('.j8-mount');
  if (!marker) return;
  const main = marker.closest('[data-testid="stMain"]') || marker.closest('main');
  if (!main) return;
  const oldTranslate = main.getAttribute('translate'), oldLang = main.getAttribute('lang');
  main.setAttribute('translate','no'); main.setAttribute('lang','ko');
  const observer = new MutationObserver(() => {
    if (document.querySelector('.j8-mount')) return;
    oldTranslate === null ? main.removeAttribute('translate') : main.setAttribute('translate',oldTranslate);
    oldLang === null ? main.removeAttribute('lang') : main.setAttribute('lang',oldLang);
    observer.disconnect(); delete window.__j8TranslationGuard;
  });
  observer.observe(document.body,{childList:true,subtree:true});
  window.__j8TranslationGuard = observer;
})();
</script>'''
