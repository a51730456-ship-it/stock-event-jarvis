"""로그인 성공 직후 본문 위에 먼저 렌더링되는 CSS 전환 오버레이."""

# 로그인 성공 시 한 번만 재생되는 아주 짧은(약 0.32초) 2음 알림음. 네트워크 요청 없이
# base64로 인라인 삽입하므로 화면 속도에는 영향을 주지 않는다. 진폭 자체를 낮게
# 합성해서(피크 약 -24dB) 이미 조용하며, 브라우저 자동재생 정책상 무음 처리되더라도
# 화면 렌더링에는 영향이 없다(2026-07-15 사용자 요청: "아주 소리 작게").
_LOGIN_CHIME_WAV_BASE64 = (
    "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"
)


def render_login_transition(st, earth_markup):
    """Render the one-shot transition before the authenticated app body streams in."""
    st.markdown(
        """
        <style>
        .jarvis-login-transition-early {
            position: fixed !important;
            inset: 0;
            z-index: 2147483647 !important;
            display: block;
            overflow: hidden;
            pointer-events: none;
            isolation: isolate;
            opacity: 1;
            visibility: visible;
            background: radial-gradient(circle at center, #071b3a 0, #020713 46%, #000207 100%);
            animation: jarvis-early-overlay 2s linear forwards;
            animation-fill-mode: forwards;
        }
        .jarvis-early-earth {
            position: absolute;
            z-index: 2;
            left: 50%;
            top: 50%;
            width: min(58vw, 620px);
            transform: translate(-92%, -50%) scale(.82);
            animation: jarvis-early-earth-zoom 2s cubic-bezier(.58, 0, .88, .72) forwards;
            animation-fill-mode: forwards;
            will-change: transform;
        }
        .jarvis-early-earth .jarvis-earth-visual {
            position: relative;
            width: 100%;
            aspect-ratio: 1;
            isolation: isolate;
        }
        .jarvis-early-earth .jarvis-earth-disc {
            position: absolute;
            inset: 7.5%;
            z-index: 2;
            overflow: hidden;
            border-radius: 50%;
            background: #01040a;
            box-shadow: 0 0 0 2px rgba(91, 190, 255, .78), 0 0 18px rgba(34, 139, 255, .3);
            animation: jarvis-early-rim-charge 2s ease-out forwards;
            animation-fill-mode: forwards;
        }
        .jarvis-early-earth .jarvis-earth-surface {
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background-color: #02102d;
            background-image: var(--jarvis-earth-texture);
            background-repeat: repeat-x;
            background-size: 200% 100%;
            background-position: 120% 50%;
            opacity: 1;
            animation: jarvis-early-earth-surface-turn 80s linear infinite;
            animation-fill-mode: both;
            will-change: background-position;
        }
        .jarvis-early-earth .jarvis-earth-surface::after {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 50%;
            pointer-events: none;
            background:
                radial-gradient(circle at 32% 27%, rgba(126, 202, 255, .16) 0, transparent 32%),
                radial-gradient(circle at 48% 44%, transparent 42%, rgba(0, 5, 19, .22) 68%, rgba(0, 2, 10, .78) 100%),
                linear-gradient(90deg, rgba(0, 4, 16, .46), transparent 24%, transparent 68%, rgba(0, 3, 14, .62));
        }
        .jarvis-early-panel {
            position: absolute;
            z-index: 4;
            right: clamp(2rem, 8vw, 9rem);
            top: 50%;
            width: min(34vw, 460px);
            padding: 2rem;
            transform: translateY(-50%);
            border: 1px solid rgba(85, 151, 236, .32);
            border-radius: 22px;
            color: #dcecff;
            background: linear-gradient(145deg, rgba(15, 31, 56, .82), rgba(3, 10, 24, .92));
            box-shadow: 0 24px 70px rgba(0, 0, 0, .45), inset 0 1px rgba(179, 220, 255, .1);
            animation: jarvis-early-panel-fade 2s ease-out forwards;
            animation-fill-mode: forwards;
        }
        .jarvis-early-panel-kicker {
            color: #64b7ff;
            font: 700 .7rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .2em;
        }
        .jarvis-early-panel-title { margin-top: .8rem; font-size: 1.8rem; font-weight: 800; }
        .jarvis-early-panel-line {
            height: 46px;
            margin-top: 1.4rem;
            border: 1px solid rgba(92, 157, 234, .28);
            border-radius: 11px;
            background: rgba(2, 9, 22, .66);
        }
        .jarvis-early-status {
            position: absolute;
            z-index: 6;
            top: 50%;
            left: 50%;
            width: min(92vw, 680px);
            transform: translate(-50%, -50%);
            color: #eaf6ff;
            text-align: center;
            text-shadow: 0 0 12px #00152f, 0 0 24px rgba(74, 174, 255, .95);
            opacity: 0;
            animation: jarvis-early-status-show 2s linear forwards;
            animation-fill-mode: forwards;
        }
        .jarvis-early-access {
            font: 800 clamp(1.15rem, 3vw, 1.85rem)/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .2em;
        }
        .jarvis-early-online {
            margin-top: .38rem;
            color: #69bfff;
            font: 700 clamp(.78rem, 2vw, 1rem)/1.35 ui-monospace, SFMono-Regular, Consolas, monospace;
            letter-spacing: .24em;
        }
        .jarvis-early-complete {
            margin-top: .28rem;
            color: #b9cce0;
            font-size: clamp(.72rem, 1.8vw, .9rem);
            letter-spacing: .12em;
        }
        .jarvis-early-light {
            position: absolute;
            z-index: 3;
            left: 50%;
            top: 50%;
            width: 9vmin;
            aspect-ratio: 1;
            border: 2px solid rgba(82, 176, 255, .92);
            border-radius: 50%;
            opacity: 0;
            transform: translate(-50%, -50%) scale(.1);
            box-shadow: 0 0 34px rgba(36, 137, 255, .9), inset 0 0 30px rgba(31, 129, 255, .62);
            animation: jarvis-early-light-expand 2s ease-in forwards;
            animation-fill-mode: forwards;
        }
        @keyframes jarvis-early-earth-surface-turn {
            from { background-position: 120% 50%; }
            to { background-position: -80% 50%; }
        }
        @keyframes jarvis-early-rim-charge {
            0% { box-shadow: 0 0 0 2px rgba(91, 190, 255, .62), 0 0 10px rgba(34, 139, 255, .2); }
            8%, 20% { box-shadow: 0 0 0 2px #8ad7ff, 0 0 28px rgba(37, 152, 255, .85); }
            50%, 100% { box-shadow: 0 0 0 2px rgba(91, 190, 255, .78), 0 0 18px rgba(34, 139, 255, .3); }
        }
        @keyframes jarvis-early-panel-fade {
            0% { opacity: 1; transform: translateY(-50%) scale(1); }
            20%, 100% { opacity: 0; transform: translateY(-50%) scale(.98); }
        }
        @keyframes jarvis-early-status-show {
            0%, 19.99% { opacity: 0; transform: translate(-50%, calc(-50% + 6px)); }
            20%, 50% { opacity: 1; transform: translate(-50%, -50%); }
            50.01%, 100% { opacity: 0; transform: translate(-50%, calc(-50% - 5px)); }
        }
        @keyframes jarvis-early-earth-zoom {
            0% { transform: translate(-92%, -50%) scale(.82); }
            20% { transform: translate(-50%, -50%) scale(.78); }
            50% { transform: translate(-50%, -50%) scale(.84); }
            100% { transform: translate(-50%, -50%) scale(5.8); }
        }
        @keyframes jarvis-early-light-expand {
            0%, 49.9% { opacity: 0; transform: translate(-50%, -50%) scale(.1); }
            56% { opacity: .88; }
            100% { opacity: 0; transform: translate(-50%, -50%) scale(24); }
        }
        @keyframes jarvis-early-overlay {
            0%, 84% { opacity: 1; visibility: visible; }
            99.9% { opacity: 0; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }
        @keyframes jarvis-early-reduced {
            0% { opacity: 1; visibility: visible; }
            100% { opacity: 0; visibility: hidden; }
        }
        @media (max-width: 768px) {
            .jarvis-early-earth { width: min(92vw, 500px); transform: translate(-50%, -66%) scale(.72); }
            .jarvis-early-panel { right: 50%; top: auto; bottom: 7%; width: min(84vw, 520px); padding: 1.2rem; transform: translateX(50%); }
            .jarvis-early-panel-line { height: 38px; margin-top: .8rem; }
            @keyframes jarvis-early-panel-fade {
                0% { opacity: 1; transform: translateX(50%) scale(1); }
                20%, 100% { opacity: 0; transform: translateX(50%) scale(.98); }
            }
            @keyframes jarvis-early-earth-zoom {
                0% { transform: translate(-50%, -66%) scale(.72); }
                20% { transform: translate(-50%, -50%) scale(.7); }
                50% { transform: translate(-50%, -50%) scale(.76); }
                100% { transform: translate(-50%, -50%) scale(5.8); }
            }
        }
        @media (prefers-reduced-motion: reduce) {
            .jarvis-login-transition-early { animation: jarvis-early-reduced .2s ease-out forwards !important; }
            .jarvis-early-earth, .jarvis-early-earth *, .jarvis-early-panel,
            .jarvis-early-status, .jarvis-early-light { animation: none !important; }
        }
        </style>
        <div class="jarvis-login-transition-early" aria-hidden="true">
            <audio autoplay preload="auto" style="display:none">
                <source src="data:audio/wav;base64,""" + _LOGIN_CHIME_WAV_BASE64 + """" type="audio/wav">
            </audio>
            <div class="jarvis-early-earth">
        """ + earth_markup + """
            </div>
            <div class="jarvis-early-panel">
                <div class="jarvis-early-panel-kicker">SECURE MARKET INTELLIGENCE</div>
                <div class="jarvis-early-panel-title">Stock Event Jarvis</div>
                <div class="jarvis-early-panel-line"></div>
            </div>
            <div class="jarvis-early-light"></div>
            <div class="jarvis-early-status">
                <div class="jarvis-early-access">ACCESS GRANTED</div>
                <div class="jarvis-early-online">JARVIS ONLINE</div>
                <div class="jarvis-early-complete">인증 완료</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
