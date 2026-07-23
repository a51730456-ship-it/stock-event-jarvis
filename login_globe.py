"""로그인 화면의 지구를 진짜 구면으로 그린다 (2026-07-23 사용자 지시).

기존 방식은 네모난 세계지도를 원형 창 뒤에서 옆으로 미는 것이라 구면 계산이
전혀 없었다. 그래서 대륙이 가장자리로 가도 압축되지 않고, 지도의 위·아래 끝인
극지방이 원판을 가로지르는 흰 띠로 걸려 '돌아가는 공'이 아니라 '지도가 지나가는
동그라미'로 보였다.

여기서는 픽셀마다 구면 법선을 구해 위도·경도로 바꿔 텍스처를 찍는다. 조명·대기
산란·하이라이트 롤오프 상수는 파이썬으로 미리 그려 눈으로 맞춘 값을 그대로 옮겼다.

WebGL을 못 쓰는 환경에서는 정적 원형 그라디언트로 조용히 물러난다.
"""


# 파이썬 사전 렌더링에서 맞춘 값 (scratchpad/globe_preview.py)
_TILT_RAD = 0.408407  # 자전축 23.4°
_LIGHT = (-0.62, 0.34, 0.52)
_AMBIENT = 0.07
_DAY_GAIN = 1.02
_NIGHT_TINT = (0.030, 0.052, 0.098)
_TERM_SOFT = 0.22
_RIM_GAIN = 0.85
_SHOULDER = 0.42
_SPIN_SECONDS = 90.0

_FRAGMENT_SHADER = """
precision highp float;
uniform vec2 uRes;
uniform float uSpin;
uniform sampler2D uTex;
const float PI = 3.14159265359;
const float TILT = %(tilt)f;
const vec3 LIGHT = vec3(%(lx)f, %(ly)f, %(lz)f);
const float AMBIENT = %(ambient)f;
const float DAY_GAIN = %(day_gain)f;
const vec3 NIGHT_TINT = vec3(%(nr)f, %(ng)f, %(nb)f);
const float TERM_SOFT = %(term)f;
const float RIM_GAIN = %(rim)f;
const float SHOULDER = %(shoulder)f;
const vec3 ATMO = vec3(0.36, 0.62, 1.0);

void main() {
    vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / (0.5 * min(uRes.x, uRes.y));
    /* 구가 화면의 짧은 쪽에서 차지하는 비율. 1보다 커지면 구가 화면을 넘어
       위아래가 잘린다(2026-07-23 실측 — 1.10으로 두었다가 잘렸다).
       0.86이면 바깥 대기광이 들어설 자리까지 남는다. */
    p /= 0.86;
    float r2 = dot(p, p);

    if (r2 > 1.0) {
        /* 원 바깥 — 대기가 흩뿌리는 빛만 남는다 */
        float glow = exp(-(sqrt(r2) - 1.0) * 13.0) * 0.34;
        gl_FragColor = vec4(ATMO * glow, glow);
        return;
    }

    float z = sqrt(max(1.0 - r2, 0.0));
    vec3 n = vec3(p, z);

    /* 자전축 기울기를 되돌린다 */
    float ct = cos(-TILT), st = sin(-TILT);
    vec3 a = vec3(n.x * ct - n.y * st, n.x * st + n.y * ct, n.z);

    /* 자전을 되돌린다 */
    float cs = cos(-uSpin), ss = sin(-uSpin);
    vec3 t = vec3(a.x * cs + a.z * ss, a.y, -a.x * ss + a.z * cs);

    float lat = asin(clamp(t.y, -1.0, 1.0));
    float lon = atan(t.x, t.z);
    vec2 uv = vec2(lon / (2.0 * PI) + 0.5, 0.5 - lat / PI);
    vec3 albedo = texture2D(uTex, uv).rgb;

    /* 부드러운 낮·밤 경계 */
    vec3 L = normalize(LIGHT);
    float ndl = dot(n, L);
    float day = clamp((ndl + TERM_SOFT) / (2.0 * TERM_SOFT), 0.0, 1.0);
    day = day * day * (3.0 - 2.0 * day);

    vec3 lit = albedo * (AMBIENT + DAY_GAIN * day);
    vec3 night = albedo * 0.16 + NIGHT_TINT;
    vec3 color = mix(night, lit, day);

    /* 가장자리 대기 산란 */
    float fres = pow(clamp(1.0 - z, 0.0, 1.0), 3.0);
    color += ATMO * (fres * (0.20 + 0.85 * day) * RIM_GAIN);

    /* 하이라이트 롤오프 — 사하라와 구름이 순백으로 뭉개지지 않게 */
    color = color / (1.0 + SHOULDER * color) * (1.0 + SHOULDER);

    float edge = clamp((1.0 - sqrt(r2)) * min(uRes.x, uRes.y) * 0.5, 0.0, 1.0);
    gl_FragColor = vec4(clamp(color, 0.0, 1.0), edge);
}
""" % {
    "tilt": _TILT_RAD,
    "lx": _LIGHT[0], "ly": _LIGHT[1], "lz": _LIGHT[2],
    "ambient": _AMBIENT,
    "day_gain": _DAY_GAIN,
    "nr": _NIGHT_TINT[0], "ng": _NIGHT_TINT[1], "nb": _NIGHT_TINT[2],
    "term": _TERM_SOFT,
    "rim": _RIM_GAIN,
    "shoulder": _SHOULDER,
}


