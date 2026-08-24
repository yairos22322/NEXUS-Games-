@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py main.py
) else (
    python main.py
)
if errorlevel 1 pause
