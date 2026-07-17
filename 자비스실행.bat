@echo off
rem 이 .bat은 숨김 실행기(vbs)를 넘겨주고 즉시 닫힌다(대기하지 않음).
rem 실제 서버는 완전히 숨김 창(콘솔 없음)으로 뜬다 — Windows Terminal의
rem 기본 터미널 설정이 /min을 가로채 무시하는 문제를 우회 (2026-07-17)
cd /d "%~dp0"
start "" wscript.exe "자비스실행_hidden.vbs"
exit