def globe_html(texture_src: str) -> str:
    """구면 지구 캔버스 한 조각. 텍스처는 data: URI로 이미 들어와 있다."""
    return """<!doctype html>
<meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%%; background: transparent; overflow: hidden; }
  #stage { position: relative; width: 100%%; height: 100%%; }
  canvas { display: block; width: 100%%; height: 100%%; }
  /* WebGL을 못 쓸 때만 보이는 정적 지구 */
  #fallback {
    position: absolute; inset: 0; margin: auto;
    width: min(100%%, 100vh); aspect-ratio: 1; border-radius: 50%%;
    background: radial-gradient(circle at 34%% 30%%, #1f7fd0, #0a3167 58%%, #020a18 82%%);
    box-shadow: 0 0 42px rgba(70, 160, 255, .45), inset -18px -10px 60px rgba(0, 0, 0, .75);
    display: none;
  }
</style>
<div id="stage">
  <canvas id="globe" role="img" aria-label="우주에서 본 자전하는 지구"></canvas>
  <div id="fallback" aria-hidden="true"></div>
</div>
<script>
(function () {
  var canvas = document.getElementById("globe");
  var gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: false, antialias: false })
        || canvas.getContext("experimental-webgl", { alpha: true, premultipliedAlpha: false });
  function giveUp() {
    canvas.style.display = "none";
    document.getElementById("fallback").style.display = "block";
  }
  if (!gl) { giveUp(); return; }

  var VERT = "attribute vec2 aPos; void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }";
  var FRAG = %(frag)s;

  function compile(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { return null; }
    return s;
  }
  var vs = compile(gl.VERTEX_SHADER, VERT), fs = compile(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) { giveUp(); return; }
  var prog = gl.createProgram();
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { giveUp(); return; }
  gl.useProgram(prog);

  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  var aPos = gl.getAttribLocation(prog, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  var uRes = gl.getUniformLocation(prog, "uRes");
  var uSpin = gl.getUniformLocation(prog, "uSpin");
  var uTex = gl.getUniformLocation(prog, "uTex");

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  var loaded = false;
  var tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
                new Uint8Array([6, 20, 48, 255]));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

  var image = new Image();
  image.onload = function () {
    loaded = true;
    /* 원본은 1400x1400이다. WebGL1은 2의 거듭제곱이 아닌 텍스처에 가로 반복을
       허용하지 않으므로 2048x1024로 다시 그린다. 등장방형 지도를 2:1로 되돌리는
       일이기도 해서 위도 왜곡도 같이 사라진다. */
    var c = document.createElement("canvas");
    c.width = 2048; c.height = 1024;
    c.getContext("2d").drawImage(image, 0, 0, 2048, 1024);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    draw(0);   /* 지도가 도착하자마자 한 장 그려둔다 */
  };
  image.onerror = giveUp;
  image.src = %(tex)s;

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, Math.round(canvas.clientWidth * dpr));
    var h = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w; canvas.height = h;
    }
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  if (window.ResizeObserver) { new ResizeObserver(resize).observe(canvas); }
  window.addEventListener("resize", resize);

  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function draw(seconds) {
    resize();
    gl.uniform2f(uRes, canvas.width, canvas.height);
    gl.uniform1f(uSpin, (seconds / %(period)f) * 6.283185307);
    gl.uniform1i(uTex, 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /* 첫 장은 requestAnimationFrame을 기다리지 않고 바로 그린다. 탭이 화면에
     없거나 브라우저가 프레임을 합성하지 않는 동안에는 rAF가 아예 돌지 않아
     캔버스가 빈 채로 남는데, 그때도 지구는 보여야 한다. */
  draw(0);

  var start = null;
  function frame(now) {
    if (start === null) { start = now; }
    draw(still ? 0 : (now - start) / 1000);
    if (!still) { window.requestAnimationFrame(frame); }
  }
  if (!still) { window.requestAnimationFrame(frame); }

  /* 검증·복구용 — 프레임 합성이 멈춘 환경에서도 한 장 그려볼 수 있게 한다. */
  window.__jarvisGlobeDraw = draw;
  window.__jarvisGlobeReady = function () { return loaded; };
})();
</script>
""" % {
        "frag": _js_string(_FRAGMENT_SHADER),
        "tex": _js_string(texture_src),
        "period": _SPIN_SECONDS,
    }


def _js_string(value: str) -> str:
    """자바스크립트 문자열 리터럴로 안전하게 감싼다."""
    import json

    return json.dumps(value)


def render_login_globe(st, texture_src: str, *, height: int = 660) -> None:
    """로그인 화면 왼쪽에 자전하는 지구를 띄운다."""
    # st.components.v1.html은 Streamlit이 2026-06-01부로 폐기 예정이라 st.iframe을 쓴다.
    # st.iframe은 HTML 문자열도 그대로 받는다(입력 종류를 스스로 판별한다).
    st.iframe(globe_html(texture_src), height=height)
