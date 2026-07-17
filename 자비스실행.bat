@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [오류] .venv 가상환경의 Python을 찾을 수 없습니다.
    echo 먼저 README.md의 가상환경 생성 및 설치 명령을 실행하세요.
    pause
    exit /b 1
)
rem 서버 콘솔을 최소화 상태로 실행 — Windows 터미널이 /min을 무시하는
rem 문제가 있어 클래식 콘솔(conhost)로 강제한다 (2026-07-17 사용자 요청)
start "Jarvis Server" /min conhost.exe ".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
rem 서버가 뜰 시간을 준 뒤 브라우저를 자동으로 연다 — 로그인 화면만 보이게
timeout /t 4 /nobreak >nul
start "" http://localhost:8501
exit
