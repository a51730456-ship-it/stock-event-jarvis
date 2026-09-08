"""J7 screen composition; only requested sections enqueue data work."""
from __future__ import annotations

import jarvis7_data as data
import jarvis7_ui as ui


VIEWS = {"home", "watch", "market", "records", "more", "theme", "stock", "breakout", "crash", "top", "risk", "alerts", "news"}


class Dashboard:
    def __init__(self, state, guest=False):
        self.state = state
        self.guest = guest
        self.pending = False
        self.snapshots = []
        self.market = {}
        self.ranking = {}

    def get(self, kind, *args, ttl=120, key=None):
        snap = data.CACHE.request(key or (kind, *args), lambda: data.load(kind, *args), ttl)
        self.pending |= snap.pending
        if isinstance(snap.value,dict):
            self.pending |= bool(snap.value.get("pending"))
        self.snapshots.append((kind, snap))
        return snap.value

    def section(self, title, body, view="", subtitle="", symbol="bolt"):
        tail = '<div class="j7-section-footer">' + ui.button('전체 보기 ' + ui.icon("arrow"), view, cls="j7-section-link") + '</div>' if view else ''
        return '<section class="j7-panel">' + ui.heading(title, subtitle, symbol) + body + tail + '</section>'

    def ranking_data(self):
        if not self.ranking:
            self.ranking = self.get("ranking", ttl=180) or {}
        return self.ranking

    def watch_data(self):
        return self.get("watch", ttl=60) or {}

    def cards(self, stocks):
        tickers = tuple(dict.fromkeys(row["ticker"] for row in stocks))
        return (self.get("cards", tickers) or {}) if tickers else {}

    def theme_choice(self, ticker=""):
        rows = self.ranking_data().get("rows") or []
        named = self.state.get("theme")
        if named:
            return next((r for r in rows if r["name"] == named), {})
        if ticker:
            # Data module is already loaded by the worker when rankings exist.
            import jarvis3_data as j3
            matches = {t["name"] for t in j3.US_THEMES if ticker in t["stocks"]}
            return next((r for r in rows if r["name"] in matches), {})
        return {}

    def market_score(self):
        return float(self.market.get("score") or 0)

    def home(self):
        a = data.market_assessment(self.market)
        posture = a.get("posture") or "시장 자료를 확인하고 있습니다"
        words=posture.split()
        title=ui.esc(' '.join(words[:-2]))+' <em>'+ui.esc(' '.join(words[-2:]))+'</em>' if len(words)>2 else ui.esc(posture)
        reasons = ' · '.join(a.get("reasons", [])[:2])
        hero = f'<section class="j7-panel j7-hero"><div><div class="j7-eyebrow">{ui.icon("star")} 오늘의 판단</div><h1>{title}</h1><p>{ui.esc(reasons or "시장·테마·종목을 순서대로 확인하세요.")}</p><div class="j7-footnote">{ui.esc(a["basis"])}</div><div class="j7-section-footer">{ui.button("시장 분석 " + ui.icon("arrow"),"market",cls="j7-section-link")}</div></div>{ui.ring(a.get("score"),a.get("regime", "자료 확인 중"))}</section>'
        out = hero + self.indices()
        watch = self.watch_data()
        selected = watch.get("selected", [])
        cards = self.cards(selected)
        # Rank calculation starts after the small market request completes. Cards
        # can render independently; news and strategy scans are not on this path.
        ranking = self.ranking_data() if self.market else {}
        out += self.section("강한 테마 TOP 5", ui.theme_rows(ranking.get("rows", []),5),"market", "테마 점수 / 100")
        out += self.section("사용자 선정 종목",ui.stock_tiles(selected,cards),"watch",symbol="star")
        archive = (self.get("archive", "", ttl=300) or {}) if not self.guest else {}
        candidates = [r for r in archive.get("rows",[]) if r.get("list_kind") == "top7"][:4]
        quick = ''
        for row in candidates:
            t = row.get("ticker") or row.get("code") or ""
            quick += ui.button(f'<b>{ui.esc(t)}</b><strong>{ui.number(row.get("score"),1)}<small>저장 점수</small></strong><small>{ui.esc(row.get("origin") or "저장 후보")}</small>',"records",cls="j7-quick-item",label=f"{t} 저장 기록 보기")
        quick_body=('<div class="j7-quick">'+quick+'</div>' if quick else ui.notice("저장된 후보가 없습니다. 전체 심사에서 현재 후보를 확인할 수 있습니다.")) if not self.guest else ui.notice("저장 후보와 전체 후보 심사는 로그인 후 볼 수 있습니다.")
        out += self.section("빠른 보기 · 강한 종목 후보",quick_body,"top",f'{archive.get("day", "")} 저장 기준' if not self.guest else "로그인 후 이용")
        out += ui.button(ui.notice("추격 매수 전, 가격 위치와 변동성을 확인하세요.  리스크 관리 가이드 →",True),"risk",cls="j7-risk-link",label="리스크 관리 가이드")
        return out

    def indices(self):
        sparks = self.get("sparks", ttl=300) or {} if self.market else {}
        rows = self.market.get("rows",{})
        out = '<div class="j7-index-grid">'
        # The original engine provides these actual indices; do not invent FX.
        for name, ticker in (("S&P 500","^GSPC"),("나스닥100","^NDX"),("VIX","^VIX"),("다우존스","^DJI")):
            row = rows.get(ticker,{})
            change = row.get("last_session_change_pct",row.get("change_pct"))
            s = sparks.get(ticker,{})
            out += f'<div class="j7-panel j7-index"><div class="j7-index-name">{name}{ui.icon("rise")}</div><div class="j7-index-price"><b>{ui.number(row.get("current"))}</b><span class="{ui.tone(change)}">{ui.pct(change)}</span></div>{ui.spark(s.get("points"),change)}<small>{ui.esc(str(row.get("source_time") or "자료 대기")[:16].replace("T"," "))}</small></div>'
        return out+'</div>'

    def market_page(self):
        a = data.market_assessment(self.market)
        f = self.get("fear",ttl=300) or {}
        d = self.get("drawdown",ttl=300) or {}
        ranking = self.ranking_data()
        out = ui.banner("시장 분석","오늘 시장과 강한 테마를 한눈에")
        out += '<div class="j7-summary">'
        out += f'<section class="j7-panel j7-summary-card"><h3>시장 국면</h3>{ui.ring(a.get("score"),a.get("regime","자료 대기"),True)}<small>{ui.esc(a["basis"])}</small></section>'
        out += f'<section class="j7-panel j7-summary-card"><h3>공포·탐욕 지수</h3>{ui.ring(f.get("score"),f.get("rating_kr","자료 대기"),True)}<small>{ui.esc(f.get("as_of") or "CNN · 직전 완료 장")}</small></section>'
        out += f'<section class="j7-panel j7-summary-card"><h3>나스닥 고점 대비</h3><strong>{ui.pct(d.get("drawdown_pct"))}</strong><p>{ui.esc(d.get("state") or "자료 대기")}</p><small>최근 1년 종가 고점 {ui.number(d.get("high"))}</small></section></div>'
        out += self.section("강한 테마 순위 TOP 10",ui.theme_rows(ranking.get("rows",[])),subtitle=f'전체 {len(ranking.get("rows",[]))}개 테마')
        if len(ranking.get("rows",[]))>10:
            out += '<details id="j7-all-themes"><summary>전체 테마 순위 펼치기</summary>'+ui.theme_rows(ranking["rows"],100)+'</details>'
        out += ui.strategy_cards()
        out += ui.notice("이 점수는 오늘 상태 요약입니다. 앞날 예측 점수가 아닙니다.")
        out += self.market_evidence(a)
        return out

    def market_evidence(self,a):
        rows = a.get("score_breakdown",[])
        body = '<table><thead><tr><th>시장 조건</th><th>점수</th><th>상태</th></tr></thead><tbody>'
        for r in rows:
            body += f'<tr><td>{ui.esc(r.get("label"))}</td><td>{ui.number(r.get("earned"),0)} / {ui.number(r.get("max"),0)}</td><td>{ui.esc(r.get("state"))}</td></tr>'
        return '<details id="j7-market-basis"><summary>시장 국면 · 상세 배점과 근거</summary>'+body+'</tbody></table></details>'

    def watch_page(self, more=False):
        out = ui.banner("검색 / 관리","종목 검색, 관심종목과 나만의 테마를 한곳에서","search")
        query = self.state.get("query","")
        out += f'<form class="j7-search" data-action="search"><input aria-label="종목 검색" name="query" placeholder="예: 엔비디아, NVDA, 애플, 팔란티어" value="{ui.esc(query)}" maxlength="80"><button class="j7-submit" type="submit">검색</button></form>'
        watch = self.watch_data()
        selected, extras = watch.get("selected",[]), watch.get("extra",[])
        cards = self.cards(selected+extras)
        out += self.section("사용자 선정 종목",ui.stock_tiles(selected,cards),symbol="star")
        if query:
            result = self.get("search",query,ttl=600)
            found = (result or {}).get("rows",[])
            body = ui.waiting() if result is None else ''
            for r in found:
                t = r.get("ticker") or r.get("symbol") or ""
                row = ui.stock_rows([{**r,"ticker":t}],guest=True)
                add = '' if self.guest else ui.button(ui.icon("plus"),action="add",ticker=t,name=r.get("name",t),cls="j7-circle",label=f"{t} 관심종목 추가")
                body += '<div class="j7-search-row">'+row+add+'</div>'
            out += self.section("검색 결과",body or ui.notice("검색 결과가 없습니다. 티커 또는 회사명을 확인하세요."),symbol="search")
        body = ''
        for r in extras:
            t = r["ticker"]
            card = cards.get(t,{})
            detail = ui.button(f'<div class="j7-logo">{ui.logo(t)}</div><div class="j7-list-name"><b>{ui.esc(t)}</b><small>{ui.esc(r.get("name"))}</small></div><div><b>{ui.number(card.get("price"))}</b><small class="{ui.tone(card.get("change_pct"))}">{ui.pct(card.get("change_pct"))}</small></div>{ui.icon("arrow")}',"stock",ticker=t,cls="j7-list-row",label=f"{t} 종목 상세")
            remove = '' if self.guest else ui.button('×',action="remove",ticker=t,cls="j7-circle",label=f"{t} 추가 종목에서 삭제")
            body += '<div class="j7-search-row">'+detail+remove+'</div>'
        out += self.section("추가 검색 종목",body or ui.notice("검색으로 관심종목을 추가해 보세요."),symbol="search")
        if not self.guest and selected:
            options = ''.join(f'<option value="{i}">{i+1}번 · {ui.esc(r["ticker"])}</option>' for i,r in enumerate(selected))
            out += f'<details id="j7-manage"><summary>사용자 선정 종목 변경</summary><form class="j7-manage-form" data-action="replace"><select name="slot" aria-label="변경할 자리">{options}</select><input name="ticker" aria-label="새 티커" placeholder="새 티커" maxlength="16" required><input name="name" aria-label="종목 이름" placeholder="종목 이름 (선택)" maxlength="100"><button class="j7-submit" type="submit">변경 저장</button></form><small>이 설정은 자비스7에만 저장됩니다.</small></details>'
        out += ui.strategy_cards()
        out += '<div class="j7-toolbar">'+ui.button("전체 테마 순위 →","market")+ui.button("현재 후보 전체 심사 →","top")+ui.button("시장·종목 뉴스 →","news")+ui.button("리스크 관리 가이드 →","risk")+'</div><p><a href="/">앱 선택 화면 →</a></p>'
        return out

    def theme_page(self):
        theme = self.theme_choice()
        name = self.state.get("theme","")
        out = ui.banner(name or "테마 상세","테마의 흐름과 대장주를 연결해서 확인하세요",ui.theme_icon(name))
        if not theme or not self.market:
            return out + ui.waiting("테마와 시장 자료를 확인하고 있습니다")
        out += '<div class="j7-summary">'+ui.metric("테마 점수",ui.number(theme.get("score"),1),"100점 만점","gold")+ui.metric("20일 수익률",ui.pct(theme.get("ret20")),color=ui.tone(theme.get("ret20")))+ui.metric("6개월 수익률",ui.pct(theme.get("ret120")),color=ui.tone(theme.get("ret120")))+'</div>'
        result = self.get("leaders",name,self.market_score(),float(theme.get("score") or 0))
        out += self.section("테마 대장주",ui.stock_rows((result or {}).get("rows",[]),theme=name,guest=self.guest) if result else ui.waiting())
        if not self.guest:
            out += self.score_parts(theme=theme)
        return out

    def strategy_page(self, kind):
        title = "상승장 · 신고가 눌림매수" if kind=="breakout" else "급락 후 반등장 · 낙폭종목" if kind=="crash" else "강한 종목 후보"
        out = ui.banner(title,"기존 미국테마의 선정 조건과 점수를 그대로 적용합니다","rise" if kind=="breakout" else "rebound")
        if kind=="top" and self.guest:
            return out+ui.notice("전체 후보 심사는 로그인 후 볼 수 있습니다.")
        if kind=="top":
            ranking = self.ranking_data()
            if not ranking or not self.market:
                return out+ui.waiting("시장·테마 자료를 먼저 확인하고 있습니다")
            signature = tuple((r["name"],r.get("score")) for r in ranking.get("rows",[]))
            result = self.get("top",ranking["rows"],self.market_score(),key=("top",signature,self.market_score()),ttl=300)
        else:
            result = self.get(kind,ttl=300)
        if result is None:
            return out+ui.waiting("후보를 심사하고 있습니다. 다른 화면도 바로 이용할 수 있습니다.")
        for k in ("universe_warning","market_history_warning"):
            if result.get(k):
                out+=ui.notice(result[k],True)
        if result.get("score_blind") or result.get("score_weak"):
            out+=ui.notice("현재 시장 낙폭에서는 기존 배점의 구분력이 약합니다. 점수만으로 판단하지 마세요.",True)
        market = result.get("market") or {}
        for k in ("message","reason"):
            if market.get(k):
                label={"MARKET_ON":"상승장 심사 조건을 충족한 시장입니다.","MARKET_OFF":"현재 시장은 상승장 심사 조건을 충족하지 않습니다."}.get(market[k],market[k])
                out+=ui.notice(label)
        if kind=="top":
            for origin in ("테마 대장주","상승장","급락 후 반등장"):
                rows=[r for r in result.get("rows",[]) if r.get("top7_origin")==origin]
                out+=self.section(origin,ui.stock_rows(rows,strategy=kind,guest=self.guest))
            out+=ui.notice("같은 종목이 여러 갈래에 나올 수 있습니다. 각 갈래의 점수와 판정은 따로 유지합니다. ★는 테마 대장주·상승장 동시 선정을 뜻합니다.")
        else:
            out += ui.stock_rows(result.get("rows",[]),strategy=kind,guest=self.guest)
        if kind=="breakout" and result.get("watch_rows"):
            out+='<details id="j7-watch-candidates"><summary>관찰 후보 · 정식 추천 제외</summary>'+ui.stock_rows(result["watch_rows"],strategy=kind,guest=self.guest)+'</details>'
        out += ui.notice(f'조회 기준 {result.get("checked_at") or result.get("as_of_date") or "기존 스캔 기준"} · 후보가 없으면 기존 조건을 완화하지 않습니다.')
        return out

    def stock_page(self):
        ticker = self.state.get("ticker","")
        out = f'<div class="j7-detail-title"><div class="j7-logo">{ui.logo(ticker)}</div><div><small>STOCK INTELLIGENCE</small><h1>{ui.esc(ticker)}</h1></div></div>'
        out += '<div class="j7-toolbar">'+ui.button("시장분석으로 →","market")+ui.button("종목 뉴스 →","news",ticker=ticker)+'</div>'
        if not self.market:
            return out+ui.waiting("시장 자료를 확인하고 있습니다")
        strategy = self.state.get("strategy")
        if strategy=="top" and self.guest:
            return out+ui.notice("전체 후보 심사의 종목 상세는 로그인 후 볼 수 있습니다.")
        theme = {}
        row = None
        if strategy in ("breakout","crash","top"):
            if strategy == "top":
                rank = self.ranking_data()
                signature = tuple((r["name"],r.get("score")) for r in rank.get("rows",[]))
                result = self.get("top",rank.get("rows",[]),self.market_score(),key=("top",signature,self.market_score()),ttl=300) if rank else None
            else:
                result = self.get(strategy,ttl=300)
            if result is None:
                return out+ui.waiting("선택한 전략의 원래 심사 결과를 불러오고 있습니다")
            origin=self.state.get("origin","")
            row = next((r for r in result.get("rows",[])+result.get("watch_rows",[])
                        if r.get("ticker")==ticker and (not origin or r.get("top7_origin")==origin)),None)
            if row is None:
                return out+ui.notice("갱신된 심사 결과에 이 종목이 없습니다. 전략 목록에서 현재 후보를 확인하세요.")
            if strategy=="top":
                strategy={"상승장":"breakout","급락 후 반등장":"crash"}.get(row.get("top7_origin"),"")
        else:
            ranking = self.ranking_data()
            if not ranking:
                return out+ui.waiting("종목에 연결된 테마를 확인하고 있습니다")
            theme = self.theme_choice(ticker)
            if theme:
                result = self.get("leaders",theme["name"],self.market_score(),float(theme.get("score") or 0))
                if result is None:
                    return out+ui.waiting("테마 대장주 점수와 매수 근거를 불러오고 있습니다")
                row = next((r for r in result.get("rows",[]) if r.get("ticker")==ticker),None)
            else:
                result = self.get("stock",ticker,self.market_score())
                row = (result or {}).get("row")
                if result is None:
                    return out+ui.waiting("종목을 분석하고 있습니다")
        if not row:
            return out+ui.notice("현재 이 종목의 분석 자료가 없습니다.")
        m = row.get("metrics") or {}
        plan = row.get("plan") or {}
        if strategy == "crash":
            import jarvis3_data as j3
            plan = j3.crash_rebound_plan(row)
        origin_label=theme.get("name") or self.state.get("origin") or {"breakout":"상승장 · 신고가 눌림매수","crash":"급락 후 반등장 · 낙폭종목"}.get(strategy,"직접 검색")
        out += f'<p>{ui.esc(row.get("name",ticker))} · {ui.esc(origin_label)} · {ui.esc(m.get("source_time") or "기존 스캔 기준")}</p>'
        denominator = 100 if row.get("final_score") is not None or strategy else 80
        if row.get("from_search"):
            out += ui.notice("테마 밖 직접 검색 점수는 80점 만점이며, 테마 대장주의 최종점수와 직접 비교하지 않습니다.")
        out += '<div class="j7-metrics">'+ui.metric("현재가",'$'+ui.number(m.get("current")),ui.pct(m.get("change_pct")),ui.tone(m.get("change_pct")))+ui.metric("52주 고가 대비",ui.pct(m.get("from_high_pct")),'$'+ui.number(m.get("high52")),ui.tone(m.get("from_high_pct")))+ui.metric("20일 수익률",ui.pct(m.get("ret20")),"20 거래일",ui.tone(m.get("ret20")))+ui.metric("14일 변동성 (ATR)",ui.pct(m.get("atr_pct")),"현재가 대비 진폭","gold")
        out += ui.metric("6개월 수익률",ui.pct(m.get("ret120")),"120 거래일",ui.tone(m.get("ret120")))
        out += ui.metric("최종점수",ui.number(row.get("score"),1),f"/ {denominator}","gold") if not self.guest else ui.metric("조회 기준","미국장","시세 참고")
        out += '</div>'
        out += '<small>현재가는 제공된 최신 시세이며 시간외 가격을 포함할 수 있습니다. 아래 차트는 선택한 기간의 정규장 종가 기준입니다.</small>'
        if not self.guest:
            if strategy == "breakout":
                import jarvis3_data as j3
                plan = j3.breakout_plan(row)
            state = plan.get("state") or row.get("status_text") or row.get("verdict") or row.get("decision") or "기존 전략 심사 결과"
            reason = plan.get("buy_reason") or plan.get("reason") or row.get("stock_reason") or "아래 선정 근거를 확인하세요."
            out += f'<section class="j7-panel j7-decision {"danger" if "금지" in state or "제외" in state else ""}"><h2>{ui.icon("warning")} {ui.esc(state)}</h2><p>{ui.esc(reason)}</p></section>'
        timeframe = self.state.get("timeframe","당일")
        chart = self.get("chart",ticker,timeframe,ttl=120)
        tabs = ''.join(ui.button(t,action="timeframe",value=t,cls="active" if t==timeframe else "",label=f"{t} 차트") for t in ("당일","일봉","주봉","월봉"))
        out += '<section class="j7-panel"><div class="j7-chart-tabs">'+tabs+'</div>'
        if chart and chart.get("price") is not None:
            frame = chart["price"]
            values = frame["Close"].dropna()
            out += ui.spark(values.tolist(),large=True,base=chart.get("prev_close"))
            def stamp(t):
                if timeframe == "당일":
                    if getattr(t,"tzinfo",None):
                        t=t.tz_convert("America/New_York")
                    return t.strftime("%m.%d %H:%M")
                return t.strftime("%Y.%m.%d")
            if len(values):
                out += '<div class="j7-chart-labels"><span>'+ui.esc(stamp(values.index[0]))+'</span><span>'+ui.esc(stamp(values.index[-1]))+'</span></div>'
            out += f'<small>{"최근 정규장 · 뉴욕시간 · 5분봉" if timeframe=="당일" else timeframe} · 종가선</small>'
        else:
            out += ui.waiting("선택한 주기의 차트를 확인하고 있습니다")
        out += '</section>'
        if not self.guest:
            a = data.market_assessment(self.market)
            out += '<div class="j7-two">'+ui.evidence("시장 근거",[a.get("regime"),a.get("basis"),*a.get("reasons",[])[:3]],"market",ui.number(a.get("score"),0)+" / 100")+ui.evidence("테마 근거",[theme.get("name") or "선택한 전략의 테마 기준 적용",f'20일 수익률 {ui.pct(theme.get("ret20"))}',f'6개월 수익률 {ui.pct(theme.get("ret120"))}'],"shield",ui.number(theme.get("score"),1))+ui.evidence("종목 근거",[row.get("stock_reason"),f'20일 수익률 {ui.pct(m.get("ret20"))}',f'52주 고가 대비 {ui.pct(m.get("from_high_pct"))}',f'ATR {ui.pct(m.get("atr_pct"))}'],"chip")+ui.evidence("매수 근거",[plan.get("recommendation"),reason, f'확인 기준가 {ui.number(plan.get("trigger"))}',f'무효화 기준 {ui.number(plan.get("invalidation"))}'],"info")+'</div>'
            out += self.score_parts(row,theme,strategy)
        return out

    def score_parts(self,row=None,theme=None,strategy=""):
        import jarvis3_data as j3
        body = ''
        if theme and theme.get("score_parts"):
            body += self.parts_table("테마 배점",j3.GENERAL_THEME_SCORE_PARTS,theme["score_parts"])
        if row and row.get("stock_score_parts"):
            body += self.parts_table("종목 배점",j3.GENERAL_STOCK_SCORE_PARTS,row["stock_score_parts"])
            body += '<p>최종점수 = 종목점수 60% + 테마점수 40%</p>'
        elif row and row.get("score_parts") and not strategy:
            body += self.parts_table("직접 검색 조건점수",j3.LEADER_SCORE_PARTS,row["score_parts"])
        if row and strategy:
            # Strategy payloads carry their own evidence. Keep their labels/values.
            details = row.get("explanations") or {}
            if strategy == "crash":
                details = j3.crash_rebound_score(row)
                body += '<table><tr><th>항목</th><th>점수 / 배점</th><th>근거</th></tr>'
                for part in details.get("parts",[]):
                    label,earned,maximum,reason = part
                    body += f'<tr><td>{ui.esc(label)}</td><td>{ui.number(earned,1)} / {ui.number(maximum,0)}</td><td>{ui.esc(reason)}</td></tr>'
                body += '</table>'
            elif details:
                for item in details.values():
                    body += ui.evidence(item.get("title", "선정 근거"),[item.get("display_value"),item.get("status"),item.get("one_line_explanation"),item.get("detail_explanation")],"info",f'{ui.number(item.get("score"),1)} / {ui.number(item.get("max_score"),0)}')
            else:
                body += ui.notice("이 전략은 종목 상세의 조건·판정과 원래 스캔 결과를 기준으로 합니다.")
        return '<details id="j7-score-parts"><summary>상세 배점 · 선정 근거</summary>'+body+'</details>' if body else ''

    @staticmethod
    def parts_table(title,spec,values):
        out=f'<h3>{ui.esc(title)}</h3><table><tr><th>항목</th><th>점수 / 배점</th></tr>'
        for part,value in zip(spec,values):
            label,maximum=part[:2]
            out += f'<tr><td>{ui.esc(label)}</td><td>{ui.number(value,1)} / {ui.number(maximum,0)}</td></tr>'
        return out+'</table>'

    def records_page(self):
        out=ui.banner("기록 / 성과","저장된 미국테마 후보와 실제 매수 기록을 확인하세요","records")
        if self.guest:
            return out+ui.notice("개인 매수 기록과 성과는 로그인 후 볼 수 있습니다.")
        archive=self.get("archive",self.state.get("day",""),ttl=300) or {}
        dates=archive.get("dates",[])
        if dates:
            opts=''.join(f'<option value="{ui.esc(d)}" {"selected" if d==archive.get("day") else ""}>{ui.esc(d)}</option>' for d in dates)
            out+=f'<form class="j7-manage-form" data-action="date"><select name="day" aria-label="저장 날짜">{opts}</select><button class="j7-submit">기록 보기</button></form>'
        rows=archive.get("rows",[])
        if rows:
            import picklist_store
            out+='<div class="j7-panel j7-table-scroll"><table><tr><th>갈래</th><th>종목</th><th>저장 점수</th><th>저장 가격</th><th>매매유형</th></tr>'
            for r in rows:
                out+=f'<tr><td>{ui.esc(picklist_store.kind_label(r.get("list_kind",""),"US"))}</td><td>{ui.esc(r.get("ticker") or r.get("code"))}</td><td>{ui.number(r.get("score"),1)}</td><td>{ui.number(r.get("price"))}</td><td>{ui.esc(r.get("trade_style") or "미기록")}</td></tr>'
            out+='</table></div>'
            csv=base64_csv(picklist_store.to_csv_bytes(rows))
            out+=f'<p><a download="jarvis7_US_{ui.esc(archive.get("day"))}.csv" href="data:text/csv;base64,{csv}">선택한 날짜 CSV 내려받기</a></p>'
        else:
            out+=ui.notice("아직 저장된 미국테마 후보 목록이 없습니다.")
        trades=self.get("trades",ttl=60)
        if trades:
            out+= '<section class="j7-panel j7-table-scroll">'+ui.heading("실제 매수 기록",symbol="records")+'<table><tr><th>매수일</th><th>종목</th><th>매매유형</th><th>매수가</th><th>매도가</th><th>수익률</th><th>상태</th></tr>'
            for r in trades:
                out+=f'<tr><td>{ui.esc(r.get("buy_date"))}</td><td>{ui.esc(r.get("ticker"))}</td><td>{ui.esc(r.get("trade_style"))}</td><td>{ui.number(r.get("buy_price"))}</td><td>{ui.number(r.get("sell_price"))}</td><td class="{ui.tone(r.get("result_pct"))}">{ui.pct(r.get("result_pct"))}</td><td>{ui.esc(r.get("status"))}</td></tr>'
            out+='</table></section>'
        elif trades is not None:
            out+=ui.notice("저장된 실제 매수 기록이 없습니다.")
        out+=ui.notice("기존 저장 기록을 그대로 보여줍니다. 저장 점수는 당시 값이며 현재 점수로 바꾸지 않습니다.")
        return out

    def risk_page(self):
        return ui.banner("리스크 관리 가이드","점수보다 먼저, 시장과 가격 위치를 확인하세요","shield")+ui.evidence("판단 순서",["시장 국면 → 강한 테마 → 종목 → 매수 근거 순서로 확인합니다.","최종점수가 높아도 매수 조건을 충족했다는 뜻은 아닙니다.","추격 금지·추천 제외·관찰 등의 판정은 기존 미국테마 계산 결과입니다.","기준가·무효화 가격은 종목 상세의 기존 계획을 확인하세요.","장중 시세, 정규장 차트, 직전 완료 장의 시장 점수는 기준 시점이 다릅니다."],"shield")+ui.notice("매수·매도 주문을 실행하는 화면이 아닙니다. 최종 판단은 사용자가 합니다.")

    def news_page(self):
        ticker=self.state.get("ticker","")
        out=ui.banner((ticker+" · " if ticker else "미국시장 · ")+"주요 뉴스","기사 제목·요약과 원문 출처를 함께 확인하세요","info")
        out+='<div class="j7-toolbar">'+ui.button("미국시장","news")
        for r in self.watch_data().get("selected",[]):
            out+=ui.button(r["ticker"],"news",ticker=r["ticker"])
        out+='</div>'
        news=self.get("news",ticker,ttl=3) or {}
        for i,item in enumerate(news.get("items",[])):
            body=ui.evidence(item.get("brief") or item.get("headline") or "주요 뉴스",[item.get("headline"),item.get("source"),str(item.get("published_at") or "")[:16].replace("T"," ")],"info")
            url=str(item.get("url") or "")
            if url.startswith("https://"):
                body+=f'<p><a href="{ui.esc(url)}" target="_blank" rel="noopener noreferrer">원문 기사 열기 ↗</a></p>'
            out+=body
        if not news.get("items"):
            out+=ui.waiting("선택한 뉴스만 불러오고 있습니다") if news.get("pending") or self.pending else ui.notice("현재 불러올 수 있는 뉴스가 없습니다. 잠시 후 다시 확인하세요.")
        return out

    def render(self):
        view=self.state.get("view","home")
        if view not in VIEWS:
            view="home"
        if view not in ("records","risk","more","watch","news"):
            self.market=self.get("market") or {}
        from us_market_calendar import phase
        phase_name=phase()["label"]
        header=f'<header class="j7-header">{ui.button("JARVIS <b>7</b>","home",cls="j7-brand")}<span class="j7-tag">미국테마</span><span class="j7-header-spacer"></span><span class="j7-status"><i class="j7-dot"></i>{ui.esc(phase_name)}</span>{ui.button(ui.icon("search"),"watch",cls="j7-circle",label="종목 검색 열기")}{ui.button(ui.icon("bell"),"alerts",cls="j7-circle",label="자료 상태 확인")}</header>'
        routes={"home":self.home,"market":self.market_page,"watch":self.watch_page,"more":self.watch_page,"theme":self.theme_page,"stock":self.stock_page,"records":self.records_page,"risk":self.risk_page,"alerts":self.alerts_page,"news":self.news_page}
        body=routes[view]() if view in routes else self.strategy_page(view)
        if self.state.get("message"):
            body=ui.notice(self.state["message"])+body
        stale=[name for name,s in self.snapshots if s.stale or s.failed or (isinstance(s.value,dict) and s.value.get("stale"))]
        if stale:
            body+=ui.notice("일부 자료를 갱신 중이거나 조회하지 못했습니다. 표시된 이전 값의 기준 시각을 확인하세요.",True)
        nav='<nav class="j7-nav" aria-label="자비스7 메뉴">'
        active="market" if view in ("theme","stock","breakout","crash","top") else "more" if view in ("risk","alerts") else view
        for key,label,symbol in (("home","홈","home"),("watch","관심종목","star"),("market","시장분석","market"),("records","기록/성과","records"),("more","더보기","more")):
            nav+=ui.button(ui.icon(symbol)+'<span>'+label+'</span>',key,cls="active" if key==active else "",label=label)
        nav+='</nav>'
        footer='<div class="j7-footer">JARVIS 7 · 미국테마 데이터 기반 참고 정보 · 시세 제공 지연 가능</div>'
        return '<main class="j7-shell">'+header+body+footer+nav+'</main>'

    def alerts_page(self):
        out=ui.banner("자료 상태","시장과 데이터의 기준 시각을 확인하세요","bell")
        a=data.market_assessment(self.market)
        out+=ui.evidence("조회 상태",[a["basis"],f'시장 자료 시각: {self.market.get("checked_at") or "조회 중"}',"화면에서 필요한 자료만 조회하며 약 2분 주기로 갱신합니다.","갱신 실패 시 기존 자료를 유지하고 이전 자료임을 표시합니다.","이 화면은 자료 상태 안내이며 외부 알림을 발송하지 않습니다."],"info")
        out+=ui.button("표시 자료 새로 확인",action="refresh",cls="j7-submit")
        return out


