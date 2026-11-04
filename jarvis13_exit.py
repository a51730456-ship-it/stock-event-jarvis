"""자비스13 「✕ 자비스 닫기」 — 자비스12 와 같은 단추(jarvis12_exit 를 베낌 · 이름만 j13 · 2026-11-04 상하님 「완전 창 닫는 것도
하나 만들자」). 자비스13 은 자비스12 파일을 부르지 않는다(CLAUDE.md 0-3 ③ — 베껴 오기만).

얼린 hero_banner 는 안 고친다 — ↻ · 실시간을 한 칸 왼쪽으로 옮기는 규칙과 바깥 문서 장치(j13-exit)를 얹어 **JARVIS 13 띠에만**
✕ 를 붙인다. 누르면 확인 창 → 「닫기」: 설치한 안드로이드 앱이면 앱을 끝내고, 아니면 창 닫기를 시도한 뒤 빈 화면으로 빠져나간다.
"""

from __future__ import annotations

import json

MODULE_REVISION = 2026110403
MARK = "13"
NAME = "j13"

CSS = """<style>
/* ↻ · 실시간을 한 칸 왼쪽으로(✕ 자리 38 + 사이 8) — 보이는 동그라미 · 겹친 진짜 ↻ 단추를 같이 옮긴다 */
.j3hero-actions{right:62px!important}
div[class*="st-key-j3hero_box"] [data-testid="stElementContainer"]:has(button){right:156px!important}
/* ✕ 단추 — ↻ 와 같은 크기 · 같은 둥글기, 붉은 금테 */
.__N__x-btn{position:absolute;right:16px;top:14px;z-index:7;width:38px;height:38px;padding:0;border-radius:50%;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  border:1px solid transparent;
  background:linear-gradient(rgba(44,8,18,.92),rgba(44,8,18,.92)) padding-box,
             linear-gradient(135deg,#ffb36b,#ff4d6d 55%,#c89550) border-box;
  box-shadow:0 2px 8px rgba(0,0,0,.45),0 0 0 0 rgba(255,77,109,.0);box-sizing:border-box;min-width:0;
  transition:transform .18s ease,box-shadow .25s ease}
.__N__x-btn svg{width:16px;height:16px;stroke:#ffe1e6;stroke-width:2.6;stroke-linecap:round;
  filter:drop-shadow(0 0 4px rgba(255,90,120,.65))}
.__N__x-btn:hover,.__N__x-btn:focus-visible{transform:scale(1.08) rotate(90deg);
  box-shadow:0 2px 10px rgba(0,0,0,.5),0 0 14px 2px rgba(255,77,109,.55);outline:none}
.__N__x-btn:active{transform:scale(.94)}
/* 확인 창 */
.__N__x-scrim{position:fixed;inset:0;z-index:2147483646;background:rgba(2,8,22,.72);backdrop-filter:blur(3px);
  display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity .22s ease}
.__N__x-scrim.__N__x-on{opacity:1}
.__N__x-card{width:min(86vw,340px);border-radius:20px;padding:22px 20px 16px;text-align:center;color:#eaf4ff;
  background:radial-gradient(120% 90% at 50% 0%,#1d2f57 0%,#0b1630 70%);
  border:1px solid rgba(255,140,160,.45);box-shadow:0 18px 50px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.08);
  transform:translateY(10px) scale(.96);transition:transform .25s cubic-bezier(.34,1.56,.64,1)}
.__N__x-on .__N__x-card{transform:none}
.__N__x-ico{width:54px;height:54px;margin:0 auto 10px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 35% 30%,#ff7a8f,#b3123a);box-shadow:0 0 22px rgba(255,77,109,.55)}
.__N__x-ico svg{width:22px;height:22px;stroke:#fff;stroke-width:3;stroke-linecap:round}
.__N__x-t{font-size:1.12rem;font-weight:900;margin:0 0 4px}
.__N__x-s{font-size:.84rem;color:#9fb6d8;margin:0 0 16px;line-height:1.5}
.__N__x-row{display:flex;gap:10px}
.__N__x-row button{flex:1;height:42px;border-radius:12px;font-weight:800;font-size:.95rem;cursor:pointer}
.__N__x-stay{background:rgba(255,255,255,.06);color:#dbe8ff;border:1px solid rgba(157,204,255,.35)}
.__N__x-go{background:linear-gradient(90deg,#ff4d6d,#d61f4b);color:#fff;border:0;box-shadow:0 4px 14px rgba(214,31,75,.45)}
@media (prefers-reduced-motion: reduce){.__N__x-btn,.__N__x-card,.__N__x-scrim{transition:none!important}}
</style>"""

