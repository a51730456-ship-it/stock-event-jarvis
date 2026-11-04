# -*- coding: utf-8 -*-
"""안드로이드 설치 파일(APK)의 설계도를 만든다 (2026-11-04 상하님 — 「친구에게 카톡으로 보내면 바탕화면에 어플이 생기게」 ·
「비밀번호는 내가 친구에게 알려준다 · 아이폰 필요없다」).

무엇 — 바탕화면 아이콘 하나(「자비스」 → 자비스12 · 한국테마는 그 화면의 「🌏 한국테마 →」로). 온라인 앱을 연다(웹 보기 한 장).
  · 앱 안에는 화면 · 계산이 없다 — 온라인 앱을 그대로 보여 줄 뿐이라, 앱을 고치면 설치 파일을 다시 안 깔아도 바로 바뀐다.
  · **비밀번호를 넣지 않는다**(저장소가 공개다). 처음 열면 화면의 로그인 칸에 상하님이 알려 주신 비밀번호를 친다 —
    로그인 유지(auth 쿠키)는 앱 안에 남는다.
  · 온라인 앱 밖의 주소(네이버 뉴스 등)와 내려받기(엑셀)는 폰의 원래 브라우저로 연다.
  · 증권사 주문 · 자동매매 없음(CLAUDE.md 2절) — 보기만 하는 창이다.

이 파일은 설계도 글만 쓴다. 실제 만들기(gradle)와 서명은 깃허브(.github/workflows/j13_android.yml)가 한다.
쓰는 법: python research/j13_android_build.py <만들 폴더>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

APP_HOST = "https://stock-event-jarvis.streamlit.app"
PACKAGE = "io.github.stockeventjarvis.app"
# (자바 이름, 아이콘 밑 이름, 여는 화면, 아이콘 큰 글자, 아이콘 작은 글자, 아이콘 글자 색)
# 아이콘은 **하나**(2026-11-04 상하님 「하나만 만들어라 · 미국테마에서 선택하면 한국테마로 들어가도록」) — 자비스12 를 열고,
# 한국테마는 자비스12 맨 위 「🌏 한국테마 →」(같은 온라인 앱 주소라 이 창 안에서 넘어간다)로 간다.
SCREENS = (
    ("MainActivity", "자비스", "자비스12", "J", "JARVIS", (255, 196, 64)),
)
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
AGP_VERSION = "8.5.2"          # 안드로이드 만들기 도구 — gradle 8.7 과 짝(워크플로가 8.7 을 깐다)


def screen_url(page: str) -> str:
    return f"{APP_HOST}/{quote(page)}"


def _settings() -> str:
    return """pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "jarvis"
include ':app'
"""


def _root_build() -> str:
    return f"plugins {{ id 'com.android.application' version '{AGP_VERSION}' apply false }}\n"


def _app_build(version_code: int) -> str:
    return f"""plugins {{ id 'com.android.application' }}

android {{
    namespace '{PACKAGE}'
    compileSdk 34
    defaultConfig {{
        applicationId '{PACKAGE}'
        minSdk 24
        targetSdk 34
        versionCode {version_code}
        versionName "1.{version_code}"
    }}
    signingConfigs {{
        release {{
            // 서명 열쇠는 깃허브 실행 안에서만 만든다(저장소에 안 올림) — 경로 · 암호는 실행 환경 값으로 받는다
            storeFile file(System.getenv("JARVIS_KEYSTORE") ?: "missing.jks")
            storePassword System.getenv("JARVIS_KEY_PASS")
            keyAlias "jarvis"
            keyPassword System.getenv("JARVIS_KEY_PASS")
        }}
    }}
    buildTypes {{
        release {{
            minifyEnabled false
            signingConfig signingConfigs.release
        }}
    }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }}
}}
"""


def _manifest() -> str:
    activities = []
    for name, label, _page, _big, _small, _color in SCREENS:
        icon = "ic_" + name[:2].lower()
        activities.append(f"""        <activity
            android:name=".{name}"
            android:label="{label}"
            android:icon="@mipmap/{icon}"
            android:roundIcon="@mipmap/{icon}"
            android:exported="true"
            android:launchMode="singleTask"
            android:taskAffinity="{PACKAGE}.{name[:2].lower()}"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden|uiMode">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:label="자비스"
        android:icon="@mipmap/ic_ma"
        android:allowBackup="false"
        android:supportsRtl="true"
        android:usesCleartextTraffic="false"
        android:theme="@android:style/Theme.Material.NoActionBar">
{chr(10).join(activities)}
    </application>
</manifest>
"""


def _web_activity() -> str:
    return f"""package {PACKAGE};

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** 온라인 앱 한 화면을 여는 창. 화면 · 계산은 없다 — 온라인 앱을 그대로 보여 준다. 비밀번호는 넣지 않는다. */
public abstract class WebActivity extends Activity {{
    static final String TAG = "JarvisWeb";
    private WebView web;

    protected abstract String startUrl();

