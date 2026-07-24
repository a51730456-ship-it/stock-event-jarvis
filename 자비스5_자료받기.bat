@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 자비스5 클라우드 자료 받기

echo.
echo   GitHub에 쌓인 자비스5 자료를 내려받아 합칩니다.
echo   노트북을 꺼 두었던 날의 자료도 함께 들어옵니다.
echo.

echo [1/2] 내려받는 중...
git pull --rebase --autostash
if errorlevel 1 (
  echo.
  echo   내려받기에 실패했습니다. 인터넷 연결이나 git 상태를 확인해 주세요.
  pause
  exit /b 1
)

echo.
echo [2/2] 로컬 DB에 합치는 중...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" jarvis5_sync.py import
) else (
  python jarvis5_sync.py import
)

echo.
echo   끝났습니다. 자비스를 실행해 '한국테마(선행감지)' 화면에서 확인하세요.
pause