X_SVG = "<svg viewBox='0 0 24 24' fill='none'><path d='M6 6l12 12M18 6L6 18'/></svg>"

DEVICE = """
(function(){
  var N = '__N__', MARK = '__MARK__', SVG = __SVG__;
  var d = document;
  function exitNow(){
    try { if (window.JarvisApp && window.JarvisApp.exit) { window.JarvisApp.exit(); return; } } catch (e) {}
    try { if (window.top.JarvisApp && window.top.JarvisApp.exit) { window.top.JarvisApp.exit(); return; } } catch (e) {}
    try { window.top.close(); } catch (e) {}
    try { window.close(); } catch (e) {}
    window.setTimeout(function(){
      try { window.top.location.replace('about:blank'); } catch (e) { window.location.replace('about:blank'); }
    }, 260);
  }
  function ask(){
    if (d.querySelector('.' + N + 'x-scrim')) { return; }
    var s = d.createElement('div');
    s.className = N + 'x-scrim';
    s.innerHTML = "<div class='" + N + "x-card' role='dialog' aria-modal='true'>"
      + "<div class='" + N + "x-ico'>" + SVG + "</div>"
      + "<p class='" + N + "x-t'>자비스를 닫을까요?</p>"
      + "<p class='" + N + "x-s'>닫으면 앱에서 완전히 빠져나갑니다.<br>다시 보시려면 앱을 새로 여십시오.</p>"
      + "<div class='" + N + "x-row'><button type='button' class='" + N + "x-stay'>계속 보기</button>"
      + "<button type='button' class='" + N + "x-go'>닫기</button></div></div>";
    function shut(){ s.classList.remove(N + 'x-on'); window.setTimeout(function(){ s.remove(); }, 220); }
    s.addEventListener('click', function(ev){ if (ev.target === s) { shut(); } });
    s.querySelector('.' + N + 'x-stay').addEventListener('click', shut);
    s.querySelector('.' + N + 'x-go').addEventListener('click', function(){ shut(); exitNow(); });
    d.body.appendChild(s);
    window.requestAnimationFrame(function(){ s.classList.add(N + 'x-on'); });
  }
  function attach(){
    var heroes = d.querySelectorAll('.j3hero');
    for (var i = 0; i < heroes.length; i++) {
      var hero = heroes[i], mark = hero.querySelector('.j3hero-mark b');
      if (!mark || (mark.textContent || '').trim() !== MARK) { continue; }
      if (hero.querySelector('.' + N + 'x-btn')) { continue; }
      var b = d.createElement('span');
      b.setAttribute('role', 'button'); b.tabIndex = 0; b.className = N + 'x-btn';
      b.setAttribute('aria-label', '자비스 닫기'); b.title = '자비스 닫기';
      b.innerHTML = SVG;
      b.addEventListener('click', function(ev){ ev.preventDefault(); ev.stopPropagation(); ask(); });
      b.addEventListener('keydown', function(ev){ if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ask(); } });
      hero.appendChild(b);
    }
  }
  // 관심종목 띠에도(2026-11-04 밤 상하님 「관심종목 띠에도 넣기」) — 화면 폭마다 ↻ 크기 · 자리가 달라 숫자를 못박지 않고
  // 그 자리를 재서 ✕ 를 같은 크기로 두고, ↻ · 실시간(보이는 동그라미 · 겹친 진짜 ↻ 단추)을 그만큼 왼쪽으로 옮긴다.
  var HOME = {hero: '__HHERO__', pop: '__HPOP__', mark: '__HMARK__', actions: '__HACT__', round: '__HROUND__', box: '__HBOX__'};
  function placeHome(){
    var heroes = d.querySelectorAll(HOME.hero);
    for (var i = 0; i < heroes.length; i++) {
      var hero = heroes[i];
      if (hero.classList.contains(HOME.pop)) { continue; }
      var mark = hero.querySelector(HOME.mark);
      if (!mark || (mark.textContent || '').trim() !== MARK) { continue; }
      var acts = hero.querySelector(HOME.actions), round = hero.querySelector(HOME.round);
      if (!acts || !round) { continue; }
      var b = hero.querySelector('.' + N + 'x-btn');
      if (!b) {
        b = d.createElement('span');
        b.setAttribute('role', 'button'); b.tabIndex = 0; b.className = N + 'x-btn ' + N + 'x-home';
        b.setAttribute('aria-label', '자비스 닫기'); b.title = '자비스 닫기';
        b.innerHTML = SVG;
        b.addEventListener('click', function(ev){ ev.preventDefault(); ev.stopPropagation(); ask(); });
      b.addEventListener('keydown', function(ev){ if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ask(); } });
        hero.appendChild(b);
      }
      acts.style.removeProperty('right');
      var cs = window.getComputedStyle(acts);
      var right = parseFloat(cs.right) || 16, top = parseFloat(cs.top) || 14;
      var size = round.getBoundingClientRect().width || 38, gap = parseFloat(cs.columnGap || cs.gap) || 8;
      b.style.setProperty('right', right + 'px', 'important');
      b.style.setProperty('top', top + 'px', 'important');
      b.style.setProperty('width', size + 'px', 'important');
      b.style.setProperty('min-width', size + 'px', 'important');
      b.style.setProperty('max-width', size + 'px', 'important');
      b.style.setProperty('min-height', size + 'px', 'important');
      b.style.setProperty('flex', 'none', 'important');
      b.style.setProperty('height', size + 'px', 'important');
      acts.style.setProperty('right', (right + size + gap) + 'px', 'important');
      var boxEl = d.querySelector('div[class*="st-key-' + HOME.box + '"]');
      if (boxEl) {
        var conts = boxEl.querySelectorAll('[data-testid="stElementContainer"]');
        for (var k = 0; k < conts.length; k++) {
          var btn = conts[k].querySelector('button');
          if (!btn || (btn.innerText || '').trim() !== '↻') { continue; }
          conts[k].style.removeProperty('right');
          var r = parseFloat(window.getComputedStyle(conts[k]).right);
          if (!isNaN(r)) { conts[k].style.setProperty('right', (r + size + gap) + 'px', 'important'); }
        }
      }
    }
  }
  function all(){ attach(); placeHome(); }
  all();
  new MutationObserver(function(){ all(); }).observe(d.body, {childList: true, subtree: true});
  window.addEventListener('resize', function(){ placeHome(); });
})();
"""


