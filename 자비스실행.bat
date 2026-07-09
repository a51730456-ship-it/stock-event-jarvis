@echo off
cd /d "%~dp0"
echo Starting Jarvis...
echo.
echo PC address: http://localhost:8501
echo Phone address: check the "Network URL" printed below.
echo.
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
