@echo off
setlocal
cd /d "%~dp0"
title NEXUS FIVE 3D ULTRA - Installer
color 0B

echo ==================================================
echo              NEXUS FIVE 3D ULTRA INSTALLER
echo ==================================================
echo.
where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=py
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo Python was not found.
        echo Install Python 3.10 through 3.14 and enable Add Python to PATH.
        pause
        exit /b 1
    )
)

echo [1/3] Updating pip...
%PYTHON% -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [2/3] Installing Panda3D + PBR graphics pipeline...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Launching NEXUS FIVE 3D ULTRA...
%PYTHON% main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Launch failed. Copy the error shown above and send it back for debugging.
pause
exit /b 1
