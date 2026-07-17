@echo off
rem 더블클릭 시 서버 콘솔 창을 자동으로 최소화해서 시작한다 (2026-07-17 사용자 요청)
if not "%1"=="MINIMIZED" (
    start "Jarvis Server" /min cmd /c ""%~f0" MINIMIZED"
    exit /b
)
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Jarvis...
echo.
echo PC address: http://localhost:8501
echo Phone address: check the "Network URL" printed below.
echo.
if not exist ".venv\Scripts\python.exe" (
    echo [오류] .venv 가상환경의 Python을 찾을 수 없습니다.
    echo 먼저 README.md의 가상환경 생성 및 설치 명령을 실행하세요.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
