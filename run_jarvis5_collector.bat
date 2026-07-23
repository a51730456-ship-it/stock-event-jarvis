@echo off
cd /d "%~dp0"
title Jarvis5 Theme Lead Collector
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" jarvis5_collector.py --interval 180
) else (
  python jarvis5_collector.py --interval 180
)
pause