def css() -> str:
    return CSS.replace("__N__", NAME)


def device() -> str:
    return (DEVICE.replace("__N__", NAME).replace("__MARK__", MARK)
            .replace("__HHERO__", ".j13h-hero").replace("__HPOP__", "j13h-hero-pop").replace("__HMARK__", ".j13h-title b")
            .replace("__HACT__", ".j13h-head-actions").replace("__HROUND__", ".j13h-round").replace("__HBOX__", "j13h_hero_box")
            .replace("__SVG__", json.dumps(X_SVG)))


def inject_html() -> str:
    """components.html 에 넣는 글 — 바깥 문서 머리에 장치를 한 번만 심는다(id j13-exit)."""
    return ("<script>(function(){try{var d=window.parent.document;"
            f"if(d.getElementById('{NAME}-exit')){{return;}}"
            f"var s=d.createElement('script');s.id='{NAME}-exit';"
            f"s.textContent={json.dumps(device())};d.head.appendChild(s);}}catch(e){{}}}})();</script>")


def render(st) -> None:
    """꾸밈(CSS)과 장치를 화면에 얹는다. 실패해도 화면은 그대로다."""
    try:
        import streamlit.components.v1 as components

        st.markdown(css(), unsafe_allow_html=True)
        components.html(inject_html(), height=0)
    except Exception:
        pass
