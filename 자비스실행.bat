@echo off
rem 이 .bat은 숨김 실행기(vbs)를 넘겨주고 즉시 닫힌다(대기하지 않음).
rem 실제 서버는 완전히 숨김 창(콘솔 없음)으로 뜬다 — Windows Terminal의
rem 기본 터미널 설정이 /min을 가로채 무시하는 문제를 우회 (2026-07-17)
cd /d "%~dp0"

rem ── 켤 때마다 새 판을 받아 온다 (2026-08-29 상하님 지시 "git pull 넣어라") ──
rem 온라인 앱은 GitHub 를 저절로 따라가는데 노트북은 안 따라간다. 그래서 고친
rem 것이 온라인에만 있고 노트북에는 없는 일이 되풀이됐다. 켤 때 한 번 받는다.
rem
rem **못 받아도 자비스는 뜬다.** 인터넷이 끊겼거나 git 이 없거나 이 폴더에서
rem 고친 것이 있어 막히면, 그냥 있던 코드로 켠다 — 받기 때문에 앱이 안 켜지면
rem 안 된다. 그래서 무슨 일이 있어도 아래 start 로 내려간다.
rem
rem **--ff-only 다.** 있던 것 위에 이어 붙이기만 하고, 합치거나 되돌리지 않는다.
rem db\jarvis.sqlite3 · 저장해 둔 목록처럼 이 컴퓨터에만 있는 것은 안 건드린다.
where git >nul 2>&1
if errorlevel 1 (
    echo [자비스] git 이 없어 새 판 받기를 건너뜁니다.
) else (
    echo [자비스] 새 판이 있는지 봅니다...
    git pull --ff-only
    if errorlevel 1 (
        echo.
        echo [자비스] 새 판을 못 받았습니다 — 있던 코드로 켭니다.
        echo          ^(인터넷이 끊겼거나, 이 폴더에서 고친 것이 있을 때 그렇습니다^)
        echo.
        rem 이 창은 바로 닫히므로, 못 받았을 때만 잠깐 세워 읽으시게 한다.
        timeout /t 8
    )
)

start "" wscript.exe "자비스실행_hidden.vbs"
exit