def base64_csv(value):
    import base64
    return base64.b64encode(value).decode()


def apply_event(event,state,*,guest):
    """Apply a component event before rendering; never add a second app rerun."""
    if not isinstance(event,dict):
        return False
    action=event.get("action")
    if action=="nav" and event.get("view") in VIEWS:
        state.update(view=event["view"],ticker=str(event.get("ticker",""))[:16],
                     theme=str(event.get("theme",""))[:100],strategy=event.get("strategy",""),origin=str(event.get("origin",""))[:40],
                     timeframe="당일",message="")
    elif action=="timeframe" and event.get("value") in ("당일","일봉","주봉","월봉"):
        state["timeframe"]=event["value"]
    elif action=="search":
        state.update(query=str(event.get("query","")).strip()[:80],view="watch",message="")
    elif action=="date":
        state["day"]=str(event.get("day",""))[:10]
    elif action in ("add","remove","replace"):
        if guest:
            state["message"]="관심종목 저장은 로그인 후 이용할 수 있습니다."
        else:
            import jarvis7_store
            try:
                jarvis7_store.edit(action,event.get("ticker",""),event.get("name",""),int(event.get("slot",0)))
                data.CACHE.invalidate(("watch",))
                state["message"]="자비스7 관심종목을 저장했습니다."
            except Exception:
                state["message"]="저장하지 못했습니다. 티커·중복 종목·저장 연결을 확인하세요."
    elif action=="refresh":
        for source in ("market","ranking","cards","fear","drawdown","sparks","leaders","chart","stock"):
            data.CACHE.invalidate((source,))
        state["message"]="표시 자료를 새로 확인합니다."
    else:
        return False
    return True
