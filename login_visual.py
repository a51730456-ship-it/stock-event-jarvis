"""로그인 성공 직후 본문 위에 먼저 렌더링되는 CSS 전환 오버레이."""


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
            box-shadow: 0 0 0 2px rgba(75, 181, 255, .84), 0 0 24px rgba(35, 139, 255, .34);
        }
        .jarvis-early-earth .jarvis-earth-image {
            position: absolute;
            inset: -8%;
            display: block;
            width: 116%;
            max-width: none;
            height: 116%;
            object-fit: cover;
            opacity: 1;
            transform: scale(1.08) rotate(0deg);
            animation: jarvis-early-earth-turn 120s linear infinite;
            animation-fill-mode: both;
            will-change: transform;
        }
        .jarvis-early-earth .jarvis-orbit {
            position: absolute;
            z-index: 1;
            left: -2%;
            top: 35%;
            width: 104%;
            height: 29%;
            border: 2px solid rgba(58, 155, 255, .72);
            border-radius: 50%;
            transform: rotate(-13deg);
            animation: jarvis-early-ring 2s ease-out forwards;
            animation-fill-mode: forwards;
        }
        .jarvis-early-earth .jarvis-orbit-secondary {
            top: 37%;
            height: 25%;
            border-width: 1px;
            transform: rotate(58deg);
            animation-name: jarvis-early-ring-soft;
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
        @keyframes jarvis-early-earth-turn {
            from { transform: scale(1.08) rotate(0deg); }
            to { transform: scale(1.08) rotate(360deg); }
        }
        @keyframes jarvis-early-ring {
            0% { opacity: .45; box-shadow: 0 0 2px rgba(73, 178, 255, .1); }
            8%, 20% { opacity: 1; border-color: #79ceff; box-shadow: 0 0 15px #2598ff; }
            50%, 100% { opacity: .34; box-shadow: 0 0 6px rgba(37, 152, 255, .25); }
        }
        @keyframes jarvis-early-ring-soft {
            0% { opacity: .2; }
            8%, 20% { opacity: .9; border-color: #8ad7ff; box-shadow: 0 0 12px #278fff; }
            50%, 100% { opacity: .18; }
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