    static boolean inside(String host) {{
        if (host == null) return false;
        return host.endsWith("streamlit.app") || host.endsWith("streamlit.io");
    }}

    private void openOutside(Uri uri) {{
        try {{
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        }} catch (Exception ignored) {{
        }}
    }}

    @Override
    protected void onCreate(Bundle saved) {{
        super.onCreate(saved);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(web, true);     // 로그인 유지 쿠키(앱 안 작은 창이 심는다)
        web.setBackgroundColor(Color.rgb(6, 14, 34));      // 첫 그림이 뜨기 전 바탕(앱 짙은 남색)
        web.setWebChromeClient(new WebChromeClient() {{
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {{
                Log.i(TAG, "화면 " + message.messageLevel() + " " + message.message());
                return true;
            }}
        }});
        web.setWebViewClient(new WebViewClient() {{
            @Override
            public void onPageFinished(WebView view, String url) {{
                Log.i(TAG, "열림 " + url);
            }}

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {{
                if (request.isForMainFrame()) Log.w(TAG, "못 엶 " + request.getUrl() + " · " + error.getDescription());
            }}

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {{
                Uri uri = request.getUrl();
                if (inside(uri.getHost())) return false;    // 온라인 앱은 이 창 안에서
                openOutside(uri);                          // 네이버 뉴스 등은 폰 브라우저로
                return true;
            }}
        }});
        web.setDownloadListener((url, agent, disposition, mime, length) -> openOutside(Uri.parse(url)));
        if (saved != null) {{
            web.restoreState(saved);
        }} else {{
            web.loadUrl(startUrl());
        }}
    }}

    @Override
    protected void onSaveInstanceState(Bundle out) {{
        super.onSaveInstanceState(out);
        web.saveState(out);
    }}

    @Override
    protected void onPause() {{
        CookieManager.getInstance().flush();               // 로그인 유지를 바로 적어 둔다
        web.onPause();
        super.onPause();
    }}

    @Override
    protected void onResume() {{
        super.onResume();
        web.onResume();
    }}

    @Override
    public void onBackPressed() {{
        if (web.canGoBack()) {{
            web.goBack();
        }} else {{
            super.onBackPressed();
        }}
    }}
}}
"""


def _screen_activity(name: str, page: str) -> str:
    return f"""package {PACKAGE};

/** 바탕화면 아이콘 하나 — {page} 를 연다. */
public class {name} extends WebActivity {{
    @Override
    protected String startUrl() {{
        return "{screen_url(page)}";
    }}
}}
"""


def _icon(path: Path, size: int, big: str, small: str, color) -> None:
    from PIL import Image, ImageDraw, ImageFont

    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    top, bottom = (16, 34, 74), (6, 14, 34)
    for y in range(side):
        t = y / max(1, side - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        draw.line([(0, y), (side, y)], fill=row)
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, side - 1, side - 1], radius=int(side * 0.22), fill=255)
    image.putalpha(mask)

    def font(px):
        for name in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(name, px)
            except Exception:
                continue
        try:
            return ImageFont.load_default(size=px)
        except TypeError:
            return ImageFont.load_default()

    big_font, small_font = font(int(side * 0.42)), font(int(side * 0.17))
    draw.text((side / 2, side * 0.44), big, font=big_font, fill=tuple(color) + (255,), anchor="mm")
    draw.text((side / 2, side * 0.78), small, font=small_font, fill=(214, 228, 255, 255), anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((size, size), Image.LANCZOS).save(path)


def write_project(out: Path, *, version_code: int = 1, icons: bool = True) -> Path:
    out = Path(out)
    app = out / "app"
    src = app / "src" / "main"
    java = src / "java" / Path(*PACKAGE.split("."))
    java.mkdir(parents=True, exist_ok=True)
    (out / "settings.gradle").write_text(_settings(), encoding="utf-8")
    (out / "build.gradle").write_text(_root_build(), encoding="utf-8")
    (out / "gradle.properties").write_text("org.gradle.jvmargs=-Xmx2g\nandroid.useAndroidX=false\n", encoding="utf-8")
    (app / "build.gradle").write_text(_app_build(version_code), encoding="utf-8")
    (src / "AndroidManifest.xml").write_text(_manifest(), encoding="utf-8")
    (java / "WebActivity.java").write_text(_web_activity(), encoding="utf-8")
    for name, _label, page, big, small, color in SCREENS:
        (java / f"{name}.java").write_text(_screen_activity(name, page), encoding="utf-8")
        if icons:
            for density, px in ICON_SIZES.items():
                _icon(src / "res" / f"mipmap-{density}" / f"ic_{name[:2].lower()}.png", px, big, small, color)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("쓰는 법: python research/j13_android_build.py <만들 폴더>")
        return 2
    version = int(os.environ.get("GITHUB_RUN_NUMBER") or 1)
    out = write_project(Path(argv[1]), version_code=version)
    print(f"설계도 만듦: {out} · 판 번호 {version}")
    for _name, label, page, *_ in SCREENS:
        print(f"  아이콘 「{label}」 → {screen_url(page)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
